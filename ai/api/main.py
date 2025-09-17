import sys
import os
from pathlib import Path
from urllib.parse import urlparse
import json
from datetime import datetime
from bs4 import BeautifulSoup

from models.tools.functions.trigger_hook import TriggerHook
from util.helper import decode_jwt_token

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from fastapi import FastAPI, HTTPException, Depends, Body, Request
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv, find_dotenv
from provider.service_container import container, ServiceContainer
from models.chat_agent.chat_agent_rag_proxy import ChatAgentRagProxy
from database.vector_store import VectorStore
from database.repository import DocumentRepository
from util.logging_config import configure_logging, log_error
from util.constants import APP_NAME, APP_VERSION
from util.event_bus import event_bus, VectorStoreEvent
from .models import (
    DataSource,
    DataSourceListResponse,
    Chunk,
    AllKnowledgeRequest,
    UpdateKnowledgeRequest,
    VectorSearchRequest,
    StoreVectorRequest,
)
from models.html_to_markdown_agent import HTMLToMarkdownAgent
from database.repository import DocumentRepository
from database.repositories.workflow_repository import WorkflowRepository
from database.models import get_db
import uuid
from models.tools.functions.app_satia_co import AppSatiaCo
from models.tools.functions.neshan import Neshan
from models.tools.functions.mayoral import Mayoral
from models.tools.functions.ayan import Ayan

# Routes
from api.about import router as about_router
from .wizard import router as wizard_router
from .document import router as document_router, document_websocket_router
from .domain import router as domain_router
from .chat import router as chat_router
from .crawl import router as crawl_router
from .vector import router as vector_router
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
    # Bind VectorStore as singleton
    container.singleton("vector_store", VectorStore)

    # Bind ChatAgentRagProxy as singleton
    container.singleton("chat_agent", ChatAgentRagProxy)

    # Bind DocumentRepository as singleton
    container.singleton("document_repository", DocumentRepository)

    # Bind WorkflowRepository as singleton
    container.singleton("workflow_repository", WorkflowRepository)

    # Bind AppSatiaCo as singleton with required dependencies
    container.singleton(
        "AppSatiaCo",
        lambda: AppSatiaCo(
            access_token=os.getenv("SATIA_ACCESS_TOKEN", ""),
            customer=os.getenv("SATIA_CUSTOMER", ""),
        ),
    )

    container.singleton(
        "Neshan",
        lambda: Neshan(
            api_key=os.getenv("NESHNA_API_KEY", ""),
            city_lat=float(os.getenv("NESHAN_CITY_LATITUDE", 34.0873)),
            city_long=float(os.getenv("NESHAN_CITY_LONG", 49.7022)),
        ),
    )

    container.singleton(
        "Mayoral",
        lambda: Mayoral(
            bearer_token=os.getenv("MAYORAL_API_BEARER_TOKEN", ""),
        ),
    )

    container.singleton("TriggerHook", TriggerHook())

    # Create and bind instances
    vector_store = container.make("vector_store")
    container.instance("vector_store", vector_store)

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

try:
    # Global vector store instance
    vector_store = container.make("vector_store")

    def get_vector_store():
        """Get or create VectorStore instance"""
        return container.make("vector_store")

    def refresh_vector_store(data=None):
        """Callback to refresh VectorStore instance"""
        print("Refreshing VectorStore instance...")
        vector_store = VectorStore()
        container.instance("vector_store", vector_store)
        print("VectorStore instance refreshed successfully")

    # Subscribe to collection modification events
    event_bus.subscribe(VectorStoreEvent.COLLECTION_MODIFIED, refresh_vector_store)

except Exception as e:
    print(f"Error during initialization: {str(e)}")
    raise

# Create FastAPI app
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="API for managing documents and knowledge base",
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
app.include_router(document_router)
app.include_router(document_websocket_router)
app.include_router(domain_router)
app.include_router(crawl_router)
app.include_router(chat_router)
app.include_router(vector_router)
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

# تعریف تگ‌ها برای سازماندهی بهتر اندپوینت‌ها
tags_metadata = [
    {
        "name": "Chat",
        "description": "اندپوینت‌های مربوط به پرسش و پاسخ",
    },
    {
        "name": "Knowledge Management",
        "description": "اندپوینت‌های مربوط به مدیریت پایگاه دانش (افزودن، به‌روزرسانی و حذف)",
    },
    {
        "name": "Data Sources",
        "description": "اندپوینت‌های مربوط به مدیریت منابع داده",
    },
    {
        "name": "Utilities",
        "description": "اندپوینت‌های متفرقه و ابزارها",
    },
    {
        "name": "System",
        "description": "اندپوینت‌های مربوط به مدیریت سیستم و پایگاه داده",
    },
]

app.openapi_tags = tags_metadata


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

# Checking authentication access_token and bind to service container if is valid
@app.middleware("http")
async def guard_middleware(request: Request, call_next):
    auth = request.headers.get("Authorization")
    
    if not auth or not auth.startswith("Bearer "):
        return JSONResponse(
                status_code=401,
                content={
                    "msg": "Missing token",
                }
            )

    token = auth.split(" ")[1]
    
    try:
        payload = decode_jwt_token(token=token)
        
        request.state.scopes = payload.get('scopes') or []
        
        request.state.user_id = payload.get('sub') or None
        
        response = await call_next(request)
        
        return response
        
    except Exception as e:
        return JSONResponse(
            status_code=401,
            content={
                "msg": "Unauthorized",
            }
        ) 

# مدل‌های درخواست و پاسخ
class QuestionRequest(BaseModel):
    question: str
    attach_resources: bool = False


class QuestionResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]


class DocumentRequest(BaseModel):
    documents: List[Dict]


class UrlRequest(BaseModel):
    url: HttpUrl


class DocumentUpdateRequest(BaseModel):
    text: str
    metadata: Optional[dict] = None


# نمونه‌های کلاس‌ها
vector_store = VectorStore()
agent_rag = ChatAgentRagProxy()


@app.get("/")
async def root():
    return {"app": APP_NAME, "version": "1.0.0", "status": "running"}


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


class AddManuallyKnowledgeRequest:
    def __init__(self, text: str, metadata: dict):
        self.text = text
        self.metadata = metadata


@app.post(
    "/add_manually_knowledge",
    tags=["Knowledge Management"],
    summary="افزودن دانش به صورت دستی (تبدیل HTML به Markdown)",
    description="این اندپوینت مشابه /store_vector است اما ابتدا متن HTML را به مارک‌داون تبدیل می‌کند و سپس در پایگاه داده برداری ذخیره می‌کند.",
)
async def add_manually_knowledge(
    request: StoreVectorRequest = Body(
        ...,
        example={
            "text": "<p class='content'>ساتیا یک پلتفرم مدیریت منابع سازمانی است که...</p>",
            "agent_type": "voice_agent",
            "metadata": {
                "source": "دستی",
                "title": "درباره ساتیا",
                "author": "تیم ساتیا",
                "date": "2024-04-26",
            },
        },
    ),
    db: Session = Depends(get_db),
):
    try:
        text = request.text

        # Convert HTML to Markdown using RAG model
        convertor_agent = HTMLToMarkdownAgent()
        markdown_result = await convertor_agent.convert(text)
        markdown_text = (
            markdown_result
            if isinstance(markdown_result, str)
            else str(markdown_result)
        )

        # Initialize vector store
        vector_store = VectorStore()

        # Store in database
        repo = DocumentRepository(db)
        doc = repo.create(
            {
                "html": request.text,
                "markdown": markdown_text,
                "title": request.metadata["title"],
                "type": "manual",
                "agent_type": request.agent_type,
            }
        )

        request.metadata["document_id"] = doc.id

        # Add document to vector store
        ids = vector_store.add_documents(
            [{"text": markdown_text, "metadata": request.metadata}]
        )

        repo.update(doc.id, {"status": "vectorized"})

        return JSONResponse(
            status_code=200,
            content={
                "message": "متن (مارک‌داون) با موفقیت در پایگاه داده برداری ذخیره شد",
                "ids": ids,
                "status": "success",
            },
        )
    except Exception as e:
        log_error(error_logger, str(e))
        raise HTTPException(
            status_code=500,
            detail=f"خطا در ذخیره متن مارک‌داون در پایگاه داده برداری: {str(e)}",
        )
