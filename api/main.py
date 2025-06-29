import sys
import os
from pathlib import Path
from urllib.parse import urlparse
import json
from datetime import datetime
from bs4 import BeautifulSoup

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
from .models import (DataSource, DataSourceListResponse, Chunk, AllKnowledgeRequest, UpdateKnowledgeRequest,VectorSearchRequest,StoreVectorRequest)
from models.html_to_markdown_agent import HTMLToMarkdownAgent
from database.repository import DocumentRepository
from database.repositories.workflow_repository import WorkflowRepository
from database.models import get_db
import uuid
from models.tools.functions.app_satia_co import AppSatiaCo

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
from .auth import router as auth_router
from .user import router as user_router
from .workspace import router as workspace_router

# Configure loggers
main_logger, error_logger, api_logger = configure_logging()

# Force reload environment variables
print("Loading environment from:", find_dotenv())
load_dotenv(override=True)

# Set base path for service container
ServiceContainer.set_base_path(str(root_dir))

# Initialize service container bindings
def init_service_container():
    # Bind VectorStore as singleton
    container.singleton('vector_store', VectorStore)
    
    # Bind ChatAgentRagProxy as singleton
    container.singleton('chat_agent', ChatAgentRagProxy)
    
    # Bind DocumentRepository as singleton
    container.singleton('document_repository', DocumentRepository)

    # Bind WorkflowRepository as singleton
    container.singleton('workflow_repository', WorkflowRepository)
    
    # Bind AppSatiaCo as singleton with required dependencies
    container.singleton('AppSatiaCo', lambda: AppSatiaCo(
        access_token=os.getenv('SATIA_ACCESS_TOKEN', ''),
        customer=os.getenv('SATIA_CUSTOMER', '')
    ))
    
    # Create and bind instances
    vector_store = container.make('vector_store')
    container.instance('vector_store', vector_store)
    
    chat_agent = container.make('chat_agent')
    container.instance('chat_agent', chat_agent)
    
    # Create and bind AppSatiaCo instance
    app_satia_co = container.make('AppSatiaCo')
    container.instance('AppSatiaCo', app_satia_co)

# Initialize the service container
init_service_container()

# Debug: Print database configuration at startup
print("Environment Variables at Startup:")
print(f"Current Directory: {os.getcwd()}")
print(f"MYSQL_DATABASE from env: {os.environ.get('MYSQL_DATABASE')}")
print(f"MYSQL_DATABASE from getenv: {os.getenv('MYSQL_DATABASE')}")

try:
    # Global vector store instance
    vector_store = container.make('vector_store')

    def get_vector_store():
        """Get or create VectorStore instance"""
        return container.make('vector_store')

    def refresh_vector_store(data=None):
        """Callback to refresh VectorStore instance"""
        print("Refreshing VectorStore instance...")
        vector_store = VectorStore()
        container.instance('vector_store', vector_store)
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
    redirect_slashes=False
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
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(workspace_router)

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
            f"Request {request_id} failed after {process_time:.3f}s: {request.method} {request.url}"
        )
        
        # Return error response
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error occurred. Please check the logs for details.",
                "request_id": request_id
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
    return {
        "app": APP_NAME,
        "version": "1.0.0",
        "status": "running"
    }

    


@app.post("/update_knowledge", tags=["Knowledge Management"],
            summary="به‌روزرسانی دانش",
            description="این اندپوینت برای به‌روزرسانی و خزش مجدد یک URL استفاده می‌شود")
async def update_knowledge(request: UpdateKnowledgeRequest):
    """
    به‌روزرسانی دانش با خزش مجدد یک URL
    
    - **url**: آدرس URL که باید مجدداً خزش شود
    
    **نمونه ورودی:**
    ```json
    {
      "url": "https://www.satia.co/blog"
    }
    ```
    
    **نمونه خروجی:**
    ```json
    {
      "message": "تعداد 8 سند از URL https://www.satia.co/blog مجدداً استخراج و پایگاه دانش به‌روزرسانی شد",
      "document_count": 8,
      "deleted_count": 5,
      "json_file": "data/crawled_data/www_satia_co_blog.json"
    }
    ```
    """
    try:
        url = request.url
        print(f"Starting to update knowledge for URL: {url}")
        
        # حذف اطلاعات قبلی مربوط به این URL از ChromaDB
        print(f"Deleting previous data for URL: {url}")
        deleted_count = await delete_url_data_from_chroma(url)
        print(f"Deleted {deleted_count} chunks for URL: {url}")
        
        # خزش مجدد URL
        print(f"Re-crawling URL: {url}")
        knowledge_items = run_spider(url)
        print(f"Crawled items: {len(knowledge_items) if knowledge_items else 0}")
        
        if not knowledge_items:
            return JSONResponse(
                content={"message": "هیچ اطلاعاتی از URL استخراج نشد"},
                media_type="application/json; charset=utf-8"
            )
        
        # اضافه کردن timestamp به metadata
        for item in knowledge_items:
            if 'metadata' not in item:
                item['metadata'] = {}
            item['metadata']['created_at'] = datetime.now().isoformat()
            item['metadata']['source'] = url
            item['metadata']['updated'] = "true"
        
        print(f"Processing {len(knowledge_items)} items")
        
        # به‌روزرسانی پایگاه دانش
        success = rag_system.update_knowledge_base(knowledge_items)
        
        if not success:
            raise Exception("Failed to update knowledge base")
        
        # به‌روزرسانی فایل JSON مربوط به این URL
        url_parsed = urlparse(url)
        file_name = url_parsed.netloc + url_parsed.path.replace('/', '_').replace('.', '_')
        file_name = ''.join(c for c in file_name if c.isalnum() or c == '_')
        file_name = file_name[:100]
        file_path = Path(f'data/crawled_data/{file_name}.json')
        
        return JSONResponse(
            content={
                "message": f"تعداد {len(knowledge_items)} سند از URL {url} مجدداً استخراج و پایگاه دانش به‌روزرسانی شد",
                "document_count": len(knowledge_items),
                "deleted_count": deleted_count,
                "json_file": str(file_path)
            },
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"Error in update_knowledge: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def delete_url_data_from_chroma(url: str) -> int:
    """
    حذف تمام داده‌های مربوط به یک URL خاص از ChromaDB
    
    Args:
        url: آدرس URL که داده‌های آن باید حذف شوند
        
    Returns:
        int: تعداد داده‌های حذف شده
    """
    try:
        import chromadb
        from chromadb.config import Settings
        
        # تنظیمات ChromaDB
        chroma_dir = os.getenv('CHROMA_PERSIST_DIRECTORY', './data/chroma')
        collection_name = os.getenv('CHROMA_COLLECTION_NAME', 'satya_docs')
        
        # ایجاد کلاینت ChromaDB
        client = chromadb.PersistentClient(
            path=chroma_dir,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # دریافت کالکشن موجود
        collection = client.get_collection(name=collection_name)
        
        # دریافت تمام داده‌ها
        all_data = collection.get()
        
        # یافتن چانک‌های مرتبط با URL
        url_chunk_ids = []
        for i, (doc_id, doc_metadata) in enumerate(zip(all_data['ids'], all_data['metadatas'])):
            if doc_metadata.get('source') == url:
                url_chunk_ids.append(doc_id)
        
        if url_chunk_ids:
            # حذف تمام چانک‌های مربوط به این URL
            collection.delete(ids=url_chunk_ids)
            
        return len(url_chunk_ids)
    except Exception as e:
        print(f"Error in delete_url_data_from_chroma: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0


@app.get("/all_knowledge")
async def get_all_knowledge(url: str):
    """
    دریافت تمام دانش‌های مرتبط با یک URL خاص
    
    پارامترها:
        url: آدرس منبع داده
    
    برمی‌گرداند:
        لیست تمام اسناد مرتبط با URL
    """
    try:
        result = rag_system.get_all_knowledge(url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/data_sources", response_model=DataSourceListResponse, tags=["Data Sources"],
          summary="دریافت لیست منابع داده",
          description="این اندپوینت لیست تمام منابع داده موجود در پایگاه دانش را برمی‌گرداند")
async def list_data_sources_no_slash():
    return await list_data_sources()

@app.get("/data_sources/", response_model=DataSourceListResponse, tags=["Data Sources"],
          summary="دریافت لیست منابع داده",
          description="این اندپوینت لیست تمام منابع داده موجود در پایگاه دانش را برمی‌گرداند")
async def list_data_sources():
    """
    لیست تمام منابع داده و محتوای استخراج شده از آنها
    
    **نمونه خروجی:**
    ```json
    {
      "sources": [
        {
          "source_id": "abc123",
          "url": "https://www.satia.co/about",
          "imported_by": "You",
          "import_date": "2023-06-15T12:30:45",
          "status": "✓",
          "refresh_status": "Never",
          "chunks": [...]
        }
      ],
      "total": 1
    }
    ```
    """
    try:
        docs = get_vector_store().get_all_documents()

        # گروه‌بندی اسناد بر اساس source_id
        source_groups = {}
        for doc in docs:
            source_id = doc['id']
            if not source_id:
                continue
                
            if source_id not in source_groups:
                created_at = doc['metadata'].get('created_at')
                if isinstance(created_at, str):
                    import_date = datetime.fromisoformat(created_at)
                else:
                    import_date = datetime.now()
                    
                source_groups[source_id] = {
                    'source_id': source_id,
                    'url': doc['metadata'].get('source', ''),
                    'chunks': [],
                    'import_date': import_date,
                    'status': '✓'
                }
            
            # فقط اضافه کردن chunks با متن معنی‌دار
            if doc['text'].strip():
                source_groups[source_id]['chunks'].append(Chunk(
                    text=doc['text'],
                    metadata=doc['metadata']
                ))
        
        # تبدیل به فرمت مورد نظر
        sources = []
        for source_id, data in source_groups.items():
            if data['chunks']:
                source = DataSource(
                    source_id=data['source_id'],
                    url=data['url'],
                    imported_by="You",
                    import_date=data['import_date'],
                    status=data['status'],
                    chunks=data['chunks']
                )
                sources.append(source)
        
        response = DataSourceListResponse(sources=sources, total=len(sources))
        return response
        
    except Exception as e:
        print(f"Error in list_data_sources: {str(e)}")  # اضافه کردن لاگ برای دیباگ
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/data_sources/{url}/chunks", response_model=List[Chunk], tags=["Data Sources"],
          summary="دریافت قطعات یک منبع داده",
          description="این اندپوینت قطعات متنی مربوط به یک منبع داده خاص را برمی‌گرداند")
async def get_source_chunks(url: str):
    """
    دریافت chunks یک منبع داده خاص
    
    - **url**: آدرس منبع داده
    """
    try:
        docs = get_vector_store().get_all_documents()
        chunks = []
        
        for doc in docs:
            if doc['metadata'].get('source', '') == url and doc['text'].strip():
                chunks.append(Chunk(
                    text=doc['text'],
                    metadata=doc['metadata']
                ))
        
        if not chunks:
            raise HTTPException(status_code=404, detail="Source not found")
            
        return JSONResponse(
            content=[chunk.dict() for chunk in chunks],
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

        if not isinstance(e, HTTPException):
            print(f"ERROR in edit_chunk: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))
        else:
            raise e

@app.get("/crawled_files", tags=["Data Sources"],
          summary="دریافت لیست فایل‌های خزش شده",
          description="این اندپوینت لیست تمام فایل‌های JSON حاصل از خزش URL‌ها را برمی‌گرداند")
async def get_crawled_files():
    """
    دریافت لیست تمام فایل‌های JSON جداگانه که از خزش URL‌ها ایجاد شده‌اند
    """
    try:
        data_dir = Path('data/crawled_data')
        if not data_dir.exists():
            return JSONResponse(
                content={"files": []},
                media_type="application/json; charset=utf-8"
            )
            
        files = list(data_dir.glob('*.json'))
        file_info = []
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                file_info.append({
                    "file_name": file_path.name,
                    "file_path": str(file_path),
                    "url": data.get('url', 'unknown'),
                    "title": data.get('title', 'بدون عنوان'),
                    "size": file_path.stat().st_size,
                    "created": datetime.fromtimestamp(file_path.stat().st_ctime).isoformat()
                })
            except Exception as e:
                # در صورت خطا در خواندن فایل، فقط اطلاعات اولیه را اضافه می‌کنیم
                file_info.append({
                    "file_name": file_path.name,
                    "file_path": str(file_path),
                    "error": str(e),
                    "size": file_path.stat().st_size,
                    "created": datetime.fromtimestamp(file_path.stat().st_ctime).isoformat()
                })
                
        return JSONResponse(
            content={"files": file_info},
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/crawled_file/{file_name}", tags=["Data Sources"],
          summary="دریافت محتوای یک فایل خزش شده",
          description="این اندپوینت محتوای یک فایل JSON خاص را برمی‌گرداند")
async def get_crawled_file_content(file_name: str):
    """
    دریافت محتوای یک فایل JSON خاص
    
    - **file_name**: نام فایل
    """
    try:
        file_path = Path(f'data/crawled_data/{file_name}')
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        return JSONResponse(
            content=data,
            media_type="application/json; charset=utf-8"
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/all_knowledge")
async def get_all_knowledge_api(request: AllKnowledgeRequest):
    """
    دریافت تمام دانش‌های مرتبط با یک URL خاص
    
    - **url**: آدرس منبع داده
    
    **نمونه ورودی:**
    ```json
    {
      "url": "https://www.satia.co/blog"
    }
    ```
    """
    try:
        result = rag_system.get_all_knowledge(request.url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health", tags=["Utilities"],
          summary="بررسی وضعیت سرویس",
          description="این اندپوینت برای بررسی فعال بودن سرویس استفاده می‌شود")
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

@app.post("/search-vector-doc", tags=["Utilities"],
          summary="جستجو در پایگاه دانش برداری",
          description="این اندپوینت نتایج جستجوی برداری را برای یک سوال نمایش می‌دهد")
async def search_vector_docs(
    request: VectorSearchRequest = Body(
        ...,
        example={
            "question": "ساتیا چیست؟",
            "limit": 5
        }
    )
):
    """
    جستجو در پایگاه دانش برداری و نمایش نتایج خام
    
    - **question**: سوال یا عبارت جستجو
    - **limit**: تعداد نتایج (پیش‌فرض: 5)
    """
    try:
        # جستجو در vector store
        relevant_docs = get_vector_store().search(request.question, request.limit)
        
        # تبدیل نتایج به فرمت مناسب
        results = []
        for doc in relevant_docs:
            result = {
                'text': doc['text'],
                'metadata': doc['metadata'],
                'score': doc.get('score', None)  # اگر امتیاز شباهت موجود باشد
            }
            results.append(result)
        
        return {
            'query': request.question,
            'results': results,
            'count': len(results)
        }
        
    except Exception as e:
        error_context = f"Question: {request.question}"
        log_error(error_logger, e, error_context)
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to search vector store",
                "error": str(e)
            }
        )

@app.post("/store_vector", tags=["Vector Store"],
         summary="ذخیره متن و متادیتا در پایگاه داده برداری",
         description="این اندپوینت متن و متادیتای مربوطه را در پایگاه داده برداری ذخیره می‌کند")
async def store_vector(
    request: StoreVectorRequest = Body(
        ...,
        example={
            "text": "<p class='content'>ساتیا یک پلتفرم مدیریت منابع سازمانی است که...</p>",
            "metadata": {
                "source": "دستی",
                "title": "درباره ساتیا",
                "author": "تیم ساتیا",
                "date": "2024-04-26"
            }
        }
    )
):
    try:
        # Clean HTML content
        soup = BeautifulSoup(request.text, 'html.parser')
        
        # Remove all attributes from HTML tags
        for tag in soup.find_all(True):
            tag.attrs = {}
        
        # Get cleaned text
        cleaned_text = str(soup)
        
        # Initialize vector store
        vector_store = VectorStore()
        
        # Create document structure with cleaned text
        document = {
            "text": cleaned_text,
            "metadata": request.metadata
        }
        
        # Add document to vector store
        vector_store.add_documents([document])
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "متن با موفقیت در پایگاه داده برداری ذخیره شد",
                "status": "success"
            }
        )
    except Exception as e:
        log_error(error_logger, str(e))
        raise HTTPException(
            status_code=500,
            detail=f"خطا در ذخیره متن در پایگاه داده برداری: {str(e)}"
        )
    


class AddManuallyKnowledgeRequest:
    def __init__(self, text: str, metadata: dict):
        self.text = text
        self.metadata = metadata

@app.post("/add_manually_knowledge", tags=["Knowledge Management"],
          summary="افزودن دانش به صورت دستی (تبدیل HTML به Markdown)",
          description="این اندپوینت مشابه /store_vector است اما ابتدا متن HTML را به مارک‌داون تبدیل می‌کند و سپس در پایگاه داده برداری ذخیره می‌کند.")
async def add_manually_knowledge(
    request: StoreVectorRequest = Body(
        ...,
        example={
            "text": "<p class='content'>ساتیا یک پلتفرم مدیریت منابع سازمانی است که...</p>",
            "metadata": {
                "source": "دستی",
                "title": "درباره ساتیا",
                "author": "تیم ساتیا",
                "date": "2024-04-26"
            }
        }
    ),
    db : Session = Depends(get_db)
):
    try:
        text = request.text

        # Convert HTML to Markdown using RAG model
        convertor_agent = HTMLToMarkdownAgent()
        markdown_result = await convertor_agent.convert(text)
        markdown_text = markdown_result if isinstance(markdown_result, str) else str(markdown_result)

        # Initialize vector store
        vector_store = VectorStore()

        # Store in database
        repo = DocumentRepository(db)
        doc = repo.create({
            'html' : request.text,
            'markdown' : markdown_text,
            'title' : request.metadata['title'],
            'type' : 'manual'
        })

        request.metadata['document_id'] = doc.id

        # Create document structure with markdown text
        document = {
            "text": markdown_text,
            "metadata": request.metadata
        }

        # Add document to vector store
        id = vector_store.add_documents([document])[0]

        repo.update(doc.id, {
            'vector_id' : id
        })

        return JSONResponse(
            status_code=200,
            content={
                "message": "متن (مارک‌داون) با موفقیت در پایگاه داده برداری ذخیره شد",
                "status": "success"
            }
        )
    except Exception as e:
        log_error(error_logger, str(e))
        raise HTTPException(
            status_code=500,
            detail=f"خطا در ذخیره متن مارک‌داون در پایگاه داده برداری: {str(e)}"
        )


@app.delete("/data_sources/{vector_id}", tags=["Data Sources"],
          summary="حذف یک منبع داده",
          description="این اندپوینت یک منبع داده را با استفاده از شناسه آن حذف می‌کند")
async def delete_data_source(vector_id: str):
    """
    حذف یک منبع داده با استفاده از شناسه آن
    
    - **vector_id**: شناسه منبع داده
    
    **نمونه خروجی:**
    ```json
    {
      "message": "منبع داده با موفقیت حذف شد",
      "deleted_chunks": 10
    }
    ```
    """
    try:
        vector = VectorStore()

        vector.delete_vector(vector_id)
        
        return JSONResponse(
            content={
                "message": "منبع داده با موفقیت حذف شد",
            },
            media_type="application/json; charset=utf-8"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error in delete_data_source: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/data_sources/{document_id}", tags=["Data Sources"],
          summary="بروزرسانی یک سند",
          description="این اندپوینت یک سند موجود را با استفاده از شناسه آن بروزرسانی می‌کند")
async def update_document(document_id: str, update_request: DocumentUpdateRequest):
    """
    بروزرسانی یک سند با استفاده از شناسه آن
    
    - **document_id**: شناسه سند
    - **text**: متن جدید سند
    - **metadata**: متادیتای جدید سند (اختیاری)
    
    **نمونه درخواست:**
    ```json
    {
      "text": "متن جدید سند",
      "metadata": {
        "source": "https://example.com",
        "title": "عنوان جدید"
      }
    }
    ```
    
    **نمونه خروجی:**
    ```json
    {
      "message": "سند با موفقیت بروزرسانی شد",
      "document_id": "doc_123"
    }
    ```
    """
    try:
        # Get all documents to verify document exists
        doc = get_vector_store().get_document(document_id=document_id)

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        
        # Update document in vector store
        get_vector_store().update_document(
            document_id=document_id,
            text=update_request.text,
            metadata=doc['metadata']
        )
        
        return JSONResponse(
            content={
                "message": "سند با موفقیت بروزرسانی شد",
                "document_id": document_id
            },
            media_type="application/json; charset=utf-8"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error in update_document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# @app.get("/data_sources/{document_id}", tags=["Data Sources"],
#           summary="دریافت یک سند",
#           description="این اندپوینت یک سند را با استفاده از شناسه آن برمی‌گرداند")
# async def get_document(document_id: str):
#     """
#     دریافت یک سند با استفاده از شناسه آن
    
#     - **document_id**: شناسه سند
    
#     **نمونه خروجی:**
#     ```