"""Cloud History contract tests with in-memory AWS protocol fakes.

No account, credentials, network, or AWS resources are used by these tests.
"""

from __future__ import annotations

import copy
import hashlib
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Lock

import pytest

from app.cloud_history import CloudHistoryStore
from app.history import HistoryNotFound, HistoryQuotaExceeded, HistoryStorageError


def val(item, name, default=None):
    attribute = item.get(name)
    if attribute is None:
        return default
    return attribute.get("S", int(attribute["N"]) if "N" in attribute else None)


class Conflict(Exception):
    response = {"Error": {"Code": "TransactionCanceledException"}}


class FakeDynamoDB:
    def __init__(self):
        self.items = {}
        self.lock = Lock()
        self.commit_then_raise = False
        self.transactions = []

    @staticmethod
    def key(item):
        return (val(item, "pk"), val(item, "sk"))

    def get_item(self, *, Key, **_):
        with self.lock:
            row = self.items.get(self.key(Key))
            return {"Item": copy.deepcopy(row)} if row else {}

    def query(self, *, ExpressionAttributeValues, **_):
        pk = val({"pk": ExpressionAttributeValues[":pk"]}, "pk")
        with self.lock:
            return {"Items": [copy.deepcopy(row) for (owner, sk), row in self.items.items()
                              if owner == pk and sk.startswith("ITEM#")]}

    def scan(self, **_):
        with self.lock:
            return {"Items": copy.deepcopy(list(self.items.values()))}

    def update_item(self, *, Key, UpdateExpression, **_):
        key = self.key(Key)
        with self.lock:
            row = self.items.get(key)
            if "SET #state = :deleting" in UpdateExpression:
                if not row and key[1] != "QUOTA":
                    raise Conflict()
                if row and key[1] != "QUOTA" and val(row, "state") != "active":
                    raise Conflict()
                row = row or copy.deepcopy(Key)
                row["state"] = {"S": "deleting"}
                if key[1] == "QUOTA":
                    row.setdefault("used_items", {"N": "0"})
                    row.setdefault("used_bytes", {"N": "0"})
                self.items[key] = row
            elif UpdateExpression == "REMOVE #state":
                if not row or val(row, "used_items") != 0 or val(row, "used_bytes") != 0:
                    raise Conflict()
                row.pop("state", None)
            else:
                raise AssertionError(UpdateExpression)

    def transact_write_items(self, *, TransactItems, **kwargs):
        with self.lock:
            self.transactions.append({"TransactItems": copy.deepcopy(TransactItems),
                                      **copy.deepcopy(kwargs)})
            if "Put" in TransactItems[-1]:
                row = TransactItems[-1]["Put"]["Item"]
                if self.key(row) in self.items:
                    raise Conflict()
                for operation in TransactItems[:2]:
                    update = operation["Update"]
                    key = self.key(update["Key"])
                    current = self.items.get(key, {})
                    values = update["ExpressionAttributeValues"]
                    if val(current, "state") == "deleting":
                        raise Conflict()
                    if (val(current, "used_items", 0) >= int(values[":max_items"]["N"])
                            or val(current, "used_bytes", 0) >
                            int(values[":remaining_bytes"]["N"])):
                        raise Conflict()
                for operation in TransactItems[:2]:
                    self._change_counter(operation["Update"])
                self.items[self.key(row)] = copy.deepcopy(row)
                if self.commit_then_raise:
                    self.commit_then_raise = False
                    raise ConnectionError("response lost after commit")
            else:
                delete = TransactItems[0]["Delete"]
                key = self.key(delete["Key"])
                if key not in self.items or val(self.items[key], "state") != "deleting":
                    raise Conflict()
                for operation in TransactItems[1:]:
                    update = operation["Update"]
                    current = self.items.get(self.key(update["Key"]), {})
                    values = update["ExpressionAttributeValues"]
                    if (val(current, "used_items", 0) < 1 or
                            val(current, "used_bytes", 0) < int(values[":bytes"]["N"])):
                        raise Conflict()
                self.items.pop(key)
                for operation in TransactItems[1:]:
                    self._change_counter(operation["Update"])

    def _change_counter(self, update):
        key = self.key(update["Key"])
        row = self.items.get(key, copy.deepcopy(update["Key"]))
        values = update["ExpressionAttributeValues"]
        row["used_items"] = {"N": str(val(row, "used_items", 0) +
                                      int(values[":item_delta"]["N"]))}
        row["used_bytes"] = {"N": str(val(row, "used_bytes", 0) +
                                      int(values[":byte_delta"]["N"]))}
        self.items[key] = row


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.fail_delete = False
        self.put_requests = []

    def put_object(self, *, Key, Body, IfNoneMatch, ServerSideEncryption, **kwargs):
        assert IfNoneMatch == "*"
        assert ServerSideEncryption == "AES256"
        self.put_requests.append({"Key": Key, "Body": Body,
                                  "IfNoneMatch": IfNoneMatch,
                                  "ServerSideEncryption": ServerSideEncryption,
                                  **kwargs})
        if Key in self.objects:
            raise Conflict()
        self.objects[Key] = (Body, datetime.now(timezone.utc))

    def get_object(self, *, Key, **_):
        return {"Body": io.BytesIO(self.objects[Key][0])}

    def delete_object(self, *, Key, **_):
        if self.fail_delete:
            raise OSError("temporary failure")
        self.objects.pop(Key, None)

    def list_objects_v2(self, **_):
        return {"Contents": [{"Key": key, "LastModified": timestamp}
                             for key, (_, timestamp) in self.objects.items()],
                "IsTruncated": False}


@pytest.fixture
def store():
    s3 = FakeS3()
    ddb = FakeDynamoDB()
    return CloudHistoryStore("private-test", "history-test", "ap-south-1",
                             s3_client=s3, dynamodb_client=ddb)


def snapshot(data):
    return {"input": {"sha256": hashlib.sha256(data).hexdigest()},
            "models": [{"status": "success", "model_key": "v3_e2"}]}


def save(store, owner="alice", data=b"exact original"):
    return store.save(owner, "folder\\photo.png", "image/png", data,
                      snapshot(data), ["v3_e2"])


def test_save_read_list_delete_and_owner_isolation(store):
    saved = save(store)
    history_id = saved["history_id"]
    assert saved["filename"] == "photo.png"
    assert saved["result"] == snapshot(b"exact original")
    assert store.read_original("alice", history_id) == b"exact original"
    assert store.list("alice")["items"][0]["history_id"] == history_id
    assert store.quota("alice")["used_items"] == 1
    with pytest.raises(HistoryNotFound):
        store.get("bob", history_id)
    assert store.delete("alice", history_id) == {"deleted": True, "pending": False}
    with pytest.raises(HistoryNotFound):
        store.read_original("alice", history_id)
    assert store.quota("alice")["used_items"] == 0
    assert store.s3.objects == {}


def test_concurrent_saves_respect_atomic_item_quota(store):
    store.MAX_ITEMS_PER_OWNER = 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = list(pool.map(lambda _: _attempt_save(store), range(2)))
    assert sorted(attempts) == ["quota", "saved"]
    assert store.quota("alice")["used_items"] == 1
    assert len(store.s3.objects) == 1


def test_shared_byte_quota_applies_across_owners(store):
    store.MAX_BYTES_GLOBAL = 7
    first = save(store, "alice", b"one")
    assert first["byte_count"] == 3
    with pytest.raises(HistoryQuotaExceeded):
        save(store, "bob", b"12345")
    assert store.quota("bob")["used_items"] == 0
    assert len(store.s3.objects) == 1


def test_history_pages_follow_newest_first_cursor(store):
    older = save(store, data=b"older")
    newer = save(store, data=b"newer")
    store.ddb.items[(store._owner_pk("alice"), f"ITEM#{older['history_id']}")][
        "created_at"
    ] = {"S": "2026-10-29T00:00:00.000000+00:00"}
    store.ddb.items[(store._owner_pk("alice"), f"ITEM#{newer['history_id']}")][
        "created_at"
    ] = {"S": "2026-10-29T00:00:01.000000+00:00"}
    first_page = store.list("alice", limit=1)
    assert [item["history_id"] for item in first_page["items"]] == [newer["history_id"]]
    assert first_page["next_cursor"]
    second_page = store.list("alice", cursor=first_page["next_cursor"], limit=1)
    assert [item["history_id"] for item in second_page["items"]] == [older["history_id"]]
    assert second_page["next_cursor"] is None


def test_ambiguous_transaction_response_preserves_committed_original(store):
    store.ddb.commit_then_raise = True
    saved = save(store)
    assert store.read_original("alice", saved["history_id"]) == b"exact original"
    assert store.quota("alice")["used_items"] == 1
    assert len(store.s3.objects) == 1


def _attempt_save(store):
    try:
        save(store)
        return "saved"
    except HistoryQuotaExceeded:
        return "quota"


def test_failed_s3_delete_hides_item_then_sweep_retries(store):
    saved = save(store)
    store.s3.fail_delete = True
    with pytest.raises(HistoryStorageError):
        store.delete("alice", saved["history_id"])
    with pytest.raises(HistoryNotFound):
        store.get("alice", saved["history_id"])
    assert store.quota("alice")["used_items"] == 1
    store.s3.fail_delete = False
    assert store.sweep()["removed"] == 1
    assert store.quota("alice")["used_items"] == 0


def test_expiry_is_enforced_before_sweep(store):
    saved = save(store)
    item_key = (store._owner_pk("alice"), f"ITEM#{saved['history_id']}")
    store.ddb.items[item_key]["expires_at"] = {"S": "2000-01-01T00:00:00+00:00"}
    with pytest.raises(HistoryNotFound):
        store.get("alice", saved["history_id"])
    assert store.list("alice")["items"] == []
    assert store.sweep()["expired_marked"] == 1
    assert store.s3.objects == {}


def test_account_delete_hides_all_then_retries_failure(store):
    save(store, data=b"one")
    save(store, data=b"two")
    store.s3.fail_delete = True
    result = store.delete_account("alice")
    assert result["complete"] is False and result["pending"] == 2
    assert store.list("alice")["items"] == []
    with pytest.raises(HistoryStorageError):
        save(store, data=b"three")
    store.s3.fail_delete = False
    assert store.sweep()["removed"] == 2
    assert store.quota("alice")["used_items"] == 0
    save(store, data=b"after deletion")


def test_orphan_cleanup_waits_one_hour(store):
    store.s3.objects["originals/" + "a" * 32 + ".bin"] = (
        b"orphan", datetime.now(timezone.utc) - timedelta(hours=2)
    )
    assert store.sweep()["orphans_removed"] == 1
    assert store.s3.objects == {}


def test_cloud_environment_requires_bucket_and_table(monkeypatch):
    monkeypatch.delenv("IOS_S3_BUCKET", raising=False)
    monkeypatch.delenv("IOS_DYNAMODB_TABLE", raising=False)
    with pytest.raises(ValueError, match="IOS_S3_BUCKET and IOS_DYNAMODB_TABLE"):
        CloudHistoryStore.from_environment()


def test_aws_requests_match_botocore_shapes_when_sdk_is_installed(store):
    pytest.importorskip("botocore")
    from botocore.session import get_session
    from botocore.validate import ParamValidator

    saved = save(store)
    store.delete("alice", saved["history_id"])
    session = get_session()
    requests = (
        ("dynamodb", "TransactWriteItems", store.ddb.transactions),
        ("s3", "PutObject", store.s3.put_requests),
    )
    for service, operation, calls in requests:
        shape = session.get_service_model(service).operation_model(operation).input_shape
        for params in calls:
            report = ParamValidator().validate(params, shape)
            assert not report.has_errors(), report.generate_report()
