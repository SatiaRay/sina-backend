import sys
import os
from pathlib import Path
from datetime import datetime

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv, find_dotenv
from provider.service_container import container, ServiceContainer
from models.chat_agent.chat_agent_rag_proxy import ChatAgentRagProxy
from util.logging_config import configure_logging, log_error
from database.repository import WorkflowRepository
import uuid

# Routes
from api.about import router as about_router
from .wizard import router as wizard_router
from .chat import router as chat_router
from .workflow import router as workflow_router
from .ai import router as ai_router
from .job import router as job_router
from .instruction import router as instruction_router
from .ai_functions_tools import router as ai_functions_router
from .voice_agent import router as voice_agent_router
from .system import router as system_router
from .function_calling_log import router as function_calling_log_router
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

    # Create and bind AppSatiaCo instance
    app_satia_co = container.make("AppSatiaCo")
    container.instance("AppSatiaCo", app_satia_co)

    # Create and bind Neshan instance
    neshan = container.make("Neshan")
    container.instance("Neshan", neshan)

    # Create and bind Mayoral instance
    mayoral = container.make("Mayoral")
    container.instance("Mayoral", mayoral)

    # Ayan
    container.instance("Ayan", Ayan())

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
app.include_router(about_router)
app.include_router(job_router)
app.include_router(instruction_router)
app.include_router(ai_functions_router)
app.include_router(voice_agent_router)
app.include_router(system_router)
app.include_router(function_calling_log_router)
app.include_router(file_router)
app.include_router(auth_router)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests and their processing time"""
    start_time = datetime.now()

    # Generate request ID for tracking
    request_id = str(uuid.uuid4())

    # Log request details
    api_logger.info(f"Request {request_id} started: {request.method} {request.url}")

    try:
        # Process request
        response = await call_next(request)

        # Calculate processing time
        process_time = (datetime.now() - start_time).total_seconds()

        # Log response details
        api_logger.info(
            f"Request {request_id} completed: {response.status_code} "
            f"(took {process_time:.3f}s)"
        )

        return response

    except Exception as e:
        # Log error details
        process_time = (datetime.now() - start_time).total_seconds()
        log_error(
            error_logger,
            e,
            f"Request {request_id} failed after {process_time:.3f}s: {request.method} {request.url}",
        )

        # Return error response
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error occurred. Please check the logs for details.",
                "request_id": request_id,
            },
        )

@app.get("/")
async def root():
    return {"app": "Sina AI Service", "status": "running"}


@app.get(
    "/health",
    tags=["Utilities"],
    summary="بررسی وضعیت سرویس",
    description="این اندپوینت برای بررسی فعال بودن سرویس استفاده می‌شود",
)
async def health_check():
    """
    بررسی سلامت و وضعیت سرویس

    **نمونه خروجی:**
    ```json
    {
      "status": "ok",
      "version": "1.0.0"
    }
    ```
    """
    return {"status": "ok", "version": "1.0.0"}