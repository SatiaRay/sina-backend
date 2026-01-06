import pytest
import sys, os

from test.conftest import force_patch_guard_auth
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException
import main

def create_test_token(workspace_id="test-workspace-123", user_id="user-456"):
    """Create a test JWT token with workspace scope"""
    payload = {
        "sub": user_id,
        "scopes": [f"workspace:{workspace_id}"],
        "exp": 9999999999  # Far future
    }
    
    # In real implementation, you'd use your private key
    # For testing, we'll use a dummy token
    return f"test_token_{workspace_id}_{user_id}"

# @pytest.fixture
# def client():
#     app = main.app
    
#     # Reset overrides
#     app.dependency_overrides = {}
    
#     # Create test client
#     return TestClient(app)

@pytest.fixture
def client():
    app = main.app

    # Reset overrides before tests
    app.dependency_overrides = {}

    fake_session = MagicMock()
    app.dependency_overrides[main.get_session] = lambda: fake_session

    return TestClient(app)


def test_guard_middleware_no_auth(client):
    force_patch_guard_auth(AsyncMock(return_value=False))
    response = client.get("/test")
    assert response.status_code == 401
    assert response.json() == {"msg": "Unauthorized - No token provided"}


def test_guard_middleware_invalid_auth(client):
    force_patch_guard_auth(AsyncMock(return_value=False))
    response = client.get("/test", headers={"Authorization": "Bearer bad"})
    assert response.status_code == 401
    assert response.json() == {"msg": "Unauthorized - No token provided"}


def test_guard_middleware_malformed_bearer(client):
    force_patch_guard_auth(AsyncMock(return_value=False))
    response = client.get("/test", headers={"Authorization": "Bearer"})
    assert response.status_code == 401

def test_tenant_middleware_no_token(client):
    """Test that requests without token are rejected"""
    response = client.get("/test")
    assert response.status_code == 401
    assert response.json()["msg"] == "Unauthorized - No token provided"

def test_tenant_middleware_with_workspace_token(client):
    """Test that requests with valid workspace token succeed"""
    # Mock the JWT decode to return workspace scopes
    with patch('src.util.decode_jwt_token') as mock_decode:
        mock_decode.return_value = {
            "sub": "user-123",
            "scopes": ["workspace:test-workspace-456"]
        }
        
        # We need to patch auth_validate to pass through
        import src.main as main_module
        original_auth_validate = main_module.auth_validate
        
        async def mock_auth_validate(credential):
            # Simulate successful auth
            if hasattr(credential, 'headers'):
                credential.state.scopes = ["workspace:test-workspace-456"]
                credential.state.user_id = "user-123"
            return credential
        
        # Apply the mock
        import test.conftest
        test.conftest.force_patch_guard_auth(mock_auth_validate)
        
        response = client.get("/test", headers={"Authorization": "Bearer test-token"})
        assert response.status_code == 200

def test_tenant_middleware_token_without_workspace_scope(client):
    """Test that tokens without workspace scope are rejected"""
    # Mock auth_validate to return a request WITHOUT workspace scope
    async def mock_auth_no_workspace(credential):
        if hasattr(credential, 'headers'):
            # Add scopes but NO workspace scope
            credential.state.scopes = ["read", "write"]
            credential.state.user_id = "user-123"
        return credential
    
    force_patch_guard_auth(mock_auth_no_workspace)
    
    response = client.get("/test", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 403
    assert "No workspace_id provided" in response.json()["msg"]
