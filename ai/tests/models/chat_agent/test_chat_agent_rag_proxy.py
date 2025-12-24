import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import WebSocket
from models.chat_agent.chat_agent_rag_proxy import ChatAgentRagProxy
from src.database.models import Chat, ChatHistory
from typing import List, Dict, Any, Optional, Union
from fastapi import Request

@pytest.fixture
def mock_websocket():
    websocket = Mock(spec=WebSocket)
    return websocket

@pytest.fixture
def mock_chat():
    chat = Mock(spec=Chat)
    chat.id = 1
    return chat

@pytest.fixture
def mock_chat_history():
    return [
        Mock(spec=ChatHistory, role="user", body="Hello"),
        Mock(spec=ChatHistory, role="assistant", body="Hi there!")
    ]

@pytest.fixture
def mock_workflows():
    return [
        {"id": "workflow1", "type": "start"},
        {"id": "workflow2", "type": "end"}
    ]

@pytest.fixture
def mock_chat_history_repository():
    repo = Mock()
    repo.get_chat_history_by_chat_id.return_value = [
        Mock(role="user", body="Hello"),
        Mock(role="assistant", body="Hi there!")
    ]
    return repo

@pytest.fixture
def mock_workflow_repository():
    repo = Mock()
    repo.get_active_workflows_flows.return_value = [
        {"id": "workflow1", "type": "start"},
        {"id": "workflow2", "type": "end"}
    ]
    return repo

@pytest.fixture
def chat_agent(mock_chat_history_repository, mock_workflow_repository):
    agent = ChatAgentRagProxy()
    agent.chat_history_repository = mock_chat_history_repository
    agent.workflow_repository = mock_workflow_repository
    return agent

@pytest.mark.asyncio
async def test_generate_response_socket_success_string(
    chat_agent,
    mock_websocket,
    mock_chat,
    mock_chat_history,
    mock_workflows,
    mock_chat_history_repository,
    mock_workflow_repository
):
    # Arrange
    question = {
        'type': 'text',
        'body': "What is the weather?"
    }
    # expected_response = "AI response"
    expected_response = {
        'type': 'text',
        'body': "AI response"
    }
    
    # Setup agent rag proxy    
    agent_proxy = ChatAgentRagProxy()
    agent_proxy.chat_history_repository = mock_chat_history_repository
    agent_proxy.workflow_repository = mock_workflow_repository
    
    # Mock agent
    async def mock_generate_response_sokcet():
        return expected_response
    agent = Mock()
    agent.generate_response_socket = mock_generate_response_sokcet
    
    # update chat mock
    def mock_update_chat(
        message: Union[dict, str, list[str]],
        role: str,
        request: Optional[Request] = None,
        websocket: Optional[WebSocket] = None,
        hidden=False
    ) :
        assert (message == question and role == 'user') or (message == expected_response and role == 'assistant')
    
    with patch.object(agent_proxy, 'update_chat_history', mock_update_chat),\
        patch.object(agent_proxy, 'agent_factory', return_value=agent):
        await agent_proxy.generate_response_socket(question, mock_websocket)

@pytest.mark.asyncio
async def test_update_chat_history_string(chat_agent, mock_chat):
    # Arrange
    message = "Test message"
    role = "user"
    chat_agent._ChatAgentRagProxy__get_chat = Mock(return_value=mock_chat)
    
    # Act
    chat_agent.update_chat_history(message, role)
    
    # Assert
    chat_agent.chat_history_repository.create.assert_called_once_with({
        "chat_id": mock_chat.id,
        "body": message,
        "role": role,
        "hidden": False,
        "type": 'text'
    })