import pytest
import sys, os
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


def override_auth_fail():
    async def _override():
        raise HTTPException(status_code=401, detail="Unauthorized")
    return _override

def override_auth_success(user=None):
    async def _override():
        return user or {"user_id": "123"}
    return _override


def test_guard_middleware_no_auth(client):
    main.app.dependency_overrides[main.auth_dependency] = override_auth_fail()

    response = client.get("/test")
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_guard_middleware_invalid_auth(client):
    main.app.dependency_overrides[main.auth_dependency] = override_auth_fail()

    response = client.get("/test", headers={"Authorization": "Bearer bad"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_guard_middleware_valid_auth(client):
    request_state_mock = MagicMock()
    main.app.dependency_overrides[main.auth_dependency] = override_auth_success()

    response = client.get("/test", headers={"Authorization": "Bearer good"})
    assert response.status_code == 200
    assert response.json() == {"msg": "The service is up !"}


def test_guard_middleware_malformed_bearer(client):
    main.app.dependency_overrides[main.auth_dependency] = override_auth_fail()

    response = client.get("/test", headers={"Authorization": "Bearer"})
    assert response.status_code == 401
