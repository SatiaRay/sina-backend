import pytest
from unittest.mock import patch, mock_open, MagicMock
import json
import sys
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import time
from typing import List, Tuple
from api.main import app
from jose import jwt

# Add the project root to the path
root_dir = Path(__file__).parent.parent.parent
sys.path.append(str(root_dir))

from api.main import app
import api.system as system_mod

client = TestClient(app)

MOCK_SETTINGS = {"site_name": "TestBot", "text_agent_model": "mock-model-v1"}

MOCK_SCHEMA = {
    "type": "object",
    "properties": {
        "site_name": {"type": "string"},
        "text_agent_model": {"type": "string"},
    },
    "required": ["site_name", "text_agent_model"],
    "additionalProperties": False,
}

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
def patch_settings_schema(monkeypatch):
    # Patch the SYSTEM_SETTINGS_SCHEMA in the system module
    monkeypatch.setattr(system_mod, "SYSTEM_SETTINGS_SCHEMA", MOCK_SCHEMA)
    yield


@patch("api.system.get_dynamic_settings_schema", return_value=MOCK_SCHEMA)
@patch("api.system.open", new_callable=mock_open, read_data=json.dumps(MOCK_SETTINGS))
@patch("api.system.os.path.exists", return_value=True)
def test_post_system_settings_valid(mock_exists, mock_file, mock_schema, client, auth_headers):
    mock_settings = MagicMock()
    with patch("api.system.container.make", return_value=mock_settings):
        with patch.object(
            system_mod.config, "get", return_value=["mock-model-v1", "other-model"]
        ):
            response = client.post("/system/settings", json=MOCK_SETTINGS, headers=auth_headers)
            assert response.status_code == 200
            assert response.json()["message"] == "Settings updated successfully"
            mock_file.assert_called_with(
                system_mod.SYSTEM_SETTINGS_PATH, "w", encoding="utf-8"
            )
            handle = mock_file()
            handle.write.assert_called()  # Should write JSON


@patch("api.system.open", new_callable=mock_open, read_data=json.dumps(MOCK_SCHEMA))
def test_post_system_settings_invalid(mock_file, client, auth_headers):
    # Missing required field
    bad_settings = {"site_name": "TestBot"}
    response = client.post("/system/settings", json=bad_settings, headers=auth_headers)
    assert response.status_code == 400
    assert "Invalid settings" in response.json()["detail"]

    # Extra field
    bad_settings2 = {
        "site_name": "TestBot",
        "text_agent_model": "mock-model",
        "extra": 123,
    }
    response2 = client.post("/system/settings", json=bad_settings2, headers=auth_headers)
    assert response2.status_code == 400
    assert "Invalid settings" in response2.json()["detail"]


@patch("api.system.open", new_callable=mock_open, read_data=json.dumps(MOCK_SETTINGS))
def test_post_system_settings_invalid_model(mock_file, client, auth_headers):
    # text_agent_model not in allowed models
    bad_model_settings = {
        "site_name": "TestBot",
        "text_agent_model": "not-allowed-model",
    }
    mock_config = MagicMock()
    mock_config.get.return_value = ["mock-model-v1", "other-model"]
    with patch("api.system.config", mock_config):
        response = client.post("/system/settings", json=bad_model_settings, headers=auth_headers)
        assert response.status_code == 400
        assert "Invalid text_agent_model" in response.json()["detail"]
    # Also test with allowed model (should pass)
    good_model_settings = {"site_name": "TestBot", "text_agent_model": "mock-model-v1"}
    mock_config2 = MagicMock()
    mock_config2.get.return_value = ["mock-model-v1", "other-model"]
    with patch("api.system.config", mock_config2):
        response = client.post("/system/settings", json=good_model_settings, headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Settings updated successfully"


def test_get_config_schema(client, auth_headers):
    mock_config = MagicMock()
    mock_config.get.return_value = ["model-a", "model-b"]
    with patch("api.system.config", mock_config):
        response = client.get("/system/settings-schema", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "schema" in data
        assert "allowed_text_models" in data
        assert data["schema"] == system_mod.SYSTEM_SETTINGS_SCHEMA
        assert data["allowed_text_models"] == ["model-a", "model-b"]
