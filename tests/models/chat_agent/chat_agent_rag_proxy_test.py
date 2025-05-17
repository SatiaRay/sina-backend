import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request, WebSocket
from starlette.datastructures import Headers, QueryParams

import sys
print(sys.path)

from database.models import Chat
from models.chat_agent.chat_agent_rag_proxy import ChatAgentRagProxy


@pytest.fixture
def mock_db_session():
    """Mocked SQLAlchemy session."""
    return MagicMock()


@pytest.fixture
def proxy(mock_db_session):
    """Returns a proxy instance with mocked DB and services."""
    return ChatAgentRagProxy(db_session=mock_db_session)


@pytest.fixture
def mock_chat():
    """Returns a mocked Chat object."""
    return Chat(id=1)


@pytest.fixture
def mock_http_request():
    """Mock an HTTP request with session ID in cookies."""
    request = MagicMock(spec=Request)
    request.cookies = {"session_id": "1"}
    return request


@pytest.fixture
def mock_websocket():
    """Mock a WebSocket connection with session ID in query parameters."""
    websocket = MagicMock(spec=WebSocket)
    websocket.query_params = QueryParams({"session_id": "1"})
    return websocket


@patch("models.chat_agent.chat_agent_rag_proxy.generate_response", return_value={"answer": "Hello!"})
def test_generate_response_http(mock_generate, proxy, mock_http_request, mock_chat):
    # Patch internal methods to avoid real DB interaction
    print('before mock')
    proxy._ChatAgentRagProxy__get_chat = MagicMock(return_value=mock_chat)
    proxy._ChatAgentRagProxy__update_chat_history = MagicMock()
    print('after mock')

    response = pytest.run(proxy.generate_response("Hi", request=mock_http_request))
    assert isinstance(response, dict)
    assert "answer" in response
    proxy._ChatAgentRagProxy__update_chat_history.assert_called()


@patch("models.chat_agent.chat_agent_rag_proxy.generate_response_socket", return_value={"answer": "Socket hello!"})
@pytest.mark.asyncio
async def test_generate_response_socket(mock_generate, proxy, mock_websocket, mock_chat):
    proxy._ChatAgentRagProxy__get_chat = MagicMock(return_value=mock_chat)
    proxy._ChatAgentRagProxy__update_chat_history = MagicMock()

    response = await proxy.generate_response_socket("Hi socket", websocket=mock_websocket)
    assert isinstance(response, dict)
    assert response["answer"] == "Socket hello!"
    proxy._ChatAgentRagProxy__update_chat_history.assert_called()


def test_get_session_id_http(proxy, mock_http_request):
    session_id = proxy._ChatAgentRagProxy__get_session_id(request=mock_http_request)
    assert session_id == 1


def test_get_session_id_websocket(proxy, mock_websocket):
    session_id = proxy._ChatAgentRagProxy__get_session_id(websocket=mock_websocket)
    assert session_id == 1


def test_get_session_id_error(proxy):
    with pytest.raises(ValueError):
        proxy._ChatAgentRagProxy__get_session_id()
