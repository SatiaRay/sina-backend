import time
from typing import List, Tuple

import pytest
from fastapi import Request
from jose import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from api.main import app


def generate_rsa_keypair() -> Tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


def _make_token(scopes: List[str], sub: str, nbf: float, exp: float, private_pem: str) -> str:
    claims = {
        "aud": "test-aud",
        "jti": "test-jti",
        "iat": nbf,
        "nbf": nbf,
        "exp": exp,
        "sub": sub,
        "scopes": scopes,
    }
    return jwt.encode(claims, private_pem, algorithm="RS256")


@pytest.fixture()
def rsa_keys():
    return generate_rsa_keypair()


@pytest.fixture()
def other_rsa_keys():
    return generate_rsa_keypair()


@pytest.fixture(autouse=True)
def set_public_key_env(monkeypatch, rsa_keys):
    _, public_pem = rsa_keys
    monkeypatch.setenv("OAUTH_TOKEN", public_pem)


def test_missing_token_returns_401(client):
    res = client.get("/health")
    assert res.status_code == 401
    assert res.json() == {"msg": "Missing token"}


def test_valid_token_allows_and_exposes_scopes_and_user(client, rsa_keys):
    @app.get("/whoami")
    def whoami(request: Request):
        return {
            "scopes": getattr(request.state, "scopes", []),
            "user_id": getattr(request.state, "user_id", None),
        }

    private_pem, _ = rsa_keys
    now = time.time()
    token = _make_token(["tenant_id:1"], sub="1", nbf=now - 10, exp=now + 3600, private_pem=private_pem)
    res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["scopes"] == ["tenant_id:1"]
    assert body["user_id"] == "1"


def test_token_not_yet_valid_returns_401(client, rsa_keys):
    private_pem, _ = rsa_keys
    now = time.time()
    token = _make_token(["tenant_id:1"], sub="1", nbf=now + 3600, exp=now + 7200, private_pem=private_pem)
    res = client.get("/health", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.json() == {"msg": "Unauthorized"}


def test_token_expired_returns_401(client, rsa_keys):
    private_pem, _ = rsa_keys
    now = time.time()
    token = _make_token(["tenant_id:1"], sub="1", nbf=now - 7200, exp=now - 10, private_pem=private_pem)
    res = client.get("/health", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.json() == {"msg": "Unauthorized"}


def test_invalid_signature_returns_401(client, other_rsa_keys):
    other_private_pem, _ = other_rsa_keys
    now = time.time()
    token = _make_token(["tenant_id:1"], sub="1", nbf=now - 10, exp=now + 3600, private_pem=other_private_pem)
    res = client.get("/health", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.json() == {"msg": "Unauthorized"}