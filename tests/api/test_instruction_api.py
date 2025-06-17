import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from database.models import get_db, BaseModel
from database.repository import InstructionRepository
from api.main import app
from fastapi import FastAPI
from tests.conftest import db
from sqlalchemy.orm import sessionmaker
from api.instruction import router


# Test data
TEST_INSTRUCTION = {
    "label": "Test Instruction",
    "text": "This is a test instruction",
    "status": True
}


# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create test app
app = FastAPI()

# Override the get_db dependency
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
app.include_router(router)
client = TestClient(app)

@pytest.fixture(scope="function")
def db():
    # Create the database and tables
    BaseModel.metadata.create_all(bind=engine)
    
    # Create a new session for the test
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after the test
        BaseModel.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_instruction(db):
    """Create a test instruction in the database"""
    repo = InstructionRepository(db)
    instruction = repo.create(TEST_INSTRUCTION)
    return instruction

def test_create_instruction(db):
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
    
    # Check pagination structure
    assert isinstance(data, dict)
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert "pages" in data
    
    # Check items
    assert isinstance(data["items"], list)
    assert len(data["items"]) > 0
    assert data["items"][0]["label"] == TEST_INSTRUCTION["label"]
    assert data["items"][0]["text"] == TEST_INSTRUCTION["text"]
    
    # Check pagination values
    assert data["page"] == 1
    assert data["size"] == 10
    assert data["total"] > 0
    assert data["pages"] > 0

def test_get_instructions_active_only(db):
    """Test getting only active instructions"""
    # Create a test instruction first
    repo = InstructionRepository(db)
    instruction = repo.create(TEST_INSTRUCTION)
    
    response = client.get("/instructions/?active_only=true")
    assert response.status_code == 200
    data = response.json()
    
    # Check pagination structure
    assert isinstance(data, dict)
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert "pages" in data
    
    # Check items
    assert isinstance(data["items"], list)
    assert len(data["items"]) > 0
    for instruction in data["items"]:
        assert instruction["status"] is True
        assert instruction["label"] == TEST_INSTRUCTION["label"]
        assert instruction["text"] == TEST_INSTRUCTION["text"]
    
    # Check pagination values
    assert data["page"] == 1
    assert data["size"] == 10
    assert data["total"] > 0
    assert data["pages"] > 0

def test_get_instructions_pagination(db):
    """Test pagination of instructions"""
    # Create multiple test instructions
    repo = InstructionRepository(db)
    for i in range(15):  # Create 15 instructions
        test_data = TEST_INSTRUCTION.copy()
        test_data["label"] = f"Test Instruction {i}"
        repo.create(test_data)
    
    # Test first page
    response = client.get("/instructions/?page=1&size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10
    assert data["page"] == 1
    assert data["size"] == 10
    assert data["total"] >= 15
    assert data["pages"] >= 2
    
    # Test second page
    response = client.get("/instructions/?page=2&size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 0
    assert data["page"] == 2
    assert data["size"] == 10

def test_get_instruction(db, test_instruction):
    """Test getting a specific instruction"""
    response = client.get(f"/instructions/{test_instruction.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_instruction.id
    assert data["label"] == test_instruction.label
    assert data["text"] == test_instruction.text

def test_get_nonexistent_instruction(db):
    """Test getting a non-existent instruction"""
    response = client.get("/instructions/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"

def test_update_instruction(db, test_instruction):
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

def test_update_nonexistent_instruction(db):
    """Test updating a non-existent instruction"""
    update_data = {
        "label": "Updated Label",
        "text": "Updated text",
        "status": False
    }
    response = client.put("/instructions/99999", json=update_data)
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"

def test_delete_instruction(db, test_instruction):
    """Test deleting an instruction"""
    response = client.delete(f"/instructions/{test_instruction.id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Instruction deleted successfully"

    # Verify the instruction is actually deleted
    get_response = client.get(f"/instructions/{test_instruction.id}")
    assert get_response.status_code == 404

def test_delete_nonexistent_instruction(db):
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

def test_disable_instruction(db, test_instruction):
    """Test disabling an instruction"""
    response = client.patch(f"/instructions/{test_instruction.id}/disable")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is False

def test_enable_nonexistent_instruction(db):
    """Test enabling a non-existent instruction"""
    response = client.patch("/instructions/99999/enable")
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"

def test_disable_nonexistent_instruction(db):
    """Test disabling a non-existent instruction"""
    response = client.patch("/instructions/99999/disable")
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"

def test_create_instruction_validation(db):
    """Test validation when creating an instruction"""
    # Test missing required fields
    invalid_data = {"label": "Test Label"}  # Missing text field
    response = client.post("/instructions/", json=invalid_data)
    assert response.status_code == 422

    # Test empty fields
    invalid_data = {"label": "", "text": "", "status": True}
    response = client.post("/instructions/", json=invalid_data)
    assert response.status_code == 422 