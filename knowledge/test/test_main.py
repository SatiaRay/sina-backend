import sys
import os

from test.conftest import force_patch_guard_auth
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from types import SimpleNamespace
import main

@pytest.fixture
def client():
    app = main.app

    # Reset overrides before tests
    app.dependency_overrides = {}

    fake_session = MagicMock()
    app.dependency_overrides[main.get_session] = lambda: fake_session

    mock_request = AsyncMock()
    force_patch_guard_auth(mock_request)

    return TestClient(app)

@pytest.fixture(autouse=True)
def patch_repos_and_vector():
    with patch('main.repo') as mock_repo, patch('main.vector') as mock_vector:
        mock_repo.create.return_value = {"id": 1}
        mock_repo.delete.return_value = True
        mock_repo.get_all.return_value = [SimpleNamespace(**{"id": 1})]
        mock_repo.get.return_value = {"id": 1}
        mock_repo.update.return_value = {"id": 1}
        mock_vector.search.return_value = [{"text": "test", "metadata": {}, "score": 1.0, "id": "abc"}]
        mock_vector.add_documents.return_value = ["vecid-123"]
        mock_vector.get_all_documents.return_value = []
        mock_vector.get_document_by_id.return_value = None
        mock_vector.delete_documents.return_value = None
        mock_vector.update_document.return_value = None
        yield

def test_service_up(client):
    response = client.get("/test")
    assert response.status_code == 200
    assert response.json() == {"msg": "The service is up !"}

def test_whoami(client):
    response = client.get("/whoami")
    assert response.status_code == 200
    assert "scopes" in response.json()
    assert "user_id" in response.json()

def test_store(client):
    doc = {"title": "foo", "text": "bar", "tag" : "pytest"}
    response = client.post("/", json=doc)
    assert response.status_code == 200
    assert response.json()["msg"] == "succeed"

def test_search(client):
    response = client.get("/search", params={"query": "foo"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_delete(client):
    response = client.delete("/1")
    assert response.status_code == 200
    assert response.json()["msg"] == "succeed"

def test_update(client):
    doc = {"title": "foo", "text": "bar", "tag" : "pytest"}
    response = client.put("/1", json=doc)
    assert response.status_code == 200
    assert response.json()["msg"] == "succeed"

def test_all(client):
    response = client.get("/")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)
    assert isinstance(response.json()['documents'], list)

def test_get_by_id(client):
    response = client.get("/1")
    assert response.status_code == 200
    assert "id" in response.json()
