import sys
import os
from pathlib import Path
from urllib.parse import urlparse
import json
from datetime import datetime
import logging

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from fastapi import FastAPI, HTTPException, Depends, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import List, Dict, Any
from dotenv import load_dotenv
from models.rag import RAGSystem
from models.text_processor import TextProcessor
from crawler.main import run_spider
import uuid
from .models import (DataSource, DataSourceListResponse, Chunk, EditChunkRequest, 
                    PlainTextRequest, AllKnowledgeRequest, UpdateKnowledgeRequest,
                    CurationStatus, CurationStats)
from database.vector_store import VectorStore
from util.database import get_db_connection
from api.models import (ChatRequest, 
                      AddKnowledgeRequest)
from util.logging_config import configure_logging, log_error
from util.constants import APP_NAME, APP_VERSION

# Configure loggers
main_logger, error_logger, api_logger = configure_logging()

load_dotenv()

app = FastAPI(
    title="Satya Support Chatbot API",
    description="""
    ## API چت‌بات پشتیبانی ساتیا
    
    این API امکانات زیر را فراهم می‌کند:
    
    * **پرسش و پاسخ**: پرسش از چت‌بات و دریافت پاسخ براساس پایگاه دانش
    * **مدیریت دانش**: افزودن، به‌روزرسانی و حذف دانش از منابع مختلف (URL یا متن ساده)
    * **مدیریت منابع داده**: مشاهده و ویرایش منابع داده موجود
    
    برای استفاده از API، می‌توانید از اندپوینت‌های زیر استفاده کنید:
    
    * `/ask` یا `/askme`: برای پرسش از چت‌بات
    * `/add_knowledge`: برای افزودن دانش از یک URL
    * `/update_knowledge`: برای به‌روزرسانی دانش موجود از یک URL
    * `/api/add_plaintext`: برای افزودن متن ساده به پایگاه دانش
    """,
    version=APP_VERSION,
    contact={
        "name": "تیم پشتیبانی ساتیا",
        "url": "https://www.satia.co/support",
        "email": "support@satia.co",
    },
    docs_url="/docs",
    redoc_url="/redoc",
)

# تنظیم CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # در محیط تولید محدود کنید
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

class QuestionResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]

class DocumentRequest(BaseModel):
    documents: List[Dict]

class UrlRequest(BaseModel):
    url: HttpUrl

# نمونه‌های کلاس‌ها
rag_system = RAGSystem()
text_processor = TextProcessor()
vector_store = VectorStore()

@app.get("/")
async def root():
    return {"message": "Welcome to Satya Support Chatbot API"}

@app.post("/ask", response_model=Dict[str, Any], tags=["Chat"],
          summary="پرسش از چت‌بات",
          description="این اندپوینت یک سوال را دریافت کرده و پاسخ مرتبط را از پایگاه دانش برمی‌گرداند")
async def ask_question(request: Request, question_request: QuestionRequest = Body(...)):
    """
    Process a question and return the answer with relevant sources
    """
    try:
        api_logger.info(f"Processing question: {question_request.question}")
        
        response = rag_system.generate_response(question_request.question)
        
        api_logger.info("Successfully generated response")
        return JSONResponse(content=response, media_type="application/json; charset=utf-8")
        
    except Exception as e:
        error_context = f"Question: {question_request.question}"
        log_error(error_logger, e, error_context)
        
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to generate response",
                "error": str(e)
            }
        )

@app.post("/askme", response_model=QuestionResponse, tags=["Chat"],
          summary="پرسش از چت‌بات (مترادف ask)",
          description="این اندپوینت مشابه اندپوینت ask است")
async def askme_question(
    request: QuestionRequest = Body(
        ...,
        example={"question": "ساتیا چه قابلیت‌هایی دارد؟"}
    )
):
    """
    پرسش از چت‌بات و دریافت پاسخ (مترادف ask)
    
    - **question**: سوال کاربر
    """
    try:
        response = rag_system.generate_response(request.question)
        return JSONResponse(content=response, media_type="application/json; charset=utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

@app.delete("/delete_all_knowledge", tags=["Knowledge Management"])
async def delete_all_knowledge():
    """
    حذف تمام داده‌های موجود در پایگاه دانش
    """
    try:
        vector_store.delete_all()
        return {"message": "تمام داده‌ها با موفقیت حذف شدند"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_knowledge", tags=["Knowledge Management"],
         summary="افزودن دانش از یک URL به پایگاه دانش",
         description="این اندپوینت یک URL را دریافت کرده، آن را خزش کرده و محتوای استخراج شده را به پایگاه دانش اضافه می‌کند")
async def add_knowledge(
    request: UrlRequest = Body(
        ...,
        example={"url": "https://www.satia.co/blog"}
    )
):
    """
    اضافه کردن دانش از یک URL به پایگاه دانش
    
    - **url**: آدرس URL که باید خزش شود (مثال: https://www.satia.co/blog)
    
    **نمونه ورودی:**
    ```json
    {
      "url": "https://www.satia.co/blog"
    }
    ```
    
    **نمونه خروجی:**
    ```json
    {
      "status": "success",
      "message": "تعداد 8 سند به پایگاه دانش اضافه شد",
      "document_count": 8,
      "file_path": "data/crawled_data/www_satia_co_blog.json"
    }
    ```
    """
    try:
        url = str(request.url)
        print(f"درحال استخراج اطلاعات از URL: {url}")
        
        # خزش URL
        print(f"شروع خزش URL: {url}")
        knowledge_items = run_spider(url)
        print(f"تعداد {len(knowledge_items) if knowledge_items else 0} سند استخراج شد")
        
        if not knowledge_items:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "هیچ اطلاعاتی از URL استخراج نشد",
                    "document_count": 0
                },
                media_type="application/json; charset=utf-8"
            )
        
        # اضافه کردن متادیتا به اسناد
        for item in knowledge_items:
            if 'metadata' not in item:
                item['metadata'] = {}
            item['metadata']['source'] = url  # حفظ دقیق URL
            item['metadata']['date_added'] = datetime.now().isoformat()
        
        # پردازش و ذخیره‌سازی اسناد
        processed_docs = text_processor.process_batch(knowledge_items)
        
        if not processed_docs:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "خطا در پردازش اسناد",
                    "document_count": 0
                },
                media_type="application/json; charset=utf-8"
            )
        
        # اضافه کردن به vector store
        vector_store.add_documents(processed_docs)
        
        # ایجاد یک نام فایل مناسب برای ذخیره داده استخراج شده
        from urllib.parse import urlparse
        url_parsed = urlparse(url)
        file_name = url_parsed.netloc + url_parsed.path.replace('/', '_').replace('.', '_')
        file_name = ''.join(c for c in file_name if c.isalnum() or c == '_')
        file_name = file_name[:100]
        
        # ذخیره اطلاعات در فایل جیسون
        data_dir = Path("data/crawled_data")
        data_dir.mkdir(parents=True, exist_ok=True)
        file_path = data_dir / f"{file_name}.json"
        
        try:
            # ذخیره اطلاعات اصلی در فایل JSON
            output_data = {
                "url": url,
                "title": knowledge_items[0].get('metadata', {}).get('title', 'بدون عنوان'),
                "date_added": datetime.now().isoformat(),
                "document_count": len(processed_docs),
                "content": knowledge_items[0].get('text', '')[:500] + "..."  # نمونه محتوا
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
                
            print(f"اطلاعات در فایل {file_path} ذخیره شد")
        except Exception as e:
            print(f"خطا در ذخیره فایل JSON: {str(e)}")
        
        return JSONResponse(
            content={
                "status": "success",
                "message": f"تعداد {len(processed_docs)} سند از URL {url} استخراج و به پایگاه دانش اضافه شد",
                "document_count": len(processed_docs),
                "file_path": str(file_path)
            },
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"خطا در افزودن دانش: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_text_knowledge")
async def add_text_knowledge(request: PlainTextRequest):
    """
    اضافه کردن متن دلخواه به پایگاه دانش
    
    پارامترها:
        request: درخواست حاوی متن، عنوان و منبع
    
    برمی‌گرداند:
        اطلاعات مربوط به اضافه شدن متن
    """
    try:
        # استفاده از عنوان یا یک عنوان پیش‌فرض
        title = request.title if request.title else "متن دستی"
        # استفاده از منبع یا یک منبع پیش‌فرض
        source = request.source if request.source else "ورودی کاربر"
        
        # پردازش متن
        processed_text = text_processor.process_text(request.text)
        
        # ایجاد متادیتا
        metadata = {
            "title": title,
            "source": source,
            "date_added": datetime.now().isoformat()
        }
        
        # افزودن به پایگاه دانش
        rag_system.vector_store.add_documents([{
            "text": processed_text,
            "metadata": metadata
        }])
        
        return {
            "status": "success",
            "message": "متن با موفقیت به پایگاه دانش اضافه شد",
            "metadata": metadata
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
async def list_data_sources():
    """
    لیست تمام منابع داده و محتوای استخراج شده از آنها
    
    **نمونه خروجی:**
    ```json
    {
      "sources": [
        {
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
        docs = vector_store.get_all_documents()
        
        # گروه‌بندی اسناد بر اساس URL
        url_groups = {}
        for doc in docs:
            url = doc['metadata'].get('source', '')
            if not url:
                continue
                
            if url not in url_groups:
                created_at = doc['metadata'].get('created_at')
                if isinstance(created_at, str):
                    import_date = datetime.fromisoformat(created_at)
                else:
                    import_date = datetime.now()
                    
                url_groups[url] = {
                    'chunks': [],
                    'import_date': import_date,
                    'status': '✓'
                }
            
            # فقط اضافه کردن chunks با متن معنی‌دار
            if doc['text'].strip():
                url_groups[url]['chunks'].append(Chunk(
                    text=doc['text'],
                    metadata=doc['metadata']
                ))
        
        # تبدیل به فرمت مورد نظر
        sources = []
        for url, data in url_groups.items():
            if data['chunks']:
                source = DataSource(
                    url=url,
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
        docs = vector_store.get_all_documents()
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

@app.post("/edit_chunk", tags=["Data Sources"],
          summary="ویرایش یک قطعه متنی",
          description="این اندپوینت امکان ویرایش یک قطعه متنی (chunk) خاص در پایگاه دانش را فراهم می‌کند")
async def edit_chunk(
    request: EditChunkRequest = Body(
        ...,
        example={
            "url": "https://www.satia.co/about",
            "chunk_index": 0,
            "new_text": "ساتیا یک پلتفرم جامع مدیریت منابع سازمانی است."
        }
    )
):
    """
    ویرایش متن یک چانک خاص در پایگاه دانش
    
    - **url**: آدرس منبع داده
    - **chunk_index**: شماره قطعه متنی
    - **new_text**: متن جدید
    """
    try:
        import chromadb
        from chromadb.config import Settings
        from sentence_transformers import SentenceTransformer
        
        # تنظیمات ChromaDB
        chroma_dir = os.getenv('CHROMA_PERSIST_DIRECTORY', './data/chroma')
        collection_name = os.getenv('CHROMA_COLLECTION_NAME', 'satya_docs')
        
        print(f"DEBUG: دایرکتوری ChromaDB: {chroma_dir}")
        print(f"DEBUG: نام کالکشن: {collection_name}")
        
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
        print(f"DEBUG: تعداد کل اسناد: {len(all_data['ids'])}")
        
        # یافتن چانک‌های مرتبط با URL
        url_chunks = []
        for i, (doc_id, doc_text, doc_metadata) in enumerate(zip(all_data['ids'], all_data['documents'], all_data['metadatas'])):
            if doc_metadata.get('source') == request.url:
                url_chunks.append({
                    'id': doc_id,
                    'text': doc_text,
                    'metadata': doc_metadata,
                    'index': i
                })
        
        print(f"DEBUG: تعداد چانک‌های مربوط به URL '{request.url}': {len(url_chunks)}")
        
        # بررسی وجود چانک‌های مرتبط با URL
        if not url_chunks:
            # بررسی URL‌های موجود در پایگاه داده
            unique_urls = set([meta.get('source', '') for meta in all_data['metadatas']])
            print(f"DEBUG: URL‌های موجود در پایگاه داده: {unique_urls}")
            raise HTTPException(status_code=404, detail="URL not found in knowledge base")
        
        # بررسی معتبر بودن شاخص چانک
        if request.chunk_index < 0 or request.chunk_index >= len(url_chunks):
            print(f"DEBUG: شاخص چانک خارج از محدوده است. شاخص درخواستی: {request.chunk_index}, محدوده مجاز: 0-{len(url_chunks)-1}")
            raise HTTPException(status_code=400, detail=f"Chunk index out of range. Valid range: 0-{len(url_chunks)-1}")
        
        # چانک مورد نظر برای ویرایش
        target_chunk = url_chunks[request.chunk_index]
        doc_id = target_chunk['id']
        doc_index = target_chunk['index']
        
        print(f"DEBUG: چانک هدف: ID={doc_id}, متن={target_chunk['text'][:50]}...")
        
        # حذف چانک قدیمی
        try:
            print(f"DEBUG: در حال حذف چانک با شناسه {doc_id}...")
            collection.delete(ids=[doc_id])
            print("DEBUG: چانک با موفقیت حذف شد")
        except Exception as e:
            print(f"ERROR: خطا در حذف چانک: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Failed to delete chunk: {str(e)}")
        
        # ایجاد embedding برای متن جدید
        try:
            print("DEBUG: در حال ایجاد embedding جدید...")
            model = SentenceTransformer(os.getenv('EMBEDDING_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2'))
            new_embedding = model.encode(request.new_text).tolist()
            
            print(f"DEBUG: در حال افزودن چانک جدید با متن '{request.new_text}'...")
            collection.add(
                ids=[doc_id],
                documents=[request.new_text],
                metadatas=[target_chunk['metadata']],
                embeddings=[new_embedding]
            )
            print("DEBUG: چانک جدید با موفقیت اضافه شد")
        except Exception as e:
            print(f"ERROR: خطا در افزودن چانک جدید: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Failed to add new chunk: {str(e)}")
        
        return JSONResponse(
            content={
                "message": "چانک با موفقیت ویرایش شد",
                "chunk_id": doc_id,
                "chunk_index": request.chunk_index,
                "url": request.url,
                "new_text": request.new_text
            },
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
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

@app.post("/api/add_plaintext", tags=["Knowledge Management"],
         summary="افزودن متن به پایگاه دانش",
         description="این اندپوینت یک متن را دریافت کرده و آن را به پایگاه دانش اضافه می‌کند")
async def add_plaintext(
    request: PlainTextRequest = Body(
        ...,
        example={
            "text": "ساتیا یک پلتفرم جامع مدیریت منابع سازمانی است.",
            "title": "درباره ساتیا",
            "source": "دستی"
        }
    )
):
    """
    اضافه کردن متن دلخواه به پایگاه دانش
    
    - **text**: متن مورد نظر (اجباری)
    - **title**: عنوان سند (اختیاری)
    - **source**: منبع سند (اختیاری)
    
    **نمونه ورودی:**
    ```json
    {
      "text": "ساتیا یک پلتفرم جامع مدیریت منابع سازمانی است.",
      "title": "درباره ساتیا",
      "source": "دستی"
    }
    ```
    
    **نمونه خروجی:**
    ```json
    {
      "status": "success",
      "message": "متن با موفقیت به پایگاه دانش اضافه شد",
      "document_count": 1
    }
    ```
    """
    try:
        # استفاده از عنوان یا یک عنوان پیش‌فرض
        title = request.title if request.title else "متن دستی"
        # استفاده از منبع یا یک منبع پیش‌فرض
        source = request.source if request.source else "ورودی کاربر"
        
        # ایجاد سند
        document = {
            "text": request.text,
            "metadata": {
                "title": title,
                "source": source,
                "date_added": datetime.now().isoformat()
            }
        }
        
        # پردازش سند و اضافه کردن به پایگاه دانش
        processed_docs = text_processor.process_batch([document])
        
        if not processed_docs:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "خطا در پردازش متن",
                    "document_count": 0
                },
                media_type="application/json; charset=utf-8"
            )
        
        # اضافه کردن به vector store
        vector_store.add_documents(processed_docs)
        
        # ذخیره دیتا در یک فایل JSON برای پشتیبان‌گیری
        try:
            data_dir = Path("data/plaintext_data")
            data_dir.mkdir(parents=True, exist_ok=True)
            
            file_name = f"plaintext_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            file_path = data_dir / file_name
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(document, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Warning: Could not save plaintext backup: {str(e)}")
        
        return JSONResponse(
            content={
                "status": "success",
                "message": "متن با موفقیت به پایگاه دانش اضافه شد",
                "document_count": len(processed_docs)
            },
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"Error in add_plaintext: {str(e)}")
        import traceback
        traceback.print_exc()
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

@app.get("/curation/pending", tags=["Curation"],
          summary="دریافت اسناد در انتظار بررسی",
          description="این اندپوینت لیست اسنادی که نیاز به بررسی دارند را برمی‌گرداند")
async def get_pending_documents(
    offset: int = 0,
    limit: int = 50
):
    """
    دریافت لیست اسناد در انتظار بررسی
    
    - **offset**: شماره شروع (پیش‌فرض: 0)
    - **limit**: تعداد نتایج (پیش‌فرض: 50)
    """
    try:
        documents = vector_store.get_pending_documents(offset, limit)
        return JSONResponse(
            content={"documents": documents},
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
        log_error(error_logger, e, "Error getting pending documents")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to get pending documents", "error": str(e)}
        )

@app.post("/curation/update_status", tags=["Curation"],
          summary="به‌روزرسانی وضعیت بررسی",
          description="این اندپوینت وضعیت بررسی یک سند را به‌روزرسانی می‌کند")
async def update_document_status(status_update: CurationStatus):
    """
    به‌روزرسانی وضعیت بررسی یک سند
    
    - **document_id**: شناسه سند
    - **status**: وضعیت جدید ('approved', 'rejected', 'pending')
    - **edited_text**: متن ویرایش شده (اختیاری)
    - **reason**: دلیل رد یا تایید (اختیاری)
    """
    try:
        vector_store.update_document_status(
            status_update.document_id,
            status_update.status,
            status_update.edited_text
        )
        return JSONResponse(
            content={"message": "Document status updated successfully"},
            media_type="application/json; charset=utf-8"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_error(error_logger, e, f"Error updating document status: {status_update.document_id}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to update document status", "error": str(e)}
        )

@app.get("/curation/stats", tags=["Curation"],
          summary="آمار بررسی اسناد",
          description="این اندپوینت آمار وضعیت بررسی اسناد را برمی‌گرداند")
async def get_curation_stats():
    """
    دریافت آمار وضعیت بررسی اسناد
    """
    try:
        stats = vector_store.get_curation_stats()
        return JSONResponse(
            content=stats,
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
        log_error(error_logger, e, "Error getting curation stats")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to get curation stats", "error": str(e)}
        )

@app.get("/curation/document/{doc_id}", tags=["Curation"],
          summary="دریافت جزئیات یک سند",
          description="این اندپوینت جزئیات یک سند خاص را برمی‌گرداند")
async def get_document_details(doc_id: str):
    """
    دریافت جزئیات یک سند با شناسه
    
    - **doc_id**: شناسه سند
    """
    try:
        document = vector_store.get_document_by_id(doc_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
            
        return JSONResponse(
            content=document,
            media_type="application/json; charset=utf-8"
        )
    except HTTPException:
        raise
    except Exception as e:
        log_error(error_logger, e, f"Error getting document details: {doc_id}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to get document details", "error": str(e)}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001) 