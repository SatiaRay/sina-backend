import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database.models import Base, User, Workspace, Document, AiBot, AiBotDocument, get_db
from datetime import datetime
import uuid
from unittest.mock import patch
import copy
import random

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

# Import app and get_db earlier if needed
from api.main import app

client = TestClient(app)

@pytest.fixture(scope="function")
def db():
    db = TestingSessionLocal()
    # Patch the dependency to always yield this session
    app.dependency_overrides[get_db] = lambda: (yield db)
    try:
        yield db
    finally:
        db.query(AiBotDocument).delete()
        db.query(AiBot).delete()
        db.query(Document).delete()
        db.query(Workspace).delete()
        db.query(User).delete()
        db.commit()
        db.close()
        # Optionally clear the override after the test
        app.dependency_overrides[get_db] = lambda: (_ for _ in ()).throw(RuntimeError("No DB override set"))

@pytest.fixture(scope="function")
def test_workspace(db: sessionmaker, auth_user):
    """Create a workspace for testing (owned by user)"""
    auth_headers, user = auth_user
    
    workspace = Workspace(
        name="Test Workspace",
        description="Test workspace description",
        owner_id=user.id,
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
def test_aibot(db: sessionmaker, auth_user, test_workspace):
    """Create an AiBot for testing"""
    auth_headers, user = auth_user
    
    aibot = AiBot(
        name="Test AiBot",
        workspace_id=test_workspace.id,
        owner_id=user.id
    )
    db.add(aibot)
    db.commit()
    db.refresh(aibot)
    return aibot

# Add fixture for authenticated customer user and token
@pytest.fixture(scope="function")
def auth_user(db):
    email = f"customer_{uuid.uuid4()}@example.com"
    password = "securepassword123"
    # Register
    register_resp = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "user_type": "customer"
        }
    )
    assert register_resp.status_code == 201
    # Login
    login_resp = client.post(
        "/auth/login",
        json={"email": email, "password": password}
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    # Fetch user from DB to ensure it's persisted
    from database.models import User
    
    user = db.query(User).filter(User.email == email).first()
    db.close()
    
    auth_headers = {"Authorization": f"Bearer {token}"}
    
    return auth_headers, user

class TestAiBotAPI:
    
    def test_create_aibot_success(self, auth_user):
        auth_headers, user = auth_user
        
        """Test successful AiBot creation"""
        aibot_data = {
            "name": "New AiBot",
            "owner_id": user.id
        }
        with patch("api.aibot.VectorStore") as mock_vector_store:
            response = client.post("/aibots/", json=aibot_data, headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "New AiBot"
            assert data["workspace_id"] == user.current_workspace_id
            assert data["owner_id"] == user.id
            assert "id" in data
            assert "created_at" in data
            assert "updated_at" in data
 
    def test_create_aibot_workspace_not_found(self, auth_user):
        """Test AiBot creation with non-existent workspace"""
        auth_headers, user = auth_user
        
        aibot_data = {
            "name": "New AiBot",
            "workspace_id": 999,
            "owner_id": user.id
        }
        
        response = client.post("/aibots/", json=aibot_data, headers=auth_headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "Workspace not found"

    def test_create_aibot_invalid_owner(self, test_workspace, auth_user):
        """Test AiBot creation with invalid owner"""
        auth_headers, user = auth_user
        
        aibot_data = {
            "name": "New AiBot",
            "workspace_id": test_workspace.id,
            "owner_id": 999
        }
        
        response = client.post("/aibots/", json=aibot_data, headers=auth_headers)
        assert response.status_code == 400
        assert response.json()["detail"] == "Owner must be a valid customer user."

    def test_list_aibots_success(self, test_aibot, auth_user):
        """Test successful AiBot listing"""
        auth_headers, user = auth_user

        response = client.get("/aibots/", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["per_page"] == 10
        assert len(data["aibots"]) == 1
        assert data["aibots"][0]["name"] == "Test AiBot"

    def test_list_aibots_with_filters(self, test_aibot, test_workspace, auth_user):
        """Test AiBot listing with filters"""
        auth_headers, user = auth_user

        # Test workspace filter
        response = client.get(f"/aibots/?workspace_id={test_workspace.id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["total"] == 1
        
        # Test owner filter
        response = client.get(f"/aibots/?owner_id={user.id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["total"] == 1
        
        # Test non-existent workspace filter
        response = client.get("/aibots/?workspace_id=999", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_get_aibot_success(self, test_aibot, auth_user):
        """Test successful AiBot retrieval"""
        auth_headers, user = auth_user

        response = client.get(f"/aibots/{test_aibot.id}", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == test_aibot.id
        assert data["name"] == "Test AiBot"

    def test_get_aibot_not_found(self, auth_user):
        """Test AiBot retrieval with non-existent ID"""
        auth_headers, user = auth_user

        response = client.get("/aibots/999", headers=auth_headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "AiBot not found"

    def test_update_aibot_success(self, test_aibot, auth_user):
        """Test successful AiBot update"""
        auth_headers, user = auth_user

        update_data = {"name": "Updated AiBot Name"}
        
        response = client.put(f"/aibots/{test_aibot.id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "Updated AiBot Name"
        assert data["id"] == test_aibot.id

    def test_update_aibot_not_found(self, auth_user):
        """Test AiBot update with non-existent ID"""
        auth_headers, user = auth_user

        update_data = {"name": "Updated AiBot Name"}
        
        response = client.put("/aibots/999", json=update_data, headers=auth_headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "AiBot not found"

    def test_delete_aibot_success(self, test_aibot, auth_user):
        """Test successful AiBot deletion"""
        auth_headers, user = auth_user

        response = client.delete(f"/aibots/{test_aibot.id}", headers=auth_headers)
        assert response.status_code == 204
        
        # Verify AiBot is deleted
        response = client.get(f"/aibots/{test_aibot.id}", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_aibot_not_found(self, auth_user):
        """Test AiBot deletion with non-existent ID"""
        auth_headers, user = auth_user

        response = client.delete("/aibots/999", headers=auth_headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "AiBot not found"

    def test_add_document_to_aibot_success(self, test_aibot, test_document, auth_user):
        """Test successful document addition to AiBot"""
        auth_headers, user = auth_user

        document_data = {
            "document_id": test_document.id,
            "vectorize_id": "test_vector_id"
        }
        
        response = client.post(f"/aibots/{test_aibot.id}/documents", json=document_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["document_id"] == test_document.id
        assert data["vectorize_id"] == "test_vector_id"

    def test_add_document_to_aibot_not_found(self, test_document, auth_user):
        """Test document addition to non-existent AiBot"""
        auth_headers, user = auth_user

        document_data = {
            "document_id": test_document.id,
            "vectorize_id": "test_vector_id"
        }
        
        response = client.post("/aibots/999/documents", json=document_data, headers=auth_headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "AiBot not found"

    def test_add_document_to_aibot_document_not_found(self, test_aibot, auth_user):
        """Test document addition with non-existent document"""
        auth_headers, user = auth_user

        document_data = {
            "document_id": 999,
            "vectorize_id": "test_vector_id"
        }
        
        response = client.post(f"/aibots/{test_aibot.id}/documents", json=document_data, headers=auth_headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "Document not found or not accessible"

    def test_add_document_to_aibot_already_associated(self, test_aibot, test_document, auth_user):
        """Test adding document that's already associated with AiBot"""
        auth_headers, user = auth_user

        # Add document first time
        document_data = {
            "document_id": test_document.id,
            "vectorize_id": "test_vector_id"
        }
        response = client.post(f"/aibots/{test_aibot.id}/documents", json=document_data, headers=auth_headers)
        assert response.status_code == 200
        
        # Try to add same document again
        response = client.post(f"/aibots/{test_aibot.id}/documents", json=document_data, headers=auth_headers)
        assert response.status_code == 400
        assert response.json()["detail"] == "Document already associated with this AiBot"

    def test_remove_document_from_aibot_success(self, test_aibot, test_document, auth_user):
        """Test successful document removal from AiBot"""
        auth_headers, user = auth_user

        # First add document
        document_data = {
            "document_id": test_document.id,
            "vectorize_id": "test_vector_id"
        }
        client.post(f"/aibots/{test_aibot.id}/documents", json=document_data, headers=auth_headers)
        
        # Then remove it
        response = client.delete(f"/aibots/{test_aibot.id}/documents/{test_document.id}", headers=auth_headers)
        assert response.status_code == 204

    def test_remove_document_from_aibot_not_associated(self, test_aibot, test_document, auth_user):
        """Test document removal that's not associated with AiBot"""
        auth_headers, user = auth_user

        response = client.delete(f"/aibots/{test_aibot.id}/documents/{test_document.id}", headers=auth_headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "Document not associated with this AiBot"

    def test_list_aibot_documents_success(self, test_aibot, test_document, auth_user):
        """Test successful listing of AiBot documents"""
        auth_headers, user = auth_user

        # First add a document
        document_data = {
            "document_id": test_document.id,
            "vectorize_id": "test_vector_id"
        }
        client.post(f"/aibots/{test_aibot.id}/documents", json=document_data, headers=auth_headers)
        
        # Then list documents
        response = client.get(f"/aibots/{test_aibot.id}/documents", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 1
        assert data[0]["document_id"] == test_document.id
        assert data[0]["vectorize_id"] == "test_vector_id"

    def test_list_aibot_documents_not_found(self, auth_user):
        """Test listing documents for non-existent AiBot"""
        auth_headers, user = auth_user

        response = client.get("/aibots/999/documents", headers=auth_headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "AiBot not found"

    def test_get_aibot_stats_success(self, test_aibot, auth_user):
        """Test successful AiBot statistics retrieval"""
        auth_headers, user = auth_user

        response = client.get(f"/aibots/{test_aibot.id}/stats", headers=auth_headers)
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

    def test_get_aibot_stats_not_found(self, auth_user):
        """Test AiBot statistics retrieval for non-existent AiBot"""
        auth_headers, user = auth_user

        response = client.get("/aibots/999/stats", headers=auth_headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "AiBot not found"

    def test_pagination(self, test_workspace, auth_user):
        """Test AiBot listing pagination"""
        auth_headers, user = auth_user
        
        # Create multiple AiBots
        for i in range(15):
            aibot_data = {
                "name": f"AiBot {i}",
                "workspace_id": test_workspace.id,
                "owner_id": user.id
            }
            client.post("/aibots/", json=aibot_data, headers=auth_headers)
        
        # Test first page
        response = client.get("/aibots/?page=1&per_page=10", headers=auth_headers)
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
        response = client.get("/aibots/?page=2&per_page=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["has_next"] == False
        assert data["has_prev"] == True
        assert len(data["aibots"]) == 5 