# test/test_main.py
import sys
import os

from test.conftest import force_patch_guard_auth
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from types import SimpleNamespace
import main

# Create mock auth function
async def mock_auth_validate(credential):
    """Mock auth_validate that always succeeds with workspace scope"""
    # Add workspace scope to request state
    if hasattr(credential, 'state'):
        credential.state.scopes = ['workspace:test-workspace']
        credential.state.user_id = 'test-user'
        credential.state.tenant_context = {
            'workspace_id': 'test-workspace',
            'user_id': 'test-user',
            'scopes': ['workspace:test-workspace']
        }
    return credential

@pytest.fixture
def client():
    app = main.app

    # Reset overrides before tests
    app.dependency_overrides = {}

    # Use force_patch_guard_auth to patch the auth function
    force_patch_guard_auth(mock_auth_validate)

    # Mock the dependencies that will be injected
    mock_repo = MagicMock()
    mock_repo.workspace_id = "test-workspace"
    mock_repo.create.return_value = MagicMock(id=1)
    mock_repo.delete.return_value = True
    mock_repo.get_all.return_value = [SimpleNamespace(**{"id": 1, "vector_id": "vid1", "workspace_id": "test-workspace"})]
    mock_repo.get.return_value = SimpleNamespace(**{"id": 1, "vector_id": "vid1", "workspace_id": "test-workspace"})
    mock_repo.update.return_value = {"id": 1}
    mock_repo.count.return_value = 1
    
    # Mock get_document_repository to return our mock repo
    app.dependency_overrides[main.get_document_repository] = lambda: mock_repo
    
    # Mock get_db to return a mock session
    mock_db = MagicMock()
    app.dependency_overrides[main.get_db] = lambda: mock_db
    
    # Mock vector - patch the global vector instance in main module
    mock_vector = MagicMock()
    mock_vector.search.return_value = [{"text": "test", "metadata": {}, "score": 1.0, "id": "abc"}]
    
    # Use patch to replace the vector instance in main module
    with patch('main.vector', mock_vector):
        return TestClient(app)

def test_service_up(client):
    response = client.get("/test")
    assert response.status_code == 200
    assert response.json() == {"msg": "The service is up !"}

def test_whoami(client):
    response = client.get("/whoami")
    assert response.status_code == 200
    data = response.json()
    assert "scopes" in data
    assert "user_id" in data
    assert data.get("workspace_id") == "test-workspace"

def test_store(client):
    doc = {"title": "foo", "text": "bar", "tag": "pytest"}
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
    doc = {"title": "foo", "text": "bar", "tag": "pytest"}
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

# Test error cases
def test_store_error(client):
    """Test store endpoint when repository.create raises an exception"""
    # Mock the repository to raise an exception
    app = main.app
    mock_repo = MagicMock()
    mock_repo.create.side_effect = Exception("Test error")
    app.dependency_overrides[main.get_document_repository] = lambda: mock_repo
    
    doc = {"title": "foo", "text": "bar", "tag": "pytest"}
    response = client.post("/", json=doc)
    assert response.status_code == 500
    assert "Store document failed" in response.json()["detail"]

def test_get_by_id_not_found(client):
    """Test find endpoint when document is not found"""
    app = main.app
    mock_repo = MagicMock()
    mock_repo.get.return_value = None  # Document not found
    app.dependency_overrides[main.get_document_repository] = lambda: mock_repo
    
    response = client.get("/999")
    assert response.status_code == 404
    assert "Document not found" in response.json()["detail"]