"""Fail-closed local test identity for the private-history development slice.

Production identity is deliberately unavailable until a managed provider is
configured and its token verification is implemented during AWS readiness.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request

_ISSUER = "image-origin-studio-local-test"
_AUDIENCE = "image-origin-studio-local"
_SECRET = secrets.token_bytes(32)


@dataclass(frozen=True)
class Identity:
    sub: str


def local_test_enabled() -> bool:
    return os.getenv("IOS_LOCAL_TEST_AUTH") == "1"


def _local_request(request: Request) -> bool:
    try:
        address = ipaddress.ip_address(request.client.host if request.client else "")
    except ValueError:
        return False
    host = request.headers.get("host", "").split(":", 1)[0].lower()
    return address.is_loopback and host in {"localhost", "127.0.0.1", "[::1]"}


def local_test_available(request: Request) -> bool:
    return local_test_enabled() and _local_request(request)


def _encode(value: dict[str, object]) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _decode(value: str) -> dict[str, object]:
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("Expected object")
    return result


def issue_local_token(request: Request, test_user: str) -> str:
    if not local_test_available(request):
        raise HTTPException(status_code=404, detail="Local test sign-in is unavailable.")
    if test_user not in {"alice", "bob"}:
        raise HTTPException(status_code=422, detail="Choose a local test identity.")
    now = int(time.time())
    header = _encode({"alg": "HS256", "typ": "JWT"})
    payload = _encode({
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "sub": f"local-test:{test_user}",
        "token_use": "access",
        "iat": now,
        "nbf": now,
        "exp": now + 3600,
    })
    signed = f"{header}.{payload}"
    signature = hmac.new(_SECRET, signed.encode(), hashlib.sha256).digest()
    return signed + "." + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()


def optional_identity(request: Request) -> Identity | None:
    authorization = request.headers.get("authorization")
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization header.")
    if not local_test_available(request):
        raise HTTPException(status_code=401, detail="Sign-in is unavailable in this build.")
    try:
        header_part, payload_part, signature_part = token.split(".")
        header = _decode(header_part)
        payload = _decode(payload_part)
        signed = f"{header_part}.{payload_part}"
        expected = hmac.new(_SECRET, signed.encode(), hashlib.sha256).digest()
        supplied = base64.urlsafe_b64decode(
            signature_part + "=" * (-len(signature_part) % 4)
        )
        now = int(time.time())
        valid = (
            header == {"alg": "HS256", "typ": "JWT"}
            and hmac.compare_digest(supplied, expected)
            and payload.get("iss") == _ISSUER
            and payload.get("aud") == _AUDIENCE
            and payload.get("token_use") == "access"
            and isinstance(payload.get("sub"), str)
            and payload["sub"] in {"local-test:alice", "local-test:bob"}
            and isinstance(payload.get("exp"), int)
            and isinstance(payload.get("nbf"), int)
            and payload["nbf"] <= now < payload["exp"]
        )
        if not valid:
            raise ValueError("Invalid claims")
    except (ValueError, KeyError, TypeError, binascii.Error):
        raise HTTPException(status_code=401, detail="Invalid or expired sign-in.") from None
    return Identity(sub=payload["sub"])


def required_identity(request: Request) -> Identity:
    identity = optional_identity(request)
    if identity is None:
        raise HTTPException(status_code=401, detail="Sign in to use history.")
    return identity
