from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional, List, Dict
import json
from models.chat_agent.chat_agent_rag_proxy import ChatAgentRagProxy
from util.logging_config import configure_logging, log_error
import wave
import os
from models.models.speech_to_text_model import SpeechToTextModel
from models.models.google_speech_to_text_model import GoogleSpeechToTextModel
import matplotlib.pyplot as plt
import io
import uuid

# Configure loggers
main_logger, error_logger, api_logger = configure_logging()

# Initialize the router
router = APIRouter(prefix="", tags=["AI"])

# Initialize the chat agent
agent_rag = ChatAgentRagProxy()

# Initialze the speech to text model
# speech_to_text_model = SpeechToTextModel()
speech_to_text_model = GoogleSpeechToTextModel()

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

            if response:
                await websocket.send_json({
                    "event" : "finished",
                    "msg" : "Response generated complete",
                })

            if isinstance(response, dict) and response.get("status") == "error":
                await websocket.send_text(f"Error: {response.get('error')}")

    except WebSocketDisconnect:
        api_logger.info("WebSocket disconnected")
    except Exception as e:
        log_error(error_logger, e, f"Failed while processing: {str(e)}")
        await websocket.send_text(f"Error: {str(e)}")
    finally:
        await websocket.close()

@router.websocket("/ws/voice")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connected")

    try:
        while True:
            try:
                data = await websocket.receive_bytes()
            except WebSocketDisconnect:
                print("WebSocket disconnected")
                break

            filename = f"received_{uuid.uuid4().hex}.webm"
            filepath = os.path.join('temp', filename)

            # Ensure the directory exists
            os.makedirs('temp', exist_ok=True)

            try:
                with open(filepath, "wb") as f:
                    f.write(data)

                await websocket.send_json({"event": "transcribing", "msg": "در حال تبدیل صدا به متن."})

                # Transcribe using Whisper
                trans = speech_to_text_model.transcribe(filepath)

                await websocket.send_text(trans)

            except Exception as e:
                print(f"Error: {e}")
                await websocket.send_text(f"Error: {e}")

            finally:
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except Exception as cleanup_error:
                    print(f"Cleanup error: {cleanup_error}")
    except Exception as e:
        print(f"Outer error: {e}")
        await websocket.send_text(f"Error: {e}")
