import pytest
from src.ai_agent.chat_agent.chat_agent_rag import ChatAgentRag
from src.database.repository import InstructionRepository
from unittest.mock import Mock, AsyncMock, patch
from fastapi import WebSocket
import asyncio

# Test data
TEST_INSTRUCTION = {
    "label": "Test Instruction",
    "text": "This is a test instruction line 1\nThis is a test instruction line 2",
    "status": True
}

@pytest.fixture(scope="function")
def test_instruction(db):
    """Create a test instruction in the database"""
    repo = InstructionRepository(db)
    instruction = repo.create(TEST_INSTRUCTION)
    return instruction

@pytest.fixture
def mock_websocket():
    websocket = Mock(spec=WebSocket)
    websocket.send_json = AsyncMock()
    websocket.send_text = AsyncMock()
    return websocket

@pytest.fixture
def mock_chat_history_repository():
    return [{
        "role": "user",
        "body": "Hello"
    }, {
        "role": "assistant",
        "body": "Hi there!"
    }]

@pytest.fixture(scope="function")
def chat_agent(db, mock_websocket, mock_chat_history_repository):
    """Create a ChatAgentRag instance with test database session"""
    return ChatAgentRag(question="test question", db=db, websocket=mock_websocket,history=mock_chat_history_repository)

def test_active_instructions_append_to_prompt(chat_agent, test_instruction):
    """Test that active instructions are properly appended to the static instructions"""
    # Get active instructions
    active_instructions = chat_agent._get_active_instructions()
    
    # Verify the format of active instructions
    assert "# Active Instructions from Database" in active_instructions
    
    # Verify each line of the instruction has the correct prefix
    instruction_lines = active_instructions.split("\n")
    for line in instruction_lines:
        if line.strip() and not line.startswith("#"):
            assert line.startswith("* "), f"Line should start with '* ': {line}"
    
    # Verify the content of the instruction
    assert "* This is a test instruction line 1" in active_instructions
    assert "* This is a test instruction line 2" in active_instructions

def test_no_active_instructions(chat_agent, db):
    """Test behavior when there are no active instructions"""
    # Create an inactive instruction
    repo = InstructionRepository(db)
    inactive_instruction = {
        "label": "Inactive Instruction",
        "text": "This instruction should not appear",
        "status": False
    }
    repo.create(inactive_instruction)
    
    # Get active instructions
    active_instructions = chat_agent._get_active_instructions()
    
    # Verify no instructions are returned
    assert active_instructions == ""

def test_multiple_active_instructions(chat_agent, db):
    """Test handling of multiple active instructions"""
    # Create multiple active instructions
    repo = InstructionRepository(db)
    instructions = [
        {
            "label": "First Instruction",
            "text": "First instruction content",
            "status": True
        },
        {
            "label": "Second Instruction",
            "text": "Second instruction content",
            "status": True
        }
    ]
    
    for instruction in instructions:
        repo.create(instruction)
    
    # Get active instructions
    active_instructions = chat_agent._get_active_instructions()
    
    # Verify all instructions are included
    assert "* First instruction content" in active_instructions
    assert "* Second instruction content" in active_instructions

def test_instruction_formatting(chat_agent, db):
    """Test that instructions are properly formatted with asterisks"""
    # Create an instruction with multiple lines
    repo = InstructionRepository(db)
    multi_line_instruction = {
        "label": "Multi-line Instruction",
        "text": "Line 1\nLine 2\nLine 3",
        "status": True
    }
    repo.create(multi_line_instruction)
    
    # Get active instructions
    active_instructions = chat_agent._get_active_instructions()
    
    # Verify each line has the correct prefix
    assert "* Line 1" in active_instructions
    assert "* Line 2" in active_instructions
    assert "* Line 3" in active_instructions
    
    # Verify the lines are properly separated
    lines = active_instructions.split("\n")
    instruction_lines = [line for line in lines if line.startswith("* ")]
    assert len(instruction_lines) == 3, "Should have exactly 3 instruction lines"
    
@patch('models.chat_agent.chat_agent_rag.ChatAgentRag._suplly_called_function')
@pytest.mark.asyncio
async def test_generate_response_socket_with_function_call(mock_suplly_func, chat_agent, mock_websocket):
    async def fake_stream_event_handler(self, stream, broadcast_response_to_websocket):
        return {
            "call_info": {
                "type": "function_call",
                "id" : 'call_123',
                "call_id": 'call_123',
                "name": 'test_function',
                "arguments": '{"arg1": "value1"}',
            },
            "text": ""
        }

    # Create a dummy coroutine to simulate the response
    async def mock_sub_response():
        return "Function result"

    # mock_suplly_func.return_value = asyncio.create_task(mock_sub_response())
    mock_suplly_func.return_value = "Function result"

    with patch('models.chat_agent.chat_agent_rag.ChatAgentRag._stream_event_handler', new=fake_stream_event_handler):
        response = await chat_agent.generate_response_socket()
        
        assert response == "Function result"

@pytest.mark.asyncio
async def test_generate_response_socket_with_text_response(chat_agent, mock_websocket):
    """Test generate_response_socket with a regular text response"""
    # Mock the OpenAI client response
    with patch('models.chat_agent.chat_agent_rag.ChatAgentRag._stream_event_handler') as mock_stream:
        mock_stream.return_value = {
            "call_info": None,
            "text": "Hello, this is a test response"
        }
        
        # Act
        response = await chat_agent.generate_response_socket()
        
        # Assert
        assert response == "Hello, this is a test response"

@pytest.mark.asyncio
async def test_generate_response_socket_with_error(chat_agent, mock_websocket):
    """Test generate_response_socket when an error occurs"""
    with patch('models.chat_agent.chat_agent_rag.ChatAgentRag._stream_event_handler') as mock_stream:
        mock_stream.side_effect = Exception("Test error")
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await chat_agent.generate_response_socket()
        
        assert str(exc_info.value) == "Test error" 