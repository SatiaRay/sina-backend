import pytest
from database.repositories.workflow_repository import WorkflowRepository
from database.models import Workflow
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, get_db, User
from fastapi.testclient import TestClient
import uuid
from provider.service_container import container

# In-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

# Import app after setting up the database
from api.main import app

client = TestClient(app)

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test"""
    db = TestingSessionLocal()
    app.dependency_overrides[get_db] = lambda: (yield db)
    try:
        yield db
    finally:
        db.close()
        app.dependency_overrides.pop(get_db, None)
        
@pytest.fixture(autouse=True)
def setup_and_teardown(auth_user):
    auth_headers, user = auth_user
    container.bind('auth_user', user)
    yield  
    print("[TEARDOWN] Cleaning up after test")
    
# Add fixture for authenticated customer user and token
@pytest.fixture(scope="function")
def auth_user(db_session):
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
    user = db_session.query(User).filter(User.email == email).first()
    db_session.close()
    auth_headers = {"Authorization": f"Bearer {token}"}
    return auth_headers, user

@pytest.fixture
def workflow_repository(db_session):
    return WorkflowRepository(db_session)

def test_get_active_workflows_flows(workflow_repository, db_session):
    user = container.make('auth_user')
    
    workspace_id = user.current_workspace_id
    
    # Arrange: create two active workflows with flows
    flow1 = {"id": "node1", "type": "start"}
    flow2 = {"id": "node2", "type": "end"}
    wf1 = Workflow(status=True, flow=flow1, name="workflow 1", workspace_id=workspace_id)
    wf2 = Workflow(status=True, flow=flow2, name="workflow 2", workspace_id=workspace_id)
    db_session.add(wf1)
    db_session.add(wf2)
    db_session.commit()
    
    # Act
    result = workflow_repository.get_active_workflows_flows()
    
    # Assert
    assert result == [flow1, flow2]
    assert len(result) == 2
    for flow in result:
        assert isinstance(flow, dict)
        assert "id" in flow
        assert "type" in flow

def test_get_active_workflows_flows_empty(workflow_repository, db_session):
    # Arrange: ensure no active workflows
    db_session.query(Workflow).delete()
    db_session.commit()
    
    # Act
    result = workflow_repository.get_active_workflows_flows()
    
    # Assert
    assert result == []
    assert len(result) == 0