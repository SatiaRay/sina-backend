import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from models.chat_agent.chat_agent_rag import ChatAgentRag, SATIA_INSTRUCTIONS
from database.models import Instruction
from database.repository import InstructionRepository

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

@pytest.fixture(scope="function")
def chat_agent(db):
    """Create a ChatAgentRag instance with test database session"""
    return ChatAgentRag(db=db)

def test_active_instructions_append_to_prompt(chat_agent, test_instruction):
    """Test that active instructions are properly appended to the static instructions"""
    # Get active instructions
    active_instructions = chat_agent._get_active_instructions()
    
    # Verify the format of active instructions
    assert "# Active Instructions from Database" in active_instructions
    assert f"## {TEST_INSTRUCTION['label']}" in active_instructions
    
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
    assert "## First Instruction" in active_instructions
    assert "## Second Instruction" in active_instructions
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