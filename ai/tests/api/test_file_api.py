import os
import io
import shutil
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from src.api.main import app
import time
from typing import List, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

client = TestClient(app)
UPLOAD_DIR = os.path.join(os.getcwd(), "uploaded_files")

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


@pytest.fixture(autouse=True)
def set_public_key_env(monkeypatch, rsa_keys):
    _, public_pem = rsa_keys
    monkeypatch.setenv("OAUTH_PUBLIC_KEY", public_pem)


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def auth_headers(rsa_keys):
    private_pem, _ = rsa_keys
    now = time.time()
    token = _make_token(["tenant_id:1"], sub="1", nbf=now - 10, exp=now + 3600, private_pem=private_pem)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def cleanup_upload_dir():
    # Ensure upload dir exists before test
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    yield
    # Remove all files after test
    shutil.rmtree(UPLOAD_DIR, ignore_errors=True)


def test_upload_single_file(client, auth_headers):
    file_content = b"hello world"
    files = {"files": ("test.txt", io.BytesIO(file_content), "text/plain")}
    response = client.post("/files/upload", files=files, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "files" in data
    assert len(data["files"]) == 1
    uploaded = data["files"][0]
    assert uploaded["filename"] == "test.txt"
    assert uploaded["url"].startswith("/files/")
    # Check file physically exists
    assert os.path.exists(uploaded["storage_path"])
    with open(uploaded["storage_path"], "rb") as f:
        assert f.read() == file_content


def test_upload_multiple_files(client, auth_headers):
    files = [
        ("files", ("a.txt", io.BytesIO(b"A"), "text/plain")),
        ("files", ("b.txt", io.BytesIO(b"B"), "text/plain")),
    ]
    response = client.post("/files/upload", files=files, headers=auth_headers)
    print(response.text)
    assert response.status_code == 200
    data = response.json()
    assert "files" in data
    assert len(data["files"]) == 2
    names = {f["filename"] for f in data["files"]}
    assert names == {"a.txt", "b.txt"}
    for uploaded in data["files"]:
        assert os.path.exists(uploaded["storage_path"])


def test_get_uploaded_file(client, auth_headers):
    # Upload a file first
    file_content = b"download me"
    files = {"files": ("download.txt", io.BytesIO(file_content), "text/plain")}
    upload_resp = client.post("/files/upload", files=files, headers=auth_headers)
    assert upload_resp.status_code == 200
    file_url = upload_resp.json()["files"][0]["url"]
    filename = file_url.split("/")[-1]
    # Download the file
    resp = client.get(f"/files/{filename}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.content == file_content
    assert resp.headers["content-type"].startswith(
        "application/octet-stream"
    ) or resp.headers["content-type"].startswith("text/plain")


def test_get_file_not_found(client, auth_headers):
    resp = client.get("/files/nonexistentfile.txt", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "File not found"
