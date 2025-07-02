import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database.models import Base, User, Workspace, Document, AiBot, AiBotDocument, get_db
from datetime import datetime
import uuid

# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

def override_get_db():
    """Override the database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Import app after setting up the override
from api.main import app

# Override the database dependency
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="function")
def db():
    """Create a fresh database session for each test"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        # Clean up all data after each test
        db.query(AiBotDocument).delete()
        db.query(AiBot).delete()
        db.query(Document).delete()
        db.query(Workspace).delete()
        db.query(User).delete()
        db.commit()
        db.close()

@pytest.fixture(scope="function")
def test_user(db: sessionmaker):
    """Create a customer user for testing"""
    email = f"customer_{uuid.uuid4()}@example.com"
    user = User(
        email=email,
        password_hash="hashed_password",
        user_type="customer",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture(scope="function")
def test_workspace(db: sessionmaker, test_user):
    """Create a workspace for testing"""
    workspace = Workspace(
        name="Test Workspace",
        description="Test workspace description",
        owner_id=test_user.id,
        is_active=True
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace

@pytest.fixture(scope="function")
def test_document(db: sessionmaker, test_workspace):
    """Create a document for testing"""
    document = Document(
        title="Test Document",
        workspace_id=test_workspace.id,
        type="manual"
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document

@pytest.fixture(scope="function")
def test_aibot(db: sessionmaker, test_user, test_workspace):
    """Create an AiBot for testing"""
    aibot = AiBot(
        name="Test AiBot",
        workspace_id=test_workspace.id,
        owner_id=test_user.id
    )
    db.add(aibot)
    db.commit()
    db.refresh(aibot)
    return aibot

class TestAiBotAPI:
    
    def test_create_aibot_success(self, test_user, test_workspace):
        """Test successful AiBot creation"""
        aibot_data = {
            "name": "New AiBot",
            "workspace_id": test_workspace.id,
            "owner_id": test_user.id
        }
        
        response = client.post("/aibots/", json=aibot_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "New AiBot"
        assert data["workspace_id"] == test_workspace.id
        assert data["owner_id"] == test_user.id
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_aibot_workspace_not_found(self, test_user):
        """Test AiBot creation with non-existent workspace"""
        aibot_data = {
            "name": "New AiBot",
            "workspace_id": 999,
            "owner_id": test_user.id
        }
        
        response = client.post("/aibots/", json=aibot_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Workspace not found"

    def test_create_aibot_invalid_owner(self, test_workspace):
        """Test AiBot creation with invalid owner"""
        aibot_data = {
            "name": "New AiBot",
            "workspace_id": test_workspace.id,
            "owner_id": 999
        }
        
        response = client.post("/aibots/", json=aibot_data)
        assert response.status_code == 400
        assert response.json()["detail"] == "Owner must be a valid customer user."

    def test_list_aibots_success(self, test_aibot):
        """Test successful AiBot listing"""
        response = client.get("/aibots/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["per_page"] == 10
        assert len(data["aibots"]) == 1
        assert data["aibots"][0]["name"] == "Test AiBot"

    def test_list_aibots_with_filters(self, test_aibot, test_workspace, test_user):
        """Test AiBot listing with filters"""
        # Test workspace filter
        response = client.get(f"/aibots/?workspace_id={test_workspace.id}")
        assert response.status_code == 200
        assert response.json()["total"] == 1
        
        # Test owner filter
        response = client.get(f"/aibots/?owner_id={test_user.id}")
        assert response.status_code == 200
        assert response.json()["total"] == 1
        
        # Test non-existent workspace filter
        response = client.get("/aibots/?workspace_id=999")
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_get_aibot_success(self, test_aibot):
        """Test successful AiBot retrieval"""
        response = client.get(f"/aibots/{test_aibot.id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == test_aibot.id
        assert data["name"] == "Test AiBot"

    def test_get_aibot_not_found(self):
        """Test AiBot retrieval with non-existent ID"""
        response = client.get("/aibots/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "AiBot not found"

    def test_update_aibot_success(self, test_aibot):
        """Test successful AiBot update"""
        update_data = {"name": "Updated AiBot Name"}
        
        response = client.put(f"/aibots/{test_aibot.id}", json=update_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "Updated AiBot Name"
        assert data["id"] == test_aibot.id

    def test_update_aibot_not_found(self):
        """Test AiBot update with non-existent ID"""
        update_data = {"name": "Updated AiBot Name"}
        
        response = client.put("/aibots/999", json=update_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "AiBot not found"

    def test_delete_aibot_success(self, test_aibot):
        """Test successful AiBot deletion"""
        response = client.delete(f"/aibots/{test_aibot.id}")
        assert response.status_code == 204
        
        # Verify AiBot is deleted
        response = client.get(f"/aibots/{test_aibot.id}")
        assert response.status_code == 404

    def test_delete_aibot_not_found(self):
        """Test AiBot deletion with non-existent ID"""
        response = client.delete("/aibots/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "AiBot not found"

    def test_add_document_to_aibot_success(self, test_aibot, test_document):
        """Test successful document addition to AiBot"""
        document_data = {
            "document_id": test_document.id,
            "vectorize_id": "test_vector_id"
        }
        
        response = client.post(f"/aibots/{test_aibot.id}/documents", json=document_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["document_id"] == test_document.id
        assert data["vectorize_id"] == "test_vector_id"

    def test_add_document_to_aibot_not_found(self, test_document):
        """Test document addition to non-existent AiBot"""
        document_data = {
            "document_id": test_document.id,
            "vectorize_id": "test_vector_id"
        }
        
        response = client.post("/aibots/999/documents", json=document_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "AiBot not found"

    def test_add_document_to_aibot_document_not_found(self, test_aibot):
        """Test document addition with non-existent document"""
        document_data = {
            "document_id": 999,
            "vectorize_id": "test_vector_id"
        }
        
        response = client.post(f"/aibots/{test_aibot.id}/documents", json=document_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Document not found or not accessible"

    def test_add_document_to_aibot_already_associated(self, test_aibot, test_document):
        """Test adding document that's already associated with AiBot"""
        # Add document first time
        document_data = {
            "document_id": test_document.id,
            "vectorize_id": "test_vector_id"
        }
        response = client.post(f"/aibots/{test_aibot.id}/documents", json=document_data)
        assert response.status_code == 200
        
        # Try to add same document again
        response = client.post(f"/aibots/{test_aibot.id}/documents", json=document_data)
        assert response.status_code == 400
        assert response.json()["detail"] == "Document already associated with this AiBot"

    def test_remove_document_from_aibot_success(self, test_aibot, test_document):
        """Test successful document removal from AiBot"""
        # First add document
        document_data = {
            "document_id": test_document.id,
            "vectorize_id": "test_vector_id"
        }
        client.post(f"/aibots/{test_aibot.id}/documents", json=document_data)
        
        # Then remove it
        response = client.delete(f"/aibots/{test_aibot.id}/documents/{test_document.id}")
        assert response.status_code == 204

    def test_remove_document_from_aibot_not_associated(self, test_aibot, test_document):
        """Test document removal that's not associated with AiBot"""
        response = client.delete(f"/aibots/{test_aibot.id}/documents/{test_document.id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Document not associated with this AiBot"

    def test_list_aibot_documents_success(self, test_aibot, test_document):
        """Test successful listing of AiBot documents"""
        # First add a document
        document_data = {
            "document_id": test_document.id,
            "vectorize_id": "test_vector_id"
        }
        client.post(f"/aibots/{test_aibot.id}/documents", json=document_data)
        
        # Then list documents
        response = client.get(f"/aibots/{test_aibot.id}/documents")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 1
        assert data[0]["document_id"] == test_document.id
        assert data[0]["vectorize_id"] == "test_vector_id"

    def test_list_aibot_documents_not_found(self):
        """Test listing documents for non-existent AiBot"""
        response = client.get("/aibots/999/documents")
        assert response.status_code == 404
        assert response.json()["detail"] == "AiBot not found"

    def test_get_aibot_stats_success(self, test_aibot):
        """Test successful AiBot statistics retrieval"""
        response = client.get(f"/aibots/{test_aibot.id}/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data["aibot_id"] == test_aibot.id
        assert data["name"] == "Test AiBot"
        assert "documents_count" in data
        assert "chats_count" in data
        assert "workflows_count" in data
        assert "instructions_count" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_get_aibot_stats_not_found(self):
        """Test AiBot statistics retrieval for non-existent AiBot"""
        response = client.get("/aibots/999/stats")
        assert response.status_code == 404
        assert response.json()["detail"] == "AiBot not found"

    def test_pagination(self, test_user, test_workspace):
        """Test AiBot listing pagination"""
        # Create multiple AiBots
        for i in range(15):
            aibot_data = {
                "name": f"AiBot {i}",
                "workspace_id": test_workspace.id,
                "owner_id": test_user.id
            }
            client.post("/aibots/", json=aibot_data)
        
        # Test first page
        response = client.get("/aibots/?page=1&per_page=10")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 15
        assert data["page"] == 1
        assert data["per_page"] == 10
        assert data["total_pages"] == 2
        assert data["has_next"] == True
        assert data["has_prev"] == False
        assert len(data["aibots"]) == 10
        
        # Test second page
        response = client.get("/aibots/?page=2&per_page=10")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["has_next"] == False
        assert data["has_prev"] == True
        assert len(data["aibots"]) == 5 