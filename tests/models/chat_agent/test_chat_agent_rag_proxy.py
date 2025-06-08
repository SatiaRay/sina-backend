import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import WebSocket
from models.chat_agent.chat_agent_rag_proxy import ChatAgentRagProxy
from database.models import Chat, ChatHistory

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
    repo.get_active_workflows_schemas.return_value = [
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
    question = "What is the weather?"
    expected_response = "AI response"
    
    # Mock the internal methods
    chat_agent._ChatAgentRagProxy__get_chat = Mock(return_value=mock_chat)
    chat_agent._ChatAgentRagProxy__update_chat_history = Mock()
    mock_chat_history_repository.get_chat_history_by_chat_id.return_value = mock_chat_history
    
    # Mock ChatAgentRag
    with patch('models.chat_agent.chat_agent_rag_proxy.ChatAgentRag') as mock_rag_class:
        mock_rag_instance = AsyncMock()
        mock_rag_instance.generate_response_socket.return_value = expected_response
        mock_rag_class.return_value = mock_rag_instance
        
        # Act
        response = await chat_agent.generate_response_socket(question, mock_websocket)
        
        # Assert
        # 1. Verify chat history was updated with user question
        chat_agent._ChatAgentRagProxy__update_chat_history.assert_any_call(
            question, "user", websocket=mock_websocket
        )
        
        # 2. Verify ChatAgentRag was initialized with correct parameters
        mock_rag_class.assert_called_once_with(
            question=question,
            history=[{"role": msg.role, "body": msg.body} for msg in mock_chat_history],
            websocket=mock_websocket,
            workflows=mock_workflows,
            db=chat_agent.db
        )
        
        # 3. Verify generate_response_socket was called
        mock_rag_instance.generate_response_socket.assert_called_once()
        
        # 4. Verify chat history was updated with AI response
        chat_agent._ChatAgentRagProxy__update_chat_history.assert_any_call(
            expected_response, role="assistant", websocket=mock_websocket
        )
        
        # 5. Verify the response was returned in the correct format
        assert response == {
            "status": "success",
            "response": expected_response
        }

@pytest.mark.asyncio
async def test_generate_response_socket_success_list(
    chat_agent,
    mock_websocket,
    mock_chat,
    mock_chat_history,
    mock_workflows,
    mock_chat_history_repository,
    mock_workflow_repository
):
    # Arrange
    question = "What is the weather?"
    expected_response = ["First response", "Second response"]
    
    # Mock the internal methods
    chat_agent._ChatAgentRagProxy__get_chat = Mock(return_value=mock_chat)
    chat_agent._ChatAgentRagProxy__update_chat_history = Mock()
    mock_chat_history_repository.get_chat_history_by_chat_id.return_value = mock_chat_history
    
    # Mock ChatAgentRag
    with patch('models.chat_agent.chat_agent_rag_proxy.ChatAgentRag') as mock_rag_class:
        mock_rag_instance = AsyncMock()
        mock_rag_instance.generate_response_socket.return_value = expected_response
        mock_rag_class.return_value = mock_rag_instance
        
        # Act
        response = await chat_agent.generate_response_socket(question, mock_websocket)
        
        # Assert
        # 1. Verify chat history was updated with user question
        chat_agent._ChatAgentRagProxy__update_chat_history.assert_any_call(
            question, "user", websocket=mock_websocket
        )
        
        # 2. Verify ChatAgentRag was initialized with correct parameters
        mock_rag_class.assert_called_once_with(
            question=question,
            history=[{"role": msg.role, "body": msg.body} for msg in mock_chat_history],
            websocket=mock_websocket,
            workflows=mock_workflows,
            db=chat_agent.db
        )
        
        # 3. Verify generate_response_socket was called
        mock_rag_instance.generate_response_socket.assert_called_once()
        
        # 4. Verify chat history was updated with each AI response
        for resp in expected_response:
            chat_agent._ChatAgentRagProxy__update_chat_history.assert_any_call(
                resp, role="assistant", websocket=mock_websocket
            )
        
        # 5. Verify the response was returned in the correct format
        assert response == {
            "status": "success",
            "response": expected_response
        }

@pytest.mark.asyncio
async def test_generate_response_socket_error(
    chat_agent,
    mock_websocket,
    mock_chat
):
    # Arrange
    question = "What is the weather?"
    error_message = "Something went wrong"
    
    # Mock the internal methods
    chat_agent._ChatAgentRagProxy__get_chat = Mock(return_value=mock_chat)
    chat_agent._ChatAgentRagProxy__update_chat_history = Mock()
    
    # Mock ChatAgentRag to raise an exception
    with patch('models.chat_agent.chat_agent_rag_proxy.ChatAgentRag') as mock_rag_class:
        mock_rag_instance = AsyncMock()
        mock_rag_instance.generate_response_socket.side_effect = Exception(error_message)
        mock_rag_class.return_value = mock_rag_instance
        
        # Act
        response = await chat_agent.generate_response_socket(question, mock_websocket)
        
        # Assert
        # Verify error was handled and chat history was updated with error message
        chat_agent._ChatAgentRagProxy__update_chat_history.assert_any_call(
            f"Error: {error_message}", role="assistant", websocket=mock_websocket
        )
        
        # Verify error response was returned
        assert response == {
            "status": "error",
            "error": error_message
        }

@pytest.mark.asyncio
async def test_update_chat_history_string(chat_agent, mock_chat):
    # Arrange
    message = "Test message"
    role = "user"
    chat_agent._ChatAgentRagProxy__get_chat = Mock(return_value=mock_chat)
    
    # Act
    chat_agent._ChatAgentRagProxy__update_chat_history(message, role)
    
    # Assert
    chat_agent.chat_history_repository.create.assert_called_once_with({
        "chat_id": mock_chat.id,
        "body": message,
        "role": role
    })

@pytest.mark.asyncio
async def test_update_chat_history_list(chat_agent, mock_chat):
    # Arrange
    messages = ["First message", "Second message"]
    role = "assistant"
    chat_agent._ChatAgentRagProxy__get_chat = Mock(return_value=mock_chat)
    
    # Act
    chat_agent._ChatAgentRagProxy__update_chat_history(messages, role)
    
    # Assert
    assert chat_agent.chat_history_repository.create.call_count == 2
    
    # Verify each message was stored separately
    calls = chat_agent.chat_history_repository.create.call_args_list
    assert calls[0][0][0] == {
        "chat_id": mock_chat.id,
        "body": messages[0],
        "role": role
    }
    assert calls[1][0][0] == {
        "chat_id": mock_chat.id,
        "body": messages[1],
        "role": role
    } 