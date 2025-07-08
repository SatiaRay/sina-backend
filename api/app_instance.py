from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from util.constants import APP_NAME, APP_VERSION
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
from .auth import router as auth_router
from .user import router as user_router
from .workspace import router as workspace_router
from .aibot import router as aibot_router

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="API for managing documents and knowledge base",
    redirect_slashes=False
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(workspace_router)
app.include_router(aibot_router)

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
]

app.openapi_tags = tags_metadata 