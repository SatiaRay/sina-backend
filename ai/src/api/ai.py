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
from util.logging_config import configure_logging, log_error
import os
from src.ai_agent.speech_to_text_agent import SpeechToTextAgent
from src.ai_agent.google_speech_to_text_agent import GoogleSpeechToTextAgent
import uuid
from dynaconf import Dynaconf
from pathlib import Path


# Configure loggers
main_logger, error_logger, api_logger, _ = configure_logging()

# Initialize the router
router = APIRouter(prefix="", tags=["AI"])

# Initialize the chat agent
agent_rag = ChatAgentRagProxy()

# Initialze the speech to text model
speech_to_text_agent = None


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
    
    # Generate unique binding token for this WebSocket session
    binding_token = binding_manager.generate_binding_token()

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

                case "service":
                    if(data.get('name') == 'satia'):
                        # Extract token and customer from the credentials object
                        credentials = data.get('credentials', {})
                        token = credentials.get('token', '')
                        customer = credentials.get('customer', '')

                        # Store binding data in Redis with unique token
                        binding_data = {
                            "class_name": "AppSatiaCo",
                            "token": token,
                            "customer": customer
                        }
                        
                        success = binding_manager.store_binding(binding_token, "AppSatiaCo", binding_data)
                        
                        if success:
                            await websocket.send_json(
                                {
                                    "event": "notice",
                                    "msg": "Service is ready",
                                }
                            )
                        else:
                            await websocket.send_json(
                                {
                                    "event": "error",
                                    "msg": "Failed to initialize service",
                                }
                            )

            if (data.get('event') == 'service'):
                continue

            await websocket.send_json(
                {
                    "event": "loading",
                }
            )
            
            await agent_rag.generate_response_socket(
                message=message, websocket=websocket, hiddenQuestion=hiddenQuestion, hiddenAnswer=hiddenAnswer, binding_token=binding_token
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
        binding_manager.remove_all_bindings(binding_token)
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
