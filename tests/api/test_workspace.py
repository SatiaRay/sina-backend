import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database.models import Base, User, Workspace, WorkspaceUser, get_db
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
        db.query(WorkspaceUser).delete()
        db.query(Workspace).delete()
        db.query(User).delete()
        db.commit()
        db.close()

@pytest.fixture(scope="function")
def customer_user(db: sessionmaker):
    """Create a customer user for testing"""
    email = f"customer_{uuid.uuid4()}@example.com"
    user = User(email=email, password_hash="hash", user_type="customer", is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture(scope="function")
def another_user(db: sessionmaker):
    """Create another user for testing"""
    email = f"member_{uuid.uuid4()}@example.com"
    user = User(email=email, password_hash="hash", user_type="customer", is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def test_create_workspace(db, customer_user):
    """Test creating a workspace"""
    workspace_data = {
        "name": "Test Workspace",
        "description": "A test workspace",
        "owner_id": customer_user.id
    }
    
    response = client.post("/workspaces/", json=workspace_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Workspace"
    assert data["owner_id"] == customer_user.id
    assert data["is_active"] is True

def test_list_workspaces(db, customer_user):
    """Test listing workspaces with pagination"""
    # Create multiple workspaces
    ws1 = Workspace(name="WS1", owner_id=customer_user.id)
    ws2 = Workspace(name="WS2", owner_id=customer_user.id)
    ws3 = Workspace(name="WS3", owner_id=customer_user.id)
    db.add_all([ws1, ws2, ws3])
    db.commit()
    
    response = client.get("/workspaces/")
    assert response.status_code == 200
    data = response.json()
    assert "workspaces" in data
    assert "total" in data
    assert "page" in data
    assert "per_page" in data
    assert "total_pages" in data
    assert "has_next" in data
    assert "has_prev" in data
    assert data["total"] >= 3
    assert len(data["workspaces"]) >= 3
    assert any(w["name"] == "WS1" for w in data["workspaces"])

def test_list_workspaces_pagination(db, customer_user):
    """Test workspace pagination"""
    # Create 15 workspaces
    workspaces = []
    for i in range(15):
        ws = Workspace(name=f"WS{i}", owner_id=customer_user.id)
        workspaces.append(ws)
    db.add_all(workspaces)
    db.commit()
    
    # Test first page with 5 items
    response = client.get("/workspaces/?page=1&per_page=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data["workspaces"]) == 5
    assert data["page"] == 1
    assert data["per_page"] == 5
    assert data["total"] == 15
    assert data["total_pages"] == 3
    assert data["has_next"] is True
    assert data["has_prev"] is False

def test_get_workspace(db, customer_user):
    """Test getting a specific workspace"""
    workspace = Workspace(name="Test WS", owner_id=customer_user.id)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    
    response = client.get(f"/workspaces/{workspace.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == workspace.id
    assert data["name"] == "Test WS"

def test_update_workspace(db, customer_user):
    """Test updating a workspace"""
    workspace = Workspace(name="Original Name", owner_id=customer_user.id)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    
    update_data = {"name": "Updated Name", "description": "Updated description"}
    response = client.put(f"/workspaces/{workspace.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["description"] == "Updated description"

def test_delete_workspace(db, customer_user):
    """Test deleting a workspace"""
    workspace = Workspace(name="To Delete", owner_id=customer_user.id)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    
    response = client.delete(f"/workspaces/{workspace.id}")
    assert response.status_code == 204
    
    # Verify it's deleted
    get_response = client.get(f"/workspaces/{workspace.id}")
    assert get_response.status_code == 404

def test_add_and_remove_user_to_workspace(db, customer_user, another_user):
    """Test adding and removing users from workspace"""
    workspace = Workspace(name="Test WS", owner_id=customer_user.id)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    
    # Add user to workspace
    add_data = {"user_id": another_user.id, "role": "member"}
    response = client.post(f"/workspaces/{workspace.id}/users", json=add_data)
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == another_user.id
    assert data["role"] == "member"
    
    # Remove user from workspace
    response = client.delete(f"/workspaces/{workspace.id}/users/{another_user.id}")
    assert response.status_code == 204  # Fixed: API returns 204 No Content

def test_list_workspace_users(db, customer_user, another_user):
    """Test listing users in a workspace"""
    workspace = Workspace(name="Test WS", owner_id=customer_user.id)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    
    # Add user to workspace
    workspace_user = WorkspaceUser(
        workspace_id=workspace.id,
        user_id=another_user.id,
        role="member"
    )
    db.add(workspace_user)
    db.commit()
    
    response = client.get(f"/workspaces/{workspace.id}/users")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(u["user_id"] == another_user.id for u in data) 