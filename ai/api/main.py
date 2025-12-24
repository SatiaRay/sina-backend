import sys
import os
from pathlib import Path

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv, find_dotenv
from provider.service_container import container, ServiceContainer
from models.chat_agent.chat_agent_rag_proxy import ChatAgentRagProxy
from util.logging_config import configure_logging
from database.repository import WorkflowRepository

# Routes
from .wizard import router as wizard_router
from .chat import router as chat_router
from .workflow import router as workflow_router
from .ai import router as ai_router
from .instruction import router as instruction_router
from .system import router as system_router
from dynaconf import Dynaconf
from .file import router as file_router
from .auth import router as auth_router

from util.settings import initialize_system_settings

# Configure loggers
main_logger, error_logger, api_logger, _ = configure_logging()

# Force reload environment variables
print("Loading environment from:", find_dotenv())
load_dotenv(override=True)

# Set base path for service container
ServiceContainer.set_base_path(str(root_dir))

# Initialize service container bindings
def init_service_container():
    # Bind ChatAgentRagProxy as singleton
    container.singleton("chat_agent", ChatAgentRagProxy)

    # Bind WorkflowRepository as singleton
    container.singleton("workflow_repository", WorkflowRepository)

    chat_agent = container.make("chat_agent")
    container.instance("chat_agent", chat_agent)

    # Bind app settings
    container.instance(
        "settings", Dynaconf(settings_files=[initialize_system_settings()])
    )


# Initialize the service container
init_service_container()

# Debug: Print database configuration at startup
print("Environment Variables at Startup:")
print(f"Current Directory: {os.getcwd()}")
print(f"MYSQL_DATABASE from env: {os.environ.get('MYSQL_DATABASE')}")
print(f"MYSQL_DATABASE from getenv: {os.getenv('MYSQL_DATABASE')}")


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
app.include_router(ai_router)
app.include_router(instruction_router)
app.include_router(system_router)
app.include_router(file_router)
app.include_router(auth_router)

@app.get("/")
async def root():
    return {"app": "Sina AI Service", "status": "running"}