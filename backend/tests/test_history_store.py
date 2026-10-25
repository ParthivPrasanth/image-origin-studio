from __future__ import annotations

import hashlib
import re
import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app.history import (
    HistoryNotFound,
    HistoryQuotaExceeded,
    HistoryStorageError,
    HistoryStore,
    InvalidHistoryRecord,
)


@pytest.fixture
def history_test_root():
    project_root = Path(__file__).resolve().parents[2]
    local_root = (project_root / ".local").resolve()
    root = local_root / f"history-tests-{uuid4().hex}"
    if root.resolve().parent != local_root:
        raise RuntimeError("History test directory escaped the ignored workspace folder.")
    root.mkdir()
    try:
        yield root
    finally:
        if root.resolve().parent != local_root:
            raise RuntimeError("History test cleanup target escaped the ignored workspace folder.")
        shutil.rmtree(root)


class SmallHistoryStore(HistoryStore):
    MAX_ITEMS_PER_OWNER = 3
    MAX_BYTES_PER_OWNER = 10
    MAX_BYTES_GLOBAL = 15


def result_for(data: bytes, *, success: bool = True) -> dict:
    models = [
        {
            "model_key": "v3_e2",
            "status": "success" if success else "error",
            "prediction": "fake" if success else None,
            "error": None if success else "could not process",
            "model_revision": "locked-revision",
        }
    ]
    return {
        "image_format": "PNG",
        "input": {"sha256": hashlib.sha256(data).hexdigest(), "width": 16, "height": 16},
        "analyzed_at": "2026-10-25T12:00:00+00:00",
        "models": models,
    }


def save(store: HistoryStore, owner: str, data: bytes = b"original") -> dict:
    return store.save(
        owner,
        r"C:\private\image.png",
        "image/png",
        data,
        result_for(data),
        ["v3_e2"],
    )


def test_save_keeps_exact_original_and_snapshot_without_exposing_storage_path(history_test_root):
    store = HistoryStore(history_test_root / "history")
    original = b"exact uploaded bytes, including metadata"
    snapshot = result_for(original)

    record = store.save(
        "owner-1", r"C:\private\photo.png", "image/png", original,
        snapshot, ["v3_e2"],
    )

    assert record["filename"] == "photo.png"
    assert record["mime_type"] == "image/png"
    assert record["original_sha256"] == hashlib.sha256(original).hexdigest()
    assert record["byte_count"] == len(original)
    assert record["result"] == snapshot
    assert record["requested_models"] == ["v3_e2"]
    assert datetime.fromisoformat(record["expires_at"]) - datetime.fromisoformat(
        record["created_at"]
    ) == timedelta(days=30)
    assert record["status"] == "active"
    assert store.read_original("owner-1", record["history_id"]) == original
    assert store.get("owner-1", record["history_id"])["result"] == snapshot
    assert "storage_key" not in record and "path" not in record
    object_files = list((history_test_root / "history" / "originals").iterdir())
    assert len(object_files) == 1
    assert re.fullmatch(r"[0-9a-f]{64}\.bin", object_files[0].name)
    assert object_files[0].read_bytes() == original


def test_ownership_checks_hide_other_users_records(history_test_root):
    store = HistoryStore(history_test_root / "history")
    record = save(store, "owner-1")

    assert store.list("owner-2")["items"] == []
    with pytest.raises(HistoryNotFound):
        store.get("owner-2", record["history_id"])
    with pytest.raises(HistoryNotFound):
        store.read_original("owner-2", record["history_id"])
    with pytest.raises(HistoryNotFound):
        store.delete("owner-2", record["history_id"])
    assert store.read_original("owner-1", record["history_id"]) == b"original"


def test_list_is_newest_first_paginated_and_includes_quota(history_test_root):
    store = SmallHistoryStore(history_test_root / "history")
    records = [save(store, "owner-1", bytes([index])) for index in range(1, 4)]

    first = store.list("owner-1", limit=2)
    second = store.list("owner-1", cursor=first["next_cursor"], limit=2)

    returned = first["items"] + second["items"]
    assert {record["history_id"] for record in returned} == {
        record["history_id"] for record in records
    }
    assert len({record["history_id"] for record in returned}) == 3
    assert [item["created_at"] for item in first["items"]] == sorted(
        (item["created_at"] for item in first["items"]), reverse=True
    )
    assert first["next_cursor"] is not None
    assert second["next_cursor"] is None
    assert first["quota"] == {
        "used_items": 3,
        "max_items": 3,
        "used_bytes": 3,
        "max_bytes": 10,
        "global_full": False,
    }


def test_owner_and_global_quotas_reject_saves_without_partial_files(history_test_root):
    store = SmallHistoryStore(history_test_root / "history")
    save(store, "owner-1", b"123456")
    with pytest.raises(HistoryQuotaExceeded):
        save(store, "owner-1", b"12345")
    # Cross-owner storage still shares one atomic cap.
    save(store, "owner-2", b"123456789")
    before = set((history_test_root / "history" / "originals").iterdir())
    with pytest.raises(HistoryQuotaExceeded):
        save(store, "owner-3", b"x")
    after = set((history_test_root / "history" / "originals").iterdir())
    assert after == before
    quota = store.list("owner-1")["quota"]
    assert quota["used_items"] == 1
    assert quota["used_bytes"] == 6
    assert quota["global_full"] is True


def test_item_limit_and_snapshot_validation(history_test_root):
    store = SmallHistoryStore(history_test_root / "history")
    for index in range(3):
        save(store, "owner-1", bytes([index + 1]))
    with pytest.raises(HistoryQuotaExceeded):
        save(store, "owner-1", b"x")

    data = b"valid"
    with pytest.raises(InvalidHistoryRecord):
        store.save("owner-2", "x.png", "image/png", data, result_for(data, success=False), ["v3_e2"])
    mismatched = result_for(data)
    mismatched["input"]["sha256"] = "0" * 64
    with pytest.raises(InvalidHistoryRecord):
        store.save("owner-2", "x.png", "image/png", data, mismatched, ["v3_e2"])


def test_expiry_blocks_read_before_sweep_and_sweep_removes_record(history_test_root):
    store = HistoryStore(history_test_root / "history")
    record = save(store, "owner-1")
    with closing(sqlite3.connect(store.database_path)) as connection:
        expired_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(
            timespec="microseconds"
        )
        connection.execute(
            "UPDATE history_records SET expires_at = ? WHERE id = ?",
            (expired_at, record["history_id"]),
        )
        connection.commit()

    with pytest.raises(HistoryNotFound):
        store.get("owner-1", record["history_id"])
    with pytest.raises(HistoryNotFound):
        store.read_original("owner-1", record["history_id"])
    report = store.sweep()
    assert report["expired_marked"] == 1
    assert report["removed"] == 1
    assert store.list("owner-1")["items"] == []
    assert list((history_test_root / "history" / "originals").iterdir()) == []


def test_delete_hides_record_immediately_and_sweep_retries_pending_delete(history_test_root, monkeypatch):
    store = HistoryStore(history_test_root / "history")
    record = save(store, "owner-1")
    remove = store._remove_deleting

    def fail_remove(_row):
        raise HistoryStorageError("simulated transient failure")

    monkeypatch.setattr(store, "_remove_deleting", fail_remove)
    with pytest.raises(HistoryStorageError):
        store.delete("owner-1", record["history_id"])
    with pytest.raises(HistoryNotFound):
        store.get("owner-1", record["history_id"])

    monkeypatch.setattr(store, "_remove_deleting", remove)
    report = store.sweep()
    assert report["removed"] == 1
    assert report["pending"] == 0
    assert store.list("owner-1")["items"] == []


def test_account_deletion_and_orphan_reconciliation(history_test_root):
    store = HistoryStore(history_test_root / "history")
    first = save(store, "owner-1", b"first")
    second = save(store, "owner-1", b"second")
    save(store, "owner-2", b"keep")
    orphan = store.originals_dir / ("a" * 64 + ".bin")
    orphan.write_bytes(b"orphan")

    deletion = store.delete_account("owner-1")
    assert deletion == {"deleted": 2, "pending": 0, "complete": True}
    with pytest.raises(HistoryNotFound):
        store.get("owner-1", first["history_id"])
    with pytest.raises(HistoryNotFound):
        store.get("owner-1", second["history_id"])
    assert len(store.list("owner-2")["items"]) == 1
    report = store.sweep()
    assert report["orphans_removed"] == 1
    assert not orphan.exists()


def test_concurrent_saves_cannot_exceed_global_byte_cap(history_test_root):
    class TinyGlobalStore(HistoryStore):
        MAX_ITEMS_PER_OWNER = 10
        MAX_BYTES_PER_OWNER = 20
        MAX_BYTES_GLOBAL = 5

    root = history_test_root / "history"
    stores = [TinyGlobalStore(root), TinyGlobalStore(root)]

    def attempt(index: int) -> str:
        try:
            save(stores[index], f"owner-{index}", b"1234")
            return "saved"
        except HistoryQuotaExceeded:
            return "quota"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(attempt, range(2)))

    assert sorted(outcomes) == ["quota", "saved"]
    assert len(stores[0].list("owner-0")["items"]) + len(
        stores[1].list("owner-1")["items"]
    ) == 1
