from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.database.models import Chat, ChatHistory, get_db
from datetime import datetime
from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Query,
    HTTPException,
    UploadFile,
    File,
)
import json
from src.ai_agent.chat_agent.chat_agent_rag_proxy import ChatAgentRagProxy
from src.util.logging_config import configure_logging, log_error
import os
from src.ai_agent.speech_to_text_agent import SpeechToTextAgent
from src.ai_agent.google_speech_to_text_agent import GoogleSpeechToTextAgent
import uuid
from dynaconf import Dynaconf
from pathlib import Path

router = APIRouter()

# Configure loggers
main_logger, error_logger, api_logger, _ = configure_logging()

# Initialize the router
router = APIRouter(prefix="", tags=["AI"])

# Initialize the chat agent
agent_rag = ChatAgentRagProxy()

# Initialze the speech to text model
speech_to_text_agent = None

class ChatHistoryResponse(BaseModel):
    id: int
    chat_id: int
    role: str
    body: str
    type: str
    created_at: datetime

@router.get("/chat/history/{session_id}", response_model=List[ChatHistoryResponse], tags=["Chat"],
          summary="دریافت تاریخچه چت",
          description="این اندپوینت تاریخچه چت را بر اساس شناسه جلسه برمی‌گرداند")
async def get_chat_history(
    session_id: str,
    limit: Optional[int] = Query(default=20, ge=1, le=100),
    offset: Optional[int] = Query(default=0, ge=0),
    db: Session = Depends(get_db)
):
    """
    دریافت تاریخچه چت بر اساس شناسه جلسه
    
    (توجه)پیام های پنهان را باز نمیگرداند
    
    - **session_id**: شناسه جلسه چت
    - **limit**: تعداد پیام‌های مورد نظر (پیش‌فرض: 20)
    - **offset**: تعداد پیام‌های رد شده (پیش‌فرض: 0)
    
    **نمونه خروجی:**
    ```json
    [
      {
        "id": 1,
        "chat_id": 123,
        "role": "user",
        "body": "سلام",
        "created_at": "2024-03-20T10:30:00"
      },
      {
        "id": 2,
        "chat_id": 123,
        "role": "assistant",
        "body": "سلام! چطور می‌توانم کمک کنم؟",
        "created_at": "2024-03-20T10:30:05"
      }
    ]
    ```
    """
    # First find the chat by session_id
    chat = db.query(Chat).filter(Chat.session_id == session_id).first()
    
    if not chat:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "تاریخچه چت یافت نشد",
                "session_id": session_id
            }
        )
    
    try:
        # Then get the chat history for this chat with offset
        history = db.query(ChatHistory)\
            .filter(ChatHistory.chat_id == chat.id)\
            .filter(ChatHistory.hidden != True)\
            .order_by(ChatHistory.created_at.desc())\
            .offset(int(offset))\
            .limit(int(limit))\
            .all()
        
        if not history:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "تاریخچه چت یافت نشد",
                    "session_id": session_id,
                    "chat_id": chat.id,
                    "offset": offset
                }
            )
        
        # Convert to response model
        return [
            ChatHistoryResponse(
                id=msg.id,
                chat_id=msg.chat_id,
                role=msg.role,
                body=msg.body,
                type=msg.type,
                created_at=msg.created_at
            )
            for msg in history
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "خطا در دریافت تاریخچه چت",
                "error": str(e)
            }
        )


def get_voice_to_text_model():

    settings_file = Path(__file__).parent.parent / "data" / "system_settings.json"

    settings = Dynaconf(settings_files=[str(settings_file)], lowercase_read=True)

    try:
        match settings.voice_to_text_service:
            case "openai":
                return SpeechToTextAgent()
            case "google":
                return GoogleSpeechToTextAgent()
            case _:
                return None
    except Exception as e:
        api_logger.info(f"Get voice to text service error {str(e)}")
        print(e)
        return None


@router.websocket("/ws/ask")
async def ask_question_agent_socket(
    websocket: WebSocket,
    session_id: str = Query(..., description="Session ID is required"),
    token: str = Query(..., description="Auth token is required"),
):
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if not data.get('event'):
                await websocket.send_text("Error: No event type provided.")
                continue
            
            
            hiddenQuestion = False
            hiddenAnswer = False
            
            match data.get('event'):
                case "cancel":
                    message = {
                        "type": "text",
                        "body": data.get('desc')
                    }
                    hiddenQuestion = True
                    
                case "image":
                    message = {
                        "type": "image",
                        "body": json.dumps(data.get('files'))
                    }
                    
                case "text":
                    message = {
                        "type": "text",
                        "body": data.get('text')
                    }
                
                case "wizard":
                    message = {
                        "type": 'wizard',
                        "wizard_id": data.get('wizard_id')
                    }

            if (data.get('event') == 'service'):
                continue

            await websocket.send_json(
                {
                    "event": "loading",
                }
            )
            
            await agent_rag.generate_response_socket(
                message=message, websocket=websocket, hiddenQuestion=hiddenQuestion, hiddenAnswer=hiddenAnswer
            )

            await websocket.send_json(
                {
                    "event": "finished",
                    "msg": "Response generated complete",
                }
                    )
                

    except WebSocketDisconnect:
        api_logger.info("WebSocket disconnected")
    except Exception as e:
        log_error(error_logger, e, f"Failed while processing: {str(e)}")
        await websocket.send_text(f"Error: {str(e)}")
    finally:
        # Clean up Redis bindings for this session
        await websocket.close()


@router.websocket("/ws/voice")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    speech_to_text_agent = get_voice_to_text_model()

    if not speech_to_text_agent:
        raise HTTPException(
            status_code=500,
            detail=f"The voice to speech service doesn't defined in the system settings",
        )

    try:
        while True:
            try:
                data = await websocket.receive_bytes()
            except WebSocketDisconnect:
                print("WebSocket disconnected")
                break

            filename = f"received_{uuid.uuid4().hex}.webm"
            filepath = os.path.join("temp", filename)

            # Ensure the directory exists
            os.makedirs("temp", exist_ok=True)

            try:
                with open(filepath, "wb") as f:
                    f.write(data)

                await websocket.send_json(
                    {"event": "transcribing", "msg": "در حال تبدیل صدا به متن."}
                )

                # Transcribe using Whisper
                trans = speech_to_text_agent.transcribe(filepath)

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


@router.post("/voice-wav-to-text")
async def voice_wav_endpoint(file: UploadFile = File(...)):
    """
    API endpoint to transcribe WAV audio files
    """
    speech_to_text_agent = get_voice_to_text_model()

    if not speech_to_text_agent:
        raise HTTPException(
            status_code=500,
            detail="The voice to speech service doesn't defined in the system settings",
        )

    # Check if file is WAV format
    if not file.content_type or "wav" not in file.content_type.lower():
        raise HTTPException(
            status_code=400, detail="Only WAV format files are accepted"
        )

    filename = f"received_{uuid.uuid4().hex}.wav"
    filepath = os.path.join("temp", filename)

    try:
        # Ensure the directory exists
        os.makedirs("temp", exist_ok=True)

        # Save uploaded file
        with open(filepath, "wb") as f:
            content = await file.read()
            f.write(content)

        # Transcribe using speech-to-text model
        transcription = speech_to_text_agent.transcribe(filepath)

        return {
            "status": "success",
            "transcription": transcription,
            "message": "Audio transcribed successfully",
        }

    except Exception as e:
        print(f"Error transcribing WAV file: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error transcribing audio: {str(e)}"
        )

    finally:
        # Clean up temporary file
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as cleanup_error:
            print(f"Cleanup error: {cleanup_error}")
