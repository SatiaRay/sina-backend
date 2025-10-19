import time
from typing import List, Tuple

import pytest
from jose import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
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

def test_get_functions_map_success(client, auth_headers):
    """Test successful retrieval of functions map"""
    response = client.get("/ai-functions/map", headers=auth_headers)
    
    assert response.status_code == 200
    
    # Verify response structure
    data = response.json()
    assert "functions" in data
    assert isinstance(data["functions"], list)
    
    # Verify first function structure if exists
    if data["functions"]:
        first_function = data["functions"][0]
        assert "type" in first_function
        assert "name" in first_function
        assert "description" in first_function
        assert "parameters" in first_function

def test_get_functions_map_file_not_found(monkeypatch, client, auth_headers):
    """Test error handling when map file is not found"""
    def mock_open(*args, **kwargs):
        raise FileNotFoundError("Map file not found")
    
    # Mock the open function to simulate file not found
    monkeypatch.setattr("builtins.open", mock_open)
    
    response = client.get("/ai-functions/map", headers=auth_headers)
    
    assert response.status_code == 500
    assert "Error loading functions map" in response.json()["detail"]

def test_get_functions_map_invalid_json(monkeypatch, client, auth_headers):
    """Test error handling when map file contains invalid JSON"""
    def mock_open(*args, **kwargs):
        class MockFile:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                return "invalid json content"
        return MockFile()
    
    # Mock the open function to return invalid JSON
    monkeypatch.setattr("builtins.open", mock_open)
    
    response = client.get("/ai-functions/map", headers=auth_headers)
    
    assert response.status_code == 500
    assert "Error loading functions map" in response.json()["detail"] 