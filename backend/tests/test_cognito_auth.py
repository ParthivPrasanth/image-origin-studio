"""Cognito access-token validation stays separate from localhost test sign-in."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException, Request

from app import auth


def request(token: str | None = None) -> Request:
    headers = [(b"host", b"example.test")]
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    return Request({
        "type": "http",
        "method": "GET",
        "scheme": "https",
        "path": "/api/history",
        "query_string": b"",
        "headers": headers,
        "client": ("192.0.2.10", 40500),
        "server": ("example.test", 443),
    })


@pytest.fixture
def cognito(monkeypatch):
    monkeypatch.setenv("IOS_COGNITO_REGION", "ap-south-1")
    monkeypatch.setenv("IOS_COGNITO_USER_POOL_ID", "ap-south-1_test123")
    monkeypatch.setenv("IOS_COGNITO_CLIENT_ID", "client123")
    monkeypatch.setenv(
        "IOS_COGNITO_DOMAIN", "https://demo.auth.ap-south-1.amazoncognito.com"
    )
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    client = SimpleNamespace(
        get_signing_key_from_jwt=lambda _token: SimpleNamespace(
            key=private_key.public_key()
        )
    )
    monkeypatch.setattr(auth, "_cognito_jwks_client", lambda _issuer: client)
    return private_key


def token(private_key, **updates):
    now = datetime.now(timezone.utc)
    claims = {
        "iss": "https://cognito-idp.ap-south-1.amazonaws.com/ap-south-1_test123",
        "sub": "person-123",
        "client_id": "client123",
        "token_use": "access",
        "iat": now,
        "exp": now + timedelta(minutes=30),
    }
    claims.update(updates)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test"})


def test_valid_cognito_access_token_is_bound_to_pool_and_client(cognito):
    assert auth.optional_identity(request()) is None
    assert auth.optional_identity(request(token(cognito))).sub == "person-123"


@pytest.mark.parametrize(
    "changed",
    [
        {"client_id": "other-client"},
        {"token_use": "id"},
        {"iss": "https://cognito-idp.ap-south-1.amazonaws.com/ap-south-1_other"},
        {"sub": ""},
        {"exp": datetime(2000, 1, 1, tzinfo=timezone.utc)},
    ],
)
def test_wrong_claims_are_rejected(cognito, changed):
    with pytest.raises(HTTPException) as error:
        auth.optional_identity(request(token(cognito, **changed)))
    assert error.value.status_code == 401


def test_wrong_signature_is_rejected(cognito):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(HTTPException) as error:
        auth.optional_identity(request(token(other_key)))
    assert error.value.status_code == 401


def test_jwks_network_failure_is_temporary_unavailability(cognito, monkeypatch):
    def fail(_issuer):
        raise jwt.PyJWKClientConnectionError("network unavailable")

    monkeypatch.setattr(auth, "_cognito_jwks_client", fail)
    with pytest.raises(HTTPException) as error:
        auth.optional_identity(request(token(cognito)))
    assert error.value.status_code == 503
    assert "network" not in error.value.detail


def test_public_cognito_mode_disables_disposable_local_test_auth(cognito, monkeypatch):
    monkeypatch.setenv("IOS_LOCAL_TEST_AUTH", "1")
    assert auth.local_test_available(request()) is False
    with pytest.raises(HTTPException) as error:
        auth.issue_local_token(request(), "alice")
    assert error.value.status_code == 404


def test_partial_or_invalid_cognito_configuration_fails_closed(monkeypatch):
    monkeypatch.setenv("IOS_COGNITO_REGION", "ap-south-1")
    with pytest.raises(RuntimeError, match="incomplete"):
        auth.cognito_config()
    monkeypatch.setenv("IOS_COGNITO_USER_POOL_ID", "ap-south-1_test123")
    monkeypatch.setenv("IOS_COGNITO_CLIENT_ID", "client123")
    monkeypatch.setenv("IOS_COGNITO_DOMAIN", "http://localhost:3000")
    with pytest.raises(RuntimeError, match="invalid"):
        auth.cognito_config()
