import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from datetime import datetime
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from api.wizard import router
from database.models import get_db

# Mock data for testing
MOCK_WIZARD = {
    "id": 1,
    "title": "Test Wizard",
    "context": "Test Context",
    "parent_id": None,
    "enabled": True,
    "created_at": datetime.now(),
    "updated_at": datetime.now(),
    "children": []
}

@pytest.fixture
def mock_db():
    return Mock(spec=Session)

@pytest.fixture
def mock_wizard_repo():
    with patch('api.wizard.WizardRepository') as mock:
        yield mock

@pytest.fixture
def client(mock_db):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app)

def test_get_root_wizards(client, mock_wizard_repo):
    # Arrange
    mock_wizard_repo.return_value.get_root_wizards.return_value = [MOCK_WIZARD]
    
    # Act
    response = client.get("/wizards/hierarchy/roots")
    
    # Assert
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Test Wizard"

def test_get_enabled_wizards(client, mock_wizard_repo):
    # Arrange
    mock_wizard_repo.return_value.get_enabled_wizards.return_value = [MOCK_WIZARD]
    
    # Act
    response = client.get("/wizards/enabled")
    
    # Assert
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["enabled"] is True

def test_get_disabled_wizards(client, mock_wizard_repo):
    # Arrange
    disabled_wizard = {**MOCK_WIZARD, "enabled": False}
    mock_wizard_repo.return_value.get_disabled_wizards.return_value = [disabled_wizard]
    
    # Act
    response = client.get("/wizards/disabled")
    
    # Assert
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["enabled"] is False

def test_create_wizard(client, mock_wizard_repo):
    # Arrange
    new_wizard = {
        "title": "New Wizard",
        "context": "New Context",
        "parent_id": None,
        "enabled": True
    }
    mock_wizard_repo.return_value.create.return_value = {**MOCK_WIZARD, **new_wizard}
    
    # Act
    response = client.post("/wizards/", json=new_wizard)
    
    # Assert
    assert response.status_code == 200
    assert response.json()["title"] == "New Wizard"
    assert response.json()["context"] == "New Context"

def test_get_wizard_by_id(client, mock_wizard_repo):
    # Arrange
    mock_wizard_repo.return_value.get.return_value = MOCK_WIZARD
    
    # Act
    response = client.get("/wizards/1")
    
    # Assert
    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["title"] == "Test Wizard"

def test_get_wizard_not_found(client, mock_wizard_repo):
    # Arrange
    mock_wizard_repo.return_value.get.return_value = None
    
    # Act
    response = client.get("/wizards/999")
    
    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Wizard not found"

def test_update_wizard(client, mock_wizard_repo):
    # Arrange
    update_data = {
        "title": "Updated Wizard",
        "context": "Updated Context"
    }
    mock_wizard_repo.return_value.update.return_value = {**MOCK_WIZARD, **update_data}
    
    # Act
    response = client.put("/wizards/1", json=update_data)
    
    # Assert
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Wizard"
    assert response.json()["context"] == "Updated Context"

def test_delete_wizard(client, mock_wizard_repo):
    # Arrange
    mock_wizard_repo.return_value.delete.return_value = True
    
    # Act
    response = client.delete("/wizards/1")
    
    # Assert
    assert response.status_code == 200
    assert response.json()["message"] == "Wizard deleted successfully"

def test_delete_wizard_not_found(client, mock_wizard_repo):
    # Arrange
    mock_wizard_repo.return_value.delete.return_value = False
    
    # Act
    response = client.delete("/wizards/999")
    
    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Wizard not found"

def test_get_wizard_hierarchy(client, mock_wizard_repo):
    # Arrange
    child_wizard = {
        **MOCK_WIZARD,
        "id": 2,
        "parent_id": 1
    }
    mock_wizard_repo.return_value.get_wizard_hierarchy.return_value = [MOCK_WIZARD, child_wizard]
    
    # Act
    response = client.get("/wizards/1/hierarchy")
    
    # Assert
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[1]["parent_id"] == 1

def test_enable_wizard(client, mock_wizard_repo):
    # Arrange
    mock_wizard_repo.return_value.enable_wizard.return_value = MOCK_WIZARD
    
    # Act
    response = client.post("/wizards/1/enable")
    
    # Assert
    assert response.status_code == 200
    assert response.json()["enabled"] is True

def test_disable_wizard(client, mock_wizard_repo):
    # Arrange
    disabled_wizard = {**MOCK_WIZARD, "enabled": False}
    mock_wizard_repo.return_value.disable_wizard.return_value = disabled_wizard
    
    # Act
    response = client.post("/wizards/1/disable")
    
    # Assert
    assert response.status_code == 200
    assert response.json()["enabled"] is False 