"""API checks for opt-in private history and local test identity."""

from __future__ import annotations

import hashlib
import shutil
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import auth
from app import main
from app.history import HistoryStorageError
from app.model import Scores


class FakeDetector:
    def predict(self, data: bytes) -> Scores:
        return Scores(label="fake", fake=0.8, real=0.2)


class BrokenDetector:
    def predict(self, data: bytes) -> Scores:
        raise RuntimeError("private details")


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 12), "navy").save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def local_root():
    base = (Path(__file__).resolve().parents[2] / ".local").resolve()
    base.mkdir(exist_ok=True)
    root = (base / f"history-api-test-{uuid4().hex}").resolve()
    assert root.parent == base
    try:
        yield root
    finally:
        if root.exists() and root.parent == base:
            shutil.rmtree(root)


def client(monkeypatch, local_root) -> TestClient:
    monkeypatch.setenv("IOS_LOCAL_TEST_AUTH", "1")
    monkeypatch.setenv("IOS_HISTORY_ROOT", str(local_root / "history"))
    monkeypatch.setattr(main, "get_e2_detector", lambda: FakeDetector())
    monkeypatch.setattr(main, "get_detector", lambda: FakeDetector())
    return TestClient(
        main.app, base_url="http://localhost", client=("127.0.0.1", 41234)
    )


def sign_in(http: TestClient, user: str) -> str:
    response = http.post("/api/auth/local-test", json={"test_user": user})
    assert response.status_code == 200
    return response.json()["access_token"]


def compare(http: TestClient, token: str | None = None, save: bool = False):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return http.post(
        "/api/analyze/compare",
        data={"models": ["v3_e2", "community_forensics"],
              "save_to_history": str(save).lower()},
        files={"file": ("image.png", image_bytes(), "image/png")},
        headers=headers,
    )


def test_guest_and_signed_in_unsaved_leave_no_history(monkeypatch, local_root):
    http = client(monkeypatch, local_root)
    guest = compare(http)
    assert guest.status_code == 200
    assert guest.json()["history"] is None
    assert not (local_root / "history").exists()
    token = sign_in(http, "alice")
    unsaved = compare(http, token)
    assert unsaved.status_code == 200
    listing = http.get("/api/history", headers={"Authorization": f"Bearer {token}"})
    assert listing.status_code == 200
    assert listing.json()["items"] == []


def test_save_original_ownership_and_delete(monkeypatch, local_root):
    http = client(monkeypatch, local_root)
    alice = sign_in(http, "alice")
    bob = sign_in(http, "bob")
    no_auth = compare(http, save=True)
    assert no_auth.status_code == 401
    saved = compare(http, alice, save=True)
    assert saved.status_code == 200
    assert saved.json()["history"]["status"] == "saved"
    history_id = saved.json()["history"]["history_id"]
    headers = {"Authorization": f"Bearer {alice}"}
    item = http.get(f"/api/history/{history_id}", headers=headers)
    assert item.status_code == 200
    assert item.json()["result"]["models"] == saved.json()["models"]
    original = http.get(f"/api/history/{history_id}/original", headers=headers)
    assert original.status_code == 200
    assert original.content == image_bytes()
    assert original.headers["cache-control"] == "no-store"
    assert hashlib.sha256(original.content).hexdigest() == item.json()["original_sha256"]
    bob_headers = {"Authorization": f"Bearer {bob}"}
    assert http.get(f"/api/history/{history_id}", headers=bob_headers).status_code == 404
    assert http.get(f"/api/history/{history_id}/original", headers=bob_headers).status_code == 404
    assert http.delete(f"/api/history/{history_id}", headers=bob_headers).status_code == 404
    assert http.delete(f"/api/history/{history_id}", headers=headers).status_code == 200
    assert http.get(f"/api/history/{history_id}", headers=headers).status_code == 404


def test_partial_success_saved_and_all_failure_not_saved(monkeypatch, local_root):
    http = client(monkeypatch, local_root)
    token = sign_in(http, "alice")
    monkeypatch.setattr(main, "get_detector", lambda: BrokenDetector())
    partial = compare(http, token, save=True).json()
    assert partial["history"]["status"] == "saved"
    assert [model["status"] for model in partial["models"]] == ["success", "error"]
    monkeypatch.setattr(main, "get_e2_detector", lambda: BrokenDetector())
    failed = compare(http, token, save=True).json()
    assert failed["history"]["status"] == "not_saved"
    assert failed["history"]["reason"] == "No model succeeded."


def test_storage_failure_preserves_analysis(monkeypatch, local_root):
    http = client(monkeypatch, local_root)
    token = sign_in(http, "alice")

    class FailingStore:
        def save(self, *_args):
            raise HistoryStorageError("private storage detail")

    monkeypatch.setattr(main, "history_store", lambda: FailingStore())
    response = compare(http, token, save=True)
    assert response.status_code == 200
    body = response.json()
    assert all(model["status"] == "success" for model in body["models"])
    assert body["history"]["status"] == "not_saved"
    assert "private storage detail" not in body["history"]["reason"]


def test_failed_delete_returns_pending_and_hides_item(monkeypatch, local_root):
    http = client(monkeypatch, local_root)
    token = sign_in(http, "alice")
    history_id = compare(http, token, save=True).json()["history"]["history_id"]
    store = main.history_store()
    remove = store._remove_deleting

    def fail_remove(_row):
        raise HistoryStorageError("transient file failure")

    monkeypatch.setattr(store, "_remove_deleting", fail_remove)
    headers = {"Authorization": f"Bearer {token}"}
    deletion = http.delete(f"/api/history/{history_id}", headers=headers)
    assert deletion.status_code == 202
    assert deletion.json() == {"deleted": False, "pending": True}
    assert http.get(f"/api/history/{history_id}", headers=headers).status_code == 404
    monkeypatch.setattr(store, "_remove_deleting", remove)
    assert store.sweep()["removed"] == 1


def test_invalid_token_and_disabled_local_sign_in(monkeypatch, local_root):
    http = client(monkeypatch, local_root)
    token = sign_in(http, "alice")
    assert compare(http, token + "tampered").status_code == 401
    issued_at = auth.time.time()
    monkeypatch.setattr(auth.time, "time", lambda: issued_at + 7200)
    assert compare(http, token, save=True).status_code == 401
    monkeypatch.delenv("IOS_LOCAL_TEST_AUTH")
    assert http.post("/api/auth/local-test", json={"test_user": "alice"}).status_code == 404
    assert compare(http, token, save=True).status_code == 401
