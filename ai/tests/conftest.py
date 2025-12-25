import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from src.database.models import Base, get_db, Instruction
from src.api.main import app
from src.oauth.dependencies import get_current_user, get_current_workspace
from src.database.models import Wizard 
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
from typing import Dict, Any

# Use in-memory SQLite for all tests
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return engine


@pytest.fixture(scope="function")
def db(test_engine):
    # Drop and recreate all tables before each test
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def mock_token_info() -> Dict[str, Any]:
    """Mock token info with workspace scope"""
    return {
        "sub": "test-user-id",
        "username": "testuser",
        "email": "test@example.com",
        "scope": "workspace:39354e1f-b9cc-30eb-9700-963b3a53e977 read write",
        "active": True
    }


@pytest.fixture
def mock_token_info_multiple_workspaces() -> Dict[str, Any]:
    """Mock token info with multiple workspace scopes"""
    return {
        "sub": "test-user-id",
        "username": "testuser",
        "email": "test@example.com",
        "scope": "workspace:39354e1f-b9cc-30eb-9700-963b3a53e977 workspace:another-workspace-id read write",
        "active": True
    }


@pytest.fixture
def mock_token_info_no_workspace() -> Dict[str, Any]:
    """Mock token info without workspace scope"""
    return {
        "sub": "test-user-id",
        "username": "testuser",
        "email": "test@example.com",
        "scope": "read write",  # No workspace scope
        "active": True
    }


@pytest.fixture
def create_test_instruction(db, mock_token_info):
    """Helper fixture to create test instructions"""
    def _create_instruction(
        label="Test Instruction", 
        text="Test content", 
        status=True,
        workspace_id="39354e1f-b9cc-30eb-9700-963b3a53e977",
        created_by=None
    ):
        # Ensure label and text are not empty
        label = label.strip() or "Test Instruction"
        text = text.strip() or "Test content"
        
        # Use provided created_by or default from mock token
        if created_by is None:
            created_by = mock_token_info.get("sub", "test-user-id")
        
        instruction = Instruction(
            label=label,
            text=text,
            status=status,
            workspace_id=workspace_id,
            created_by=created_by,  # Add this field
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(instruction)
        db.commit()
        db.refresh(instruction)
        return instruction
    return _create_instruction


@pytest.fixture(scope="function")
def client(db, monkeypatch, mock_token_info):
    # Override get_db to use the session from the db fixture
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    # Mock OAuth dependencies
    async def override_get_current_user():
        return mock_token_info
    
    async def override_get_current_workspace():
        # Extract workspace from mock token info
        scope = mock_token_info.get("scope", "")
        for scope_item in scope.split():
            if scope_item.startswith("workspace:"):
                return scope_item.split(":", 1)[1]
        return None
    
    # Apply dependency overrides
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_workspace] = override_get_current_workspace
    
    with TestClient(app) as c:
        yield c
    
    # Clear overrides after test
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client_no_workspace(db, monkeypatch, mock_token_info_no_workspace):
    """Client with token that has no workspace scope"""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    async def override_get_current_user():
        return mock_token_info_no_workspace
    
    async def override_get_current_workspace():
        # This will trigger the "No workspace access found in token" error
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="No workspace access found in token"
        )
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_workspace] = override_get_current_workspace
    
    with TestClient(app) as c:
        yield c
    
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client_multiple_workspaces(db, monkeypatch, mock_token_info_multiple_workspaces):
    """Client with token that has multiple workspace scopes"""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    async def override_get_current_user():
        return mock_token_info_multiple_workspaces
    
    async def override_get_current_workspace():
        # Return the first workspace from the token
        scope = mock_token_info_multiple_workspaces.get("scope", "")
        for scope_item in scope.split():
            if scope_item.startswith("workspace:"):
                return scope_item.split(":", 1)[1]
        return None
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_workspace] = override_get_current_workspace
    
    with TestClient(app) as c:
        yield c
    
    app.dependency_overrides.clear()


# Helper functions for tests
@pytest.fixture
def mock_extract_workspace():
    """Mock the extract_workspace_id function"""
    with patch('src.oauth.dependencies.extract_workspace_id') as mock:
        yield mock


@pytest.fixture
def mock_extract_all_workspaces():
    """Mock the extract_all_workspace_ids function"""
    with patch('src.oauth.dependencies.extract_all_workspace_ids') as mock:
        yield mock


@pytest.fixture
def mock_oauth_service():
    """Mock the OAuthIntrospectionService"""
    with patch('src.oauth.dependencies.OAuthIntrospectionService') as MockService:
        mock_instance = AsyncMock()
        mock_instance.introspect_token = AsyncMock()
        MockService.return_value = mock_instance
        yield mock_instance


# Optional: Add a fixture for testing without any authentication overrides
@pytest.fixture
def unauth_client(db):
    """Client without authentication overrides (for testing auth failures)"""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as c:
        yield c
    
    app.dependency_overrides.clear()
    
@pytest.fixture
def create_test_wizard(db, mock_token_info):
    """Helper fixture to create test wizards"""
    def _create_wizard(
        title="Test Wizard",
        context="Test context",
        parent_id=None,
        enabled=True,
        wizard_type="answer",
        workspace_id="39354e1f-b9cc-30eb-9700-963b3a53e977"
    ):
        wizard = Wizard(
            title=title,
            context=context,
            parent_id=parent_id,
            enabled=enabled,
            wizard_type=wizard_type,
            created_by=mock_token_info["sub"],
            workspace_id=workspace_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(wizard)
        db.commit()
        db.refresh(wizard)
        return wizard
    return _create_wizard

@pytest.fixture
def create_wizard_hierarchy(db, mock_token_info):
    """Helper fixture to create a wizard hierarchy for testing"""
    def _create_hierarchy():
        workspace_id = "39354e1f-b9cc-30eb-9700-963b3a53e977"
        
        # Create root wizard
        root_wizard = Wizard(
            title="Root Wizard",
            context="Root context",
            parent_id=None,
            enabled=True,
            wizard_type="question",
            created_by=mock_token_info["sub"],
            workspace_id=workspace_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(root_wizard)
        db.flush()
        
        # Create child wizards
        child1 = Wizard(
            title="Child Wizard 1",
            context="Child 1 context",
            parent_id=root_wizard.id,
            enabled=True,
            wizard_type="answer",
            created_by=mock_token_info["sub"],
            workspace_id=workspace_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        child2 = Wizard(
            title="Child Wizard 2",
            context="Child 2 context",
            parent_id=root_wizard.id,
            enabled=True,
            wizard_type="answer",
            created_by=mock_token_info["sub"],
            workspace_id=workspace_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        db.add_all([child1, child2])
        db.commit()
        
        db.refresh(root_wizard)
        
        return {
            "root": root_wizard,
            "child1": child1,
            "child2": child2
        }
    return _create_hierarchy

@pytest.fixture
def wizard_client(db, monkeypatch, mock_token_info):
    """Client for testing wizard endpoints (no workspace dependencies needed)"""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    # Mock OAuth dependencies - wizards don't use workspace, just authentication
    async def override_get_current_user():
        return mock_token_info
    
    # Apply dependency overrides
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    # Note: Wizard endpoints don't use get_current_workspace
    
    with TestClient(app) as c:
        yield c
    
    # Clear overrides after test
    app.dependency_overrides.clear()