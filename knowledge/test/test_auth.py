import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from test.test_util import force_patch_guard_auth

from main import app, guard_middleware

client = TestClient(app)

def test_guard_middleware_no_auth():
    force_patch_guard_auth(AsyncMock(return_value=False))
    response = client.get('/test')
    assert response.status_code == 401
    assert response.json() == {"msg": "Unauthorized"}

def test_guard_middleware_invalid_auth():
    force_patch_guard_auth(AsyncMock(return_value=False))
    headers = {"Authorization": "Bearer badtoken"}
    response = client.get('/test', headers=headers)
    assert response.status_code == 401
    assert response.json() == {"msg": "Unauthorized"}

def test_guard_middleware_valid_auth():
    mock_request = MagicMock()
    force_patch_guard_auth(AsyncMock(return_value=mock_request))
    headers = {"Authorization": "Bearer goodtoken"}
    response = client.get('/test', headers=headers)
    assert response.status_code == 200
    assert response.json() == {"msg": "The service is up !"}

def test_guard_middleware_malformed_bearer():
    force_patch_guard_auth(AsyncMock(return_value=False))
    headers = {"Authorization": "Bearer"}  # Missing token
    response = client.get('/test', headers=headers)
    assert response.status_code == 401