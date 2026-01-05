import sys
import os
from pathlib import Path

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from src.util.logging_config import configure_logging
from src.api.dependencies.oauth import get_current_user

# Routes
from .wizard import router as wizard_router
from .chat import router as chat_router
from .workflow import router as workflow_router
from .instruction import router as instruction_router
from .setting import router as system_router


# Configure loggers
main_logger, error_logger, api_logger, _ = configure_logging()

# Force reload environment variables
load_dotenv(override=True)

# Create FastAPI app
app = FastAPI(
    title="Sina AI Service",
    description="Sina AI service responsible for storing instructions, workflows and settings and interaction with LLM services like OpenAi",
    redirect_slashes=False,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(wizard_router)
app.include_router(chat_router)
app.include_router(workflow_router)
app.include_router(instruction_router)
app.include_router(system_router)

@app.get("/")
async def root():
    return {"app": "Sina AI Service", "status": "running"}

@app.get("/whoami")
def whoami(current_user: dict = Depends(get_current_user)):
    return current_user