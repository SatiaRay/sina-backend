from fastapi import (
    APIRouter,
    Depends,
    WebSocket,
    WebSocketDisconnect,
    Query,
    HTTPException,
)
from typing import Optional, List, Dict
from enum import Enum
import json
from pydantic import BaseModel, Field
from models.chat_agent.chat_agent_rag_proxy import ChatAgentRagProxy
from util.logging_config import configure_logging, log_error
import wave
import os
from models.models.speech_to_text_model import SpeechToTextModel
import matplotlib.pyplot as plt
import io
import httpx

from sqlalchemy.orm import Session
from database.models import get_db
from database.repository import (
    DocumentRepository,
    WorkflowRepository,
    InstructionRepository,
)

# Configure loggers
main_logger, error_logger, api_logger = configure_logging()

# Initialize the router
router = APIRouter(prefix="/voice_agent", tags=["Voice Agent"])


class InstructionResponse(BaseModel):
    instruction: str

class OpenAIModel(str, Enum):
    GPT4_REALTIME_2025 = "gpt-4o-realtime-preview-2025-06-03"
    GPT4_REALTIME_2024 = "gpt-4o-realtime-preview-2024-12-17"
    GPT4_MINI_REALTIME_2024 = "gpt-4o-mini-realtime-preview-2024-12-17"


# get voice agent instruction
@router.get("/instruction", response_model=InstructionResponse)
def get_instruction(db: Session = Depends(get_db)):
    """
    Fetch all documents, workflows, and instructions with agent_type equal to 'voice_agent' or 'both',
    then combine them into a well-structured instruction string using prompt engineering principles.
    """
    try:
        # Initialize repositories
        document_repo = DocumentRepository(db)
        workflow_repo = WorkflowRepository(db)
        instruction_repo = InstructionRepository(db)

        # Fetch data for voice agent
        voice_agent_type = "voice_agent"

        # Get documents for voice agent
        voice_documents = document_repo.get_by_agent_type(voice_agent_type)

        # Get workflows for voice agent
        voice_workflows = workflow_repo.get_active_workflows(voice_agent_type)

        # Get instructions for voice agent
        voice_instructions = instruction_repo.get_by_agent_type(voice_agent_type)

        # Build comprehensive instruction using prompt engineering principles
        instruction_parts = []

        # 1. System Context and Role Definition
        instruction_parts.append("## VOICE AGENT SYSTEM INSTRUCTIONS")
        instruction_parts.append(
            "You are an intelligent voice assistant designed to help users through voice interactions."
        )
        instruction_parts.append(
            "Your responses should be natural, conversational, and optimized for voice communication."
        )
        instruction_parts.append("")

        # 2. Core Behavioral Guidelines
        instruction_parts.append("### CORE BEHAVIORAL GUIDELINES")
        instruction_parts.append("- Speak clearly and at a natural pace")
        instruction_parts.append(
            "- Use conversational language appropriate for voice interaction"
        )
        instruction_parts.append("- Provide concise but complete responses")
        instruction_parts.append("- Ask clarifying questions when needed")
        instruction_parts.append("- Confirm important actions before executing them")
        instruction_parts.append("")

        # 3. Available Knowledge Base (Documents)
        if voice_documents:
            instruction_parts.append("### AVAILABLE KNOWLEDGE BASE")
            instruction_parts.append(
                "You have access to the following documents and information:"
            )
            for doc in voice_documents:
                try:
                    title = getattr(doc, "title", None)
                    if title:
                        instruction_parts.append(f"- {title}")
                        markdown = getattr(doc, "markdown", None)
                        if markdown:
                            instruction_parts.append(f"  Content: {markdown}")
                except Exception:
                    continue
            instruction_parts.append("")

        # 4. Available Workflows
        if voice_workflows:
            instruction_parts.append("### AVAILABLE WORKFLOWS")
            instruction_parts.append("You can execute the following workflows:")
            for workflow in voice_workflows:
                try:
                    name = getattr(workflow, "name", "Unknown Workflow")
                    instruction_parts.append(f"- {name}")
                    flow = getattr(workflow, "flow", None)
                    if flow:
                        instruction_parts.append(f"  Flow: {str(flow)}")
                except Exception:
                    continue
            instruction_parts.append("")

        # 5. Specific Instructions
        if voice_instructions:
            instruction_parts.append("### SPECIFIC INSTRUCTIONS")
            for instruction in voice_instructions:
                try:
                    label = getattr(instruction, "label", None)
                    text = getattr(instruction, "text", None)
                    if label and text:
                        instruction_parts.append(f"**{label}:**")
                        instruction_parts.append(f"{text}")
                        instruction_parts.append("")
                except Exception:
                    continue

        # 6. Voice-Specific Optimization Guidelines
        instruction_parts.append("### VOICE INTERACTION OPTIMIZATION")
        instruction_parts.append(
            "- Use shorter sentences and simpler vocabulary for better voice comprehension"
        )
        instruction_parts.append("- Provide step-by-step guidance for complex tasks")
        instruction_parts.append(
            "- Use natural speech patterns and avoid robotic responses"
        )
        instruction_parts.append(
            "- Include appropriate pauses and transitions in your responses"
        )
        instruction_parts.append("- Be patient and repeat information when necessary")
        instruction_parts.append("")

        # 7. Error Handling and Fallbacks
        instruction_parts.append("### ERROR HANDLING")
        instruction_parts.append(
            "- If you don't understand a request, ask for clarification"
        )
        instruction_parts.append("- If a workflow fails, provide alternative solutions")
        instruction_parts.append(
            "- Always confirm before performing destructive actions"
        )
        instruction_parts.append("- Provide helpful error messages in natural language")
        instruction_parts.append("")

        # 8. Context Awareness
        instruction_parts.append("### CONTEXT AWARENESS")
        instruction_parts.append(
            "- Remember previous interactions within the same session"
        )
        instruction_parts.append(
            "- Adapt your communication style based on user preferences"
        )
        instruction_parts.append("- Maintain conversation flow and coherence")
        instruction_parts.append("")

        # Combine all parts into a single instruction string
        complete_instruction = "\n".join(instruction_parts)

        return InstructionResponse(instruction=complete_instruction)

    except Exception as e:
        api_logger.error(f"Error generating voice agent instruction: {str(e)}")
        error_logger.error(f"Error generating voice agent instruction: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to generate voice agent instruction"
        )

OPENAI_API_URL = "https://api.openai.com/v1/realtime/sessions"

# Use query parameters instead of a body for GET
@router.get("/client_key")
async def get_client_key(model: OpenAIModel = OpenAIModel.GPT4_REALTIME_2025):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            # Forward model as a query param to OpenAI
            response = await client.post(
                OPENAI_API_URL,
                headers=headers,
                json={"model": model.value}
            )
            response.raise_for_status()
            data = response.json()
            if 'client_secret' not in data:
                raise HTTPException(status_code=500, detail="OpenAI response missing client_secret")
            return data['client_secret']
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=e.response.json()
            )
