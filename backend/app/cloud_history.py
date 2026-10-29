"""S3 originals and DynamoDB metadata for opted-in cloud History.

The table has string keys ``pk`` and ``sk``. Owner partitions contain
``ITEM#<history_id>`` rows and one ``QUOTA`` row; a ``GLOBAL`` partition has
another ``QUOTA`` row. No GSI is required for the small, bounded trial.
The instance role supplies credentials. This module makes no AWS calls at import.

Record TTL must remain disabled: automatic removal would bypass S3 deletion and
transactional quota decrement. The app's sweep is authoritative for expiry.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import timedelta
from typing import Any
from uuid import uuid4

from .history import (
    HistoryNotFound,
    HistoryQuotaExceeded,
    HistoryStorageError,
    HistoryStore,
    InvalidHistoryRecord,
    _EXPIRY_DAYS,
    _MAX_PAGE_SIZE,
)


def _s(value: str) -> dict[str, str]:
    return {"S": value}


def _n(value: int) -> dict[str, str]:
    return {"N": str(value)}


def _value(item: dict[str, Any], field: str, default: Any = None) -> Any:
    attribute = item.get(field)
    if attribute is None:
        return default
    if "S" in attribute:
        return attribute["S"]
    if "N" in attribute:
        return int(attribute["N"])
    raise HistoryStorageError("The stored history record has an invalid attribute.")


class CloudHistoryStore(HistoryStore):
    """HistoryStore-compatible adapter with atomic owner and shared quotas."""

    def __init__(
        self,
        bucket: str,
        table: str,
        region: str,
        *,
        s3_client: Any | None = None,
        dynamodb_client: Any | None = None,
    ) -> None:
        if not bucket or not table or not region:
            raise ValueError("Cloud history bucket, table, and region are required.")
        self.bucket = bucket
        self.table = table
        self.region = region
        if s3_client is None or dynamodb_client is None:
            import boto3  # Only needed in cloud mode; never at module import.

            session = boto3.session.Session(region_name=region)
            s3_client = s3_client or session.client("s3")
            dynamodb_client = dynamodb_client or session.client("dynamodb")
        self.s3 = s3_client
        self.ddb = dynamodb_client

    @classmethod
    def from_environment(cls) -> CloudHistoryStore:
        bucket = os.getenv("IOS_S3_BUCKET")
        table = os.getenv("IOS_DYNAMODB_TABLE")
        if not bucket or not table:
            raise ValueError(
                "Cloud History requires IOS_S3_BUCKET and IOS_DYNAMODB_TABLE."
            )
        return cls(
            bucket=bucket,
            table=table,
            region=os.getenv("IOS_AWS_REGION", "ap-south-1"),
        )

    @classmethod
    def _owner_pk(cls, owner_sub: str) -> str:
        owner_sub = cls._owner(owner_sub)
        return "OWNER#" + hashlib.sha256(owner_sub.encode("utf-8")).hexdigest()

    @staticmethod
    def _item_key(owner_pk: str, history_id: str) -> dict[str, dict[str, str]]:
        return {"pk": _s(owner_pk), "sk": _s(f"ITEM#{history_id}")}

    def _get_item(self, key: dict[str, Any]) -> dict[str, Any] | None:
        response = self.ddb.get_item(
            TableName=self.table, Key=key, ConsistentRead=True
        )
        return response.get("Item")

    def _counter(self, pk: str) -> dict[str, Any]:
        return self._get_item({"pk": _s(pk), "sk": _s("QUOTA")}) or {}

    def _owner_locked(self, owner_pk: str) -> bool:
        return _value(self._counter(owner_pk), "state") == "deleting"

    def quota(self, owner_sub: str) -> dict[str, int | bool]:
        owner_pk = self._owner_pk(owner_sub)
        try:
            owner = self._counter(owner_pk)
            shared = self._counter("GLOBAL")
            return {
                "used_items": _value(owner, "used_items", 0),
                "max_items": self.MAX_ITEMS_PER_OWNER,
                "used_bytes": _value(owner, "used_bytes", 0),
                "max_bytes": self.MAX_BYTES_PER_OWNER,
                "global_full": _value(shared, "used_bytes", 0) >= self.MAX_BYTES_GLOBAL,
            }
        except Exception as exc:
            if isinstance(exc, HistoryStorageError):
                raise
            raise HistoryStorageError("Could not read history quota.") from exc

    @staticmethod
    def _record(row: dict[str, Any]) -> dict[str, Any]:
        try:
            return {
                "history_id": _value(row, "history_id"),
                "filename": _value(row, "filename"),
                "mime_type": _value(row, "mime_type"),
                "byte_count": _value(row, "byte_count"),
                "original_sha256": _value(row, "sha256"),
                "created_at": _value(row, "created_at"),
                "expires_at": _value(row, "expires_at"),
                "status": _value(row, "state"),
                "requested_models": json.loads(_value(row, "requested_models_json")),
                "result": json.loads(_value(row, "result_json")),
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise HistoryStorageError("The stored history record is invalid.") from exc

    def _all_owner_rows(self, owner_pk: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        start_key: dict[str, Any] | None = None
        while True:
            params: dict[str, Any] = {
                "TableName": self.table,
                "KeyConditionExpression": "pk = :pk AND begins_with(sk, :prefix)",
                "ExpressionAttributeValues": {
                    ":pk": _s(owner_pk), ":prefix": _s("ITEM#")
                },
                "ConsistentRead": True,
            }
            if start_key:
                params["ExclusiveStartKey"] = start_key
            result = self.ddb.query(**params)
            rows.extend(result.get("Items", []))
            start_key = result.get("LastEvaluatedKey")
            if not start_key:
                return rows

    def _all_table_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        start_key: dict[str, Any] | None = None
        while True:
            params: dict[str, Any] = {"TableName": self.table, "ConsistentRead": True}
            if start_key:
                params["ExclusiveStartKey"] = start_key
            result = self.ddb.scan(**params)
            rows.extend(result.get("Items", []))
            start_key = result.get("LastEvaluatedKey")
            if not start_key:
                return rows

    @staticmethod
    def _quota_update(pk: str, *, item_delta: int, byte_delta: int,
                      max_items: int | None = None,
                      max_bytes: int | None = None) -> dict[str, Any]:
        values = {":zero": _n(0), ":item_delta": _n(item_delta),
                  ":byte_delta": _n(byte_delta)}
        names = {"#items": "used_items", "#bytes": "used_bytes"}
        update = (
            "SET #items = if_not_exists(#items, :zero) + :item_delta, "
            "#bytes = if_not_exists(#bytes, :zero) + :byte_delta"
        )
        if item_delta > 0:
            assert max_items is not None and max_bytes is not None
            values.update({":max_items": _n(max_items),
                           ":remaining_bytes": _n(max_bytes - byte_delta),
                           ":active": _s("active")})
            names["#state"] = "state"
            condition = (
                "(attribute_not_exists(#items) OR "
                "(#items < :max_items AND #bytes <= :remaining_bytes)) "
                "AND (attribute_not_exists(#state) OR #state = :active)"
            )
        else:
            values[":one"] = _n(1)
            values[":bytes"] = _n(-byte_delta)
            condition = "#items >= :one AND #bytes >= :bytes"
        return {
            "TableName": "",  # Set by caller.
            "Key": {"pk": _s(pk), "sk": _s("QUOTA")},
            "UpdateExpression": update,
            "ConditionExpression": condition,
            "ExpressionAttributeNames": names,
            "ExpressionAttributeValues": values,
        }

    def save(
        self,
        owner_sub: str,
        filename: str,
        mime_type: str | None,
        data: bytes,
        result: dict[str, Any],
        requested_models: list[str],
    ) -> dict[str, Any]:
        owner_pk = self._owner_pk(owner_sub)
        if not isinstance(data, bytes) or not data:
            raise InvalidHistoryRecord("The original image bytes are empty or invalid.")
        models_json = self._serialize_models(requested_models)
        result_json = self._serialize_result(result, data, requested_models)
        byte_count = len(data)
        if byte_count > min(self.MAX_BYTES_PER_OWNER, self.MAX_BYTES_GLOBAL):
            raise HistoryQuotaExceeded("The account history storage limit has been reached.")
        now = self._now()
        created_at = self._iso(now)
        expires_at = self._iso(now + timedelta(days=_EXPIRY_DAYS))
        history_id = uuid4().hex
        storage_key = f"originals/{uuid4().hex}.bin"
        sha256 = hashlib.sha256(data).hexdigest()
        row = {
            **self._item_key(owner_pk, history_id),
            "history_id": _s(history_id),
            "storage_key": _s(storage_key),
            "filename": _s(self._safe_filename(filename)),
            "mime_type": _s(self._safe_mime_type(mime_type)),
            "byte_count": _n(byte_count),
            "sha256": _s(sha256),
            "created_at": _s(created_at),
            "expires_at": _s(expires_at),
            "state": _s("active"),
            "requested_models_json": _s(models_json),
            "result_json": _s(result_json),
        }
        try:
            self.s3.put_object(
                Bucket=self.bucket, Key=storage_key, Body=data,
                ServerSideEncryption="AES256", IfNoneMatch="*",
            )
        except Exception as exc:
            raise HistoryStorageError("Could not store the private original.") from exc

        owner_update = self._quota_update(
            owner_pk, item_delta=1, byte_delta=byte_count,
            max_items=self.MAX_ITEMS_PER_OWNER, max_bytes=self.MAX_BYTES_PER_OWNER,
        )
        global_update = self._quota_update(
            "GLOBAL", item_delta=1, byte_delta=byte_count,
            max_items=2**31, max_bytes=self.MAX_BYTES_GLOBAL,
        )
        owner_update["TableName"] = global_update["TableName"] = self.table
        try:
            self.ddb.transact_write_items(ClientRequestToken=history_id,
                                          TransactItems=[
                {"Update": owner_update}, {"Update": global_update},
                {"Put": {
                    "TableName": self.table, "Item": row,
                    "ConditionExpression": "attribute_not_exists(pk)",
                }},
            ])
        except Exception as exc:
            # A timeout can occur after DynamoDB committed. Never delete the
            # original until a strongly consistent read confirms no record.
            try:
                committed = self._get_item(self._item_key(owner_pk, history_id))
            except Exception:
                committed = None
                outcome_unknown = True
            else:
                outcome_unknown = False
            if committed is not None:
                return self._record(committed)
            # A consistent read can still race a request whose response was
            # lost before DynamoDB finished. Only a definite transaction
            # cancellation proves that this S3 object cannot gain a row.
            error = getattr(exc, "response", {})
            cancelled = (
                isinstance(error, dict)
                and error.get("Error", {}).get("Code") == "TransactionCanceledException"
            )
            if not outcome_unknown and cancelled:
                try:
                    self.s3.delete_object(Bucket=self.bucket, Key=storage_key)
                except Exception:
                    # Sweep finds aged unreferenced objects if compensation fails.
                    pass
            try:
                quota = self.quota(owner_sub)
                global_bytes = _value(self._counter("GLOBAL"), "used_bytes", 0)
                if (quota["used_items"] >= self.MAX_ITEMS_PER_OWNER or
                    quota["used_bytes"] + byte_count > self.MAX_BYTES_PER_OWNER or
                    global_bytes + byte_count > self.MAX_BYTES_GLOBAL):
                    raise HistoryQuotaExceeded("History storage is full.") from exc
            except HistoryQuotaExceeded:
                raise
            except Exception:
                pass
            raise HistoryStorageError("Could not save the private history record.") from exc
        return self._record(row)

    def list(self, owner_sub: str, cursor: str | None = None,
             limit: int = 20) -> dict[str, Any]:
        owner_pk = self._owner_pk(owner_sub)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= _MAX_PAGE_SIZE:
            raise ValueError(f"History page size must be between 1 and {_MAX_PAGE_SIZE}.")
        cursor_values = self._decode_cursor(cursor) if cursor is not None else None
        try:
            if self._owner_locked(owner_pk):
                return {"items": [], "next_cursor": None, "quota": self.quota(owner_sub)}
            now = self._iso(self._now())
            rows = [row for row in self._all_owner_rows(owner_pk)
                    if _value(row, "state") == "active" and
                    _value(row, "expires_at") > now]
            rows.sort(key=lambda row: (_value(row, "created_at"),
                                       _value(row, "history_id")), reverse=True)
            if cursor_values:
                rows = [row for row in rows if
                        (_value(row, "created_at"), _value(row, "history_id")) < cursor_values]
            page = rows[:limit]
            next_cursor = self._encode_cursor(
                _value(page[-1], "created_at"), _value(page[-1], "history_id")
            ) if len(rows) > limit else None
            return {"items": [self._record(row) for row in page],
                    "next_cursor": next_cursor, "quota": self.quota(owner_sub)}
        except (ValueError, HistoryStorageError):
            raise
        except Exception as exc:
            raise HistoryStorageError("Could not list private history records.") from exc

    def _active_record(self, owner_sub: str, history_id: str) -> dict[str, Any]:
        owner_pk = self._owner_pk(owner_sub)
        if not isinstance(history_id, str) or not re.fullmatch(r"[0-9a-f]{32}", history_id):
            raise HistoryNotFound("The history record is unavailable.")
        try:
            if self._owner_locked(owner_pk):
                raise HistoryNotFound("The history record is unavailable.")
            row = self._get_item(self._item_key(owner_pk, history_id))
        except HistoryNotFound:
            raise
        except Exception as exc:
            raise HistoryStorageError("Could not read the private history record.") from exc
        if (not row or _value(row, "state") != "active" or
                _value(row, "expires_at") <= self._iso(self._now())):
            raise HistoryNotFound("The history record is unavailable.")
        return row

    def get(self, owner_sub: str, history_id: str) -> dict[str, Any]:
        return self._record(self._active_record(owner_sub, history_id))

    def read_original(self, owner_sub: str, history_id: str) -> bytes:
        row = self._active_record(owner_sub, history_id)
        try:
            response = self.s3.get_object(
                Bucket=self.bucket, Key=_value(row, "storage_key")
            )
            data = response["Body"].read()
        except Exception as exc:
            raise HistoryStorageError("The private original is temporarily unavailable.") from exc
        if (len(data) != _value(row, "byte_count") or
                hashlib.sha256(data).hexdigest() != _value(row, "sha256")):
            raise HistoryStorageError("The private original failed its integrity check.")
        return data

    def _mark_deleting(self, row: dict[str, Any]) -> dict[str, Any]:
        if _value(row, "state") == "deleting":
            return row
        try:
            self.ddb.update_item(
                TableName=self.table,
                Key={"pk": row["pk"], "sk": row["sk"]},
                UpdateExpression="SET #state = :deleting",
                ConditionExpression="#state = :active",
                ExpressionAttributeNames={"#state": "state"},
                ExpressionAttributeValues={
                    ":deleting": _s("deleting"), ":active": _s("active")
                },
            )
        except Exception as exc:
            # A concurrent delete may have finished; do not resurrect its row.
            try:
                current = self._get_item({"pk": row["pk"], "sk": row["sk"]})
            except Exception as read_exc:
                raise HistoryStorageError(
                    "Could not confirm the history deletion state."
                ) from read_exc
            if current is None:
                return row
            if _value(current, "state") != "deleting":
                raise HistoryStorageError("Could not mark the history record for deletion.") from exc
            return current
        return {**row, "state": _s("deleting")}

    def _remove_deleting(self, row: dict[str, Any]) -> None:
        key = _value(row, "storage_key")
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            raise HistoryStorageError("Deletion is pending and will be retried.") from exc
        byte_count = _value(row, "byte_count")
        owner_pk = _value(row, "pk")
        owner_update = self._quota_update(owner_pk, item_delta=-1,
                                          byte_delta=-byte_count)
        global_update = self._quota_update("GLOBAL", item_delta=-1,
                                           byte_delta=-byte_count)
        owner_update["TableName"] = global_update["TableName"] = self.table
        try:
            self.ddb.transact_write_items(TransactItems=[
                {"Delete": {
                    "TableName": self.table,
                    "Key": {"pk": row["pk"], "sk": row["sk"]},
                    "ConditionExpression": "#state = :deleting",
                    "ExpressionAttributeNames": {"#state": "state"},
                    "ExpressionAttributeValues": {":deleting": _s("deleting")},
                }},
                {"Update": owner_update}, {"Update": global_update},
            ])
        except Exception as exc:
            try:
                current = self._get_item({"pk": row["pk"], "sk": row["sk"]})
            except Exception as read_exc:
                raise HistoryStorageError(
                    "Deletion is pending and will be retried."
                ) from read_exc
            if current is not None:
                raise HistoryStorageError("Deletion is pending and will be retried.") from exc

    def delete(self, owner_sub: str, history_id: str) -> dict[str, bool]:
        owner_pk = self._owner_pk(owner_sub)
        if not isinstance(history_id, str) or not re.fullmatch(r"[0-9a-f]{32}", history_id):
            raise HistoryNotFound("The history record is unavailable.")
        try:
            row = self._get_item(self._item_key(owner_pk, history_id))
        except Exception as exc:
            raise HistoryStorageError("Could not read the private history record.") from exc
        if row is None:
            raise HistoryNotFound("The history record is unavailable.")
        row = self._mark_deleting(row)
        self._remove_deleting(row)
        return {"deleted": True, "pending": False}

    def _finish_account_deletion(self, owner_pk: str) -> bool:
        if self._all_owner_rows(owner_pk):
            return False
        self.ddb.update_item(
            TableName=self.table, Key={"pk": _s(owner_pk), "sk": _s("QUOTA")},
            UpdateExpression="REMOVE #state",
            ConditionExpression="#items = :zero AND #bytes = :zero AND #state = :deleting",
            ExpressionAttributeNames={"#state": "state", "#items": "used_items",
                                      "#bytes": "used_bytes"},
            ExpressionAttributeValues={":zero": _n(0), ":deleting": _s("deleting")},
        )
        return True

    def delete_account(self, owner_sub: str) -> dict[str, int | bool]:
        owner_pk = self._owner_pk(owner_sub)
        try:
            self.ddb.update_item(
                TableName=self.table,
                Key={"pk": _s(owner_pk), "sk": _s("QUOTA")},
                UpdateExpression="SET #state = :deleting, "
                                 "#items = if_not_exists(#items, :zero), "
                                 "#bytes = if_not_exists(#bytes, :zero)",
                ExpressionAttributeNames={"#state": "state", "#items": "used_items",
                                          "#bytes": "used_bytes"},
                ExpressionAttributeValues={":deleting": _s("deleting"),
                                           ":zero": _n(0)},
            )
            rows = self._all_owner_rows(owner_pk)
        except Exception as exc:
            raise HistoryStorageError("Could not start account history deletion.") from exc
        removed = 0
        pending = 0
        for row in rows:
            try:
                self._remove_deleting(self._mark_deleting(row))
                removed += 1
            except HistoryStorageError:
                pending += 1
        if pending == 0:
            try:
                self._finish_account_deletion(owner_pk)
            except Exception:
                pending += 1
        return {"deleted": removed, "pending": pending, "complete": pending == 0}

    def _remove_orphans(self, referenced: set[str]) -> int:
        removed = 0
        continuation: str | None = None
        # Leave a one-hour grace for S3 writes awaiting their Dynamo transaction.
        cutoff = self._now() - timedelta(hours=1)
        while True:
            params: dict[str, Any] = {"Bucket": self.bucket, "Prefix": "originals/"}
            if continuation:
                params["ContinuationToken"] = continuation
            response = self.s3.list_objects_v2(**params)
            for obj in response.get("Contents", []):
                key = obj["Key"]
                if (key not in referenced and
                        re.fullmatch(r"originals/[0-9a-f]{32}\.bin", key) and
                        obj["LastModified"] < cutoff):
                    try:
                        self.s3.delete_object(Bucket=self.bucket, Key=key)
                        removed += 1
                    except Exception:
                        pass
            if not response.get("IsTruncated"):
                return removed
            continuation = response["NextContinuationToken"]

    def sweep(self) -> dict[str, int]:
        try:
            rows = self._all_table_rows()
        except Exception as exc:
            raise HistoryStorageError("Could not start the history cleanup sweep.") from exc
        now = self._iso(self._now())
        expired = removed = pending = 0
        for row in rows:
            if not _value(row, "sk", "").startswith("ITEM#"):
                continue
            state = _value(row, "state")
            if state == "active" and _value(row, "expires_at") <= now:
                expired += 1
            elif state != "deleting":
                continue
            try:
                self._remove_deleting(self._mark_deleting(row))
                removed += 1
            except HistoryStorageError:
                pending += 1
        # Read a fresh snapshot: concurrent saves may have created new objects.
        try:
            fresh = self._all_table_rows()
            referenced = {_value(row, "storage_key") for row in fresh
                          if _value(row, "sk", "").startswith("ITEM#")}
            for row in fresh:
                if (_value(row, "sk") == "QUOTA" and
                        _value(row, "state") == "deleting"):
                    try:
                        self._finish_account_deletion(_value(row, "pk"))
                    except Exception:
                        pending += 1
            orphaned = self._remove_orphans(referenced)
        except Exception as exc:
            raise HistoryStorageError("Could not reconcile cloud history.") from exc
        return {"expired_marked": expired, "removed": removed,
                "pending": pending, "orphans_removed": orphaned}
