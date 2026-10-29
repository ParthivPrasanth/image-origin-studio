"""A hosted sign-in must never silently use local original-file storage."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _cognito(monkeypatch):
    monkeypatch.setenv("IOS_COGNITO_REGION", "ap-south-1")
    monkeypatch.setenv("IOS_COGNITO_USER_POOL_ID", "ap-south-1_Example")
    monkeypatch.setenv("IOS_COGNITO_CLIENT_ID", "publicclient123")
    monkeypatch.setenv("IOS_COGNITO_DOMAIN", "https://example.auth.ap-south-1.amazoncognito.com")


def test_hosted_sign_in_refuses_local_history(monkeypatch):
    _cognito(monkeypatch)
    monkeypatch.setenv("IOS_HISTORY_BACKEND", "local")
    with pytest.raises(RuntimeError, match="configured together"):
        with TestClient(app):
            pass


def test_cloud_history_refuses_missing_hosted_identity(monkeypatch):
    monkeypatch.setenv("IOS_HISTORY_BACKEND", "aws")
    for key in (
        "IOS_COGNITO_REGION", "IOS_COGNITO_USER_POOL_ID",
        "IOS_COGNITO_CLIENT_ID", "IOS_COGNITO_DOMAIN",
    ):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match="configured together"):
        with TestClient(app):
            pass
