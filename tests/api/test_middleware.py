import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from api.main import app

def setup_test_endpoint():
    @app.get("/test-vectorstore")
    async def test_vectorstore_endpoint(request: Request):
        # This endpoint will return the current vector_store's tenant and database
        from provider.service_container import container
        vector_store = container.make('vector_store')
        return JSONResponse({
            "tenant": getattr(vector_store, 'tenant', None),
            "database": getattr(vector_store, 'database', None)
        })

setup_test_endpoint()

@pytest.fixture
def client():
    return TestClient(app)

@patch("api.main.VectorStore")
@patch("database.models.SessionLocal")
def test_middleware_valid_token(mock_sessionlocal, mock_vectorstore, client):
    # Mock DB session and AiBot lookup
    mock_db = MagicMock()
    mock_sessionlocal.return_value = mock_db
    mock_aibot = MagicMock()
    mock_workspace = MagicMock()
    mock_workspace.name = "test_workspace"
    mock_aibot.workspace = mock_workspace
    mock_aibot.name = "test_bot"
    mock_db.query().filter().first.return_value = mock_aibot

    # Mock VectorStore instantiation
    instance = MagicMock()
    mock_vectorstore.return_value = instance
    instance.tenant = "test_workspace"
    instance.database = "test_bot"

    headers = {"X-BOT-TOKEN": "valid-token"}
    response = client.get("/test-vectorstore", headers=headers)
    data = response.json()
    assert data["tenant"] == "test_workspace"
    assert data["database"] == "test_bot"
    mock_vectorstore.assert_called_with(tenant="test_workspace", database="test_bot")

@patch("api.main.VectorStore")
def test_middleware_invalid_token(mock_vectorstore, client):
    # Simulate no AiBot found
    with patch("database.models.SessionLocal") as mock_sessionlocal:
        mock_db = MagicMock()
        mock_sessionlocal.return_value = mock_db
        mock_db.query().filter().first.return_value = None

        instance = MagicMock()
        mock_vectorstore.return_value = instance
        instance.tenant = "default_tenant"
        instance.database = "default_db"

        headers = {"X-BOT-TOKEN": "invalid-token"}
        response = client.get("/test-vectorstore", headers=headers)
        data = response.json()
        # Should fallback to default
        assert mock_vectorstore.call_args is not None
        assert mock_vectorstore.call_args[1] == {}  # Called with no args

@patch("api.main.VectorStore")
def test_middleware_no_token(mock_vectorstore, client):
    # No token header at all
    instance = MagicMock()
    mock_vectorstore.return_value = instance
    instance.tenant = "default_tenant"
    instance.database = "default_db"

    response = client.get("/test-vectorstore")
    data = response.json()
    # Should fallback to default
    assert mock_vectorstore.call_args is not None
    assert mock_vectorstore.call_args[1] == {}  # Called with no args 