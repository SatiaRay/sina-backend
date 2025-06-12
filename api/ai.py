from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import asyncio
from typing import Optional, List, Dict
import json
from models.chat_agent.chat_agent_rag_proxy import ChatAgentRagProxy
from util.logging_config import configure_logging, log_error
import wave
import numpy as np
import datetime
import os
from models.models.speech_to_text_model import SpeechToTextModel
import matplotlib.pyplot as plt
import io
from pydub import AudioSegment
import uuid

# Configure loggers
main_logger, error_logger, api_logger = configure_logging()

# Initialize the router
router = APIRouter(prefix="", tags=["AI"])

# Initialize the chat agent
agent_rag = ChatAgentRagProxy()

# Initialze the speech to text model
speech_to_text_model = SpeechToTextModel()

@router.websocket("/ws/ask")
async def ask_question_agent_socket(
    websocket: WebSocket, 
    session_id: str = Query(..., description="Session ID is required"),
):
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_text()
            question_data = json.loads(data)
            question = question_data.get("question", "")

            if not question:
                await websocket.send_text("Error: No question provided.")
                continue

            api_logger.info(f"Processing question with agent: {question}")

            response = await agent_rag.generate_response_socket(
                question=question,
                websocket=websocket
            )

            if isinstance(response, dict) and response.get("status") == "error":
                await websocket.send_text(f"Error: {response.get('error')}")

    except WebSocketDisconnect:
        api_logger.info("WebSocket disconnected")
    except Exception as e:
        log_error(error_logger, e, f"Failed while processing: {str(e)}")
        await websocket.send_text(f"Error: {str(e)}")
    finally:
        await websocket.close()

AUDIO_SAVE_DIR = "audios"

@router.websocket("/ws/voice")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        print("WebSocket connected")
        data = await websocket.receive_bytes()

        filename = f"received_{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(AUDIO_SAVE_DIR, filename)

        with open(filepath, "wb") as f:
            f.write(data)

        print(f"Saved MP3: {filepath}")

        # Transcribe using Whisper
        trans = speech_to_text_model.transcribe(filepath)
        print("Transcription:", trans)

    except Exception as e:
        print(f"Error: {e}")
