import pytest
import sys, os

from test.conftest import force_patch_guard_auth
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
from fastapi import HTTPException
import main

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
    assert response.json() == {"msg": "Unauthorized"}


def test_guard_middleware_invalid_auth(client):
    force_patch_guard_auth(AsyncMock(return_value=False))
    response = client.get("/test", headers={"Authorization": "Bearer bad"})
    assert response.status_code == 401
    assert response.json() == {"msg": "Unauthorized"}


def test_guard_middleware_valid_auth(client):
    mock_request = MagicMock()
    force_patch_guard_auth(AsyncMock(return_value=mock_request))
    response = client.get("/test", headers={"Authorization": "Bearer good"})
    assert response.status_code == 200
    assert response.json() == {"msg": "The service is up !"}


def test_guard_middleware_malformed_bearer(client):
    force_patch_guard_auth(AsyncMock(return_value=False))
    response = client.get("/test", headers={"Authorization": "Bearer"})
    assert response.status_code == 401
