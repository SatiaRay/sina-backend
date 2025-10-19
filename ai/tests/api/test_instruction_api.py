import pytest
from api.main import app
import time
from typing import List, Tuple
import pytest
from jose import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

TEST_INSTRUCTION = {
    "label": "Test Instruction",
    "text": "This is a test instruction",
    "status": True,
    "agent_type": "text_agent",
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


@pytest.fixture(scope="function")
def test_instruction(client, auth_headers):
    response = client.post("/instructions/", json=TEST_INSTRUCTION, headers=auth_headers)
    assert response.status_code == 200
    return response.json()


def test_create_instruction(client, auth_headers):
    response = client.post("/instructions/", json=TEST_INSTRUCTION, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == TEST_INSTRUCTION["label"]
    assert data["text"] == TEST_INSTRUCTION["text"]
    assert data["status"] == TEST_INSTRUCTION["status"]
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_get_instructions(client, auth_headers):
    # Insert at least one instruction
    response = client.post("/instructions/", json=TEST_INSTRUCTION, headers=auth_headers)
    assert response.status_code == 200
    response = client.get("/instructions/?agent_type=text_agent", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert "pages" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) > 0


def test_get_instructions_active_only(client, auth_headers):
    response = client.post("/instructions/", json=TEST_INSTRUCTION, headers=auth_headers)
    assert response.status_code == 200
    response = client.get("/instructions/?active_only=true&agent_type=text_agent", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert "pages" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) > 0
    for instruction in data["items"]:
        assert instruction["status"] is True
        assert instruction["text"] == TEST_INSTRUCTION["text"]


def test_get_instructions_pagination(client, auth_headers):
    for i in range(15):
        test_data = TEST_INSTRUCTION.copy()
        test_data["label"] = f"Test Instruction {i}"
        response = client.post("/instructions/", json=test_data, headers=auth_headers)
        assert response.status_code == 200
    response = client.get("/instructions/?page=1&size=10&agent_type=text_agent", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10
    assert data["page"] == 1
    assert data["size"] == 10
    assert data["total"] >= 15
    assert data["pages"] >= 2
    response = client.get("/instructions/?page=2&size=10&agent_type=text_agent", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 0
    assert data["page"] == 2
    assert data["size"] == 10


def test_get_instruction(client, test_instruction, auth_headers):
    response = client.get(f"/instructions/{test_instruction['id']}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_instruction["id"]
    assert data["label"] == test_instruction["label"]
    assert data["text"] == test_instruction["text"]


def test_get_nonexistent_instruction(client, auth_headers):
    response = client.get("/instructions/99999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"


def test_update_instruction(client, test_instruction, auth_headers):
    update_data = {
        "label": "Updated Label",
        "text": "Updated text",
        "status": False,
        "agent_type": "text_agent",
    }
    response = client.put(f"/instructions/{test_instruction['id']}", json=update_data, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == update_data["label"]
    assert data["text"] == update_data["text"]
    assert data["status"] == update_data["status"]


def test_update_nonexistent_instruction(client, auth_headers):
    update_data = {
        "label": "Updated Label",
        "text": "Updated text",
        "status": False,
        "agent_type": "text_agent",
    }
    response = client.put("/instructions/99999", json=update_data, headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"


def test_delete_instruction(client, test_instruction, auth_headers):
    response = client.delete(f"/instructions/{test_instruction['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Instruction deleted successfully"
    get_response = client.get(f"/instructions/{test_instruction['id']}", headers=auth_headers)
    assert get_response.status_code == 404


def test_delete_nonexistent_instruction(client, auth_headers):
    response = client.delete("/instructions/99999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"


def test_enable_instruction(client, test_instruction, auth_headers):
    # First disable the instruction
    response = client.patch(f"/instructions/{test_instruction['id']}/disable", headers=auth_headers)
    assert response.status_code == 200
    # Then enable it
    response = client.patch(f"/instructions/{test_instruction['id']}/enable", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is True


def test_disable_instruction(client, test_instruction, auth_headers):
    response = client.patch(f"/instructions/{test_instruction['id']}/disable", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is False


def test_enable_nonexistent_instruction(client, auth_headers):
    response = client.patch("/instructions/99999/enable", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"


def test_disable_nonexistent_instruction(client, auth_headers):
    response = client.patch("/instructions/99999/disable", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"


def test_create_instruction_validation(client, auth_headers):
    invalid_data = {"label": "Test Label"}  # Missing text field
    response = client.post("/instructions/", json=invalid_data, headers=auth_headers)
    assert response.status_code == 422
    invalid_data = {"label": "", "text": "", "status": True, "agent_type": "text_agent"}
    response = client.post("/instructions/", json=invalid_data, headers=auth_headers)
    assert response.status_code == 422
