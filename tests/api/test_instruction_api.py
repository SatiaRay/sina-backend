import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime
from database.models import Instruction, get_db, SessionLocal
from database.repository import InstructionRepository
from api.main import app

client = TestClient(app)

# Test data
TEST_INSTRUCTION = {
    "label": "Test Instruction",
    "text": "This is a test instruction",
    "status": True
}

@pytest.fixture(scope="function")
def db():
    """Create a fresh database session for each test"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def test_instruction(db):
    """Create a test instruction in the database"""
    repo = InstructionRepository(db)
    instruction = repo.create(TEST_INSTRUCTION)
    return instruction

def test_create_instruction():
    """Test creating a new instruction"""
    response = client.post("/instructions/", json=TEST_INSTRUCTION)
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == TEST_INSTRUCTION["label"]
    assert data["text"] == TEST_INSTRUCTION["text"]
    assert data["status"] == TEST_INSTRUCTION["status"]
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data

def test_get_instructions(db):
    """Test getting all instructions"""
    # Create a test instruction first
    repo = InstructionRepository(db)
    instruction = repo.create(TEST_INSTRUCTION)
    
    response = client.get("/instructions/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["label"] == TEST_INSTRUCTION["label"]
    assert data[0]["text"] == TEST_INSTRUCTION["text"]

def test_get_instructions_active_only(db):
    """Test getting only active instructions"""
    # Create a test instruction first
    repo = InstructionRepository(db)
    instruction = repo.create(TEST_INSTRUCTION)
    
    response = client.get("/instructions/?active_only=true")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    for instruction in data:
        assert instruction["status"] is True
        assert instruction["label"] == TEST_INSTRUCTION["label"]
        assert instruction["text"] == TEST_INSTRUCTION["text"]

def test_get_instruction(test_instruction):
    """Test getting a specific instruction"""
    response = client.get(f"/instructions/{test_instruction.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_instruction.id
    assert data["label"] == test_instruction.label
    assert data["text"] == test_instruction.text

def test_get_nonexistent_instruction():
    """Test getting a non-existent instruction"""
    response = client.get("/instructions/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"

def test_update_instruction(test_instruction):
    """Test updating an instruction"""
    update_data = {
        "label": "Updated Label",
        "text": "Updated text",
        "status": False
    }
    response = client.put(
        f"/instructions/{test_instruction.id}",
        json=update_data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == update_data["label"]
    assert data["text"] == update_data["text"]
    assert data["status"] == update_data["status"]

def test_update_nonexistent_instruction():
    """Test updating a non-existent instruction"""
    update_data = {
        "label": "Updated Label",
        "text": "Updated text",
        "status": False
    }
    response = client.put("/instructions/99999", json=update_data)
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"

def test_delete_instruction(test_instruction):
    """Test deleting an instruction"""
    response = client.delete(f"/instructions/{test_instruction.id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Instruction deleted successfully"

    # Verify the instruction is actually deleted
    get_response = client.get(f"/instructions/{test_instruction.id}")
    assert get_response.status_code == 404

def test_delete_nonexistent_instruction():
    """Test deleting a non-existent instruction"""
    response = client.delete("/instructions/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"

def test_enable_instruction(test_instruction, db):
    """Test enabling an instruction"""
    # First disable the instruction
    repo = InstructionRepository(db)
    repo.disable_instruction(test_instruction.id)

    # Then enable it
    response = client.patch(f"/instructions/{test_instruction.id}/enable")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is True

def test_disable_instruction(test_instruction):
    """Test disabling an instruction"""
    response = client.patch(f"/instructions/{test_instruction.id}/disable")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is False

def test_enable_nonexistent_instruction():
    """Test enabling a non-existent instruction"""
    response = client.patch("/instructions/99999/enable")
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"

def test_disable_nonexistent_instruction():
    """Test disabling a non-existent instruction"""
    response = client.patch("/instructions/99999/disable")
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"

def test_create_instruction_validation():
    """Test validation when creating an instruction"""
    # Test missing required fields
    invalid_data = {"label": "Test Label"}  # Missing text field
    response = client.post("/instructions/", json=invalid_data)
    assert response.status_code == 422

    # Test empty fields
    invalid_data = {"label": "", "text": "", "status": True}
    response = client.post("/instructions/", json=invalid_data)
    assert response.status_code == 422 