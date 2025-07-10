from fastapi import APIRouter, Depends, HTTPException, Query
from redis import Redis
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import traceback
from fastapi.responses import JSONResponse
from urllib.parse import urlparse, urlunparse
import asyncio
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
import os
from rq import Queue
from rq.job import Job
import uuid
import re
import httpx

from database.models import get_db
from database.repository import DocumentRepository, CrawledDomainRepository
from models.html_to_markdown_agent import HTMLToMarkdownAgent
from database.vector_store import VectorStore
from api.auth import get_current_user

router = APIRouter(prefix="/documents", tags=["documents"])

# Initialize the HTML to Markdown agent and vector store
html_to_markdown_agent = HTMLToMarkdownAgent()
vector_store = VectorStore()

# Pydantic models for request/response
class DocumentBase(BaseModel):
    title: str
    html: str
    markdown: str
    uri: Optional[str] = None
    domain_id: Optional[int] = None
    workspace_id: Optional[int] = None
    aibot_id: Optional[int] = None

class DocumentCreate(DocumentBase):
    pass

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    html: Optional[str] = None
    markdown: Optional[str] = None
    uri: Optional[str] = None
    domain_id: Optional[int] = None
    aibot_id: Optional[int] = None

class VectorizeDocumentRequest(BaseModel):
    title: Optional[str] = None
    html: str
    metadata: Optional[dict] = None

class VectorizeDocumentResponse(BaseModel):
    message: str
    job_id: str

class DomainInfo(BaseModel):
    id: int
    domain: str

    class Config:
        from_attributes = True

class AiBotInfo(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class DocumentResponse(DocumentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    domain: Optional[DomainInfo] = None
    aibot: Optional[AiBotInfo] = None

    class Config:
        from_attributes = True

class DocumentListResponse(BaseModel):
    id: int
    title: str
    uri: Optional[str] = None
    domain_id: Optional[int] = None
    domain: Optional[DomainInfo] = None
    aibot_id: Optional[int] = None
    aibot: Optional[AiBotInfo] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PaginatedDocumentListResponse(BaseModel):
    items: List[DocumentListResponse]
    total: int
    page: int
    size: int
    pages: int

    class Config:
        from_attributes = True

def clean_domain(url: str) -> str:
    """
    Clean domain name by removing www. and ensuring proper URL structure
    
    Args:
        url: The URL to clean
        
    Returns:
        Cleaned URL with proper domain structure
    """
    try:
        # Parse the URL
        parsed = urlparse(url)
        
        # Remove www. from netloc using regex
        netloc = re.sub(r'^www\.', '', parsed.netloc)
        
        # Reconstruct the URL with cleaned netloc
        cleaned = urlunparse((
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        
        return cleaned
    except Exception as e:
        print(f"Error cleaning domain: {str(e)}")
        return url

# Create a new document
@router.post("/", response_model=DocumentResponse)
def create_document(document: DocumentCreate, db: Session = Depends(get_db), current_user: Any = Depends(get_current_user)):
    document_repo = DocumentRepository(db)
    domain_repo = CrawledDomainRepository(db)
    
    # Set workspace_id if not provided
    doc_data = document.model_dump()
    if not doc_data.get("workspace_id"):
        if hasattr(current_user, "current_workspace_id") and current_user.current_workspace_id:
            doc_data["workspace_id"] = current_user.current_workspace_id
        else:
            raise HTTPException(status_code=400, detail="workspace_id must be provided or selected by user.")

    # Verify domain exists if provided
    domain = None
    if doc_data.get("domain_id"):
        domain = domain_repo.get(doc_data["domain_id"])
        if not domain:
            raise HTTPException(status_code=400, detail="Domain not found")

    # Verify AiBot exists if provided
    aibot = None
    if doc_data.get("aibot_id"):
        from database.models import AiBot
        aibot = db.query(AiBot).filter(AiBot.id == doc_data["aibot_id"]).first()
        if not aibot:
            raise HTTPException(status_code=400, detail="AiBot not found")
        # Verify AiBot belongs to the same workspace
        if aibot.workspace_id != doc_data.get("workspace_id"):
            raise HTTPException(status_code=400, detail="AiBot does not belong to the specified workspace")

    # Create document
    created_doc = document_repo.create(doc_data)
    # Ensure required fields are present and not SQLAlchemy Column objects
    def get_value(obj, attr):
        value = getattr(obj, attr, None)
        # If value is a SQLAlchemy Column, get from instance
        if hasattr(value, 'expression') and hasattr(obj, '__table__'):
            value = getattr(obj, attr, None)
        return value

    id_val = get_value(created_doc, 'id')
    title_val = get_value(created_doc, 'title')
    html_val = get_value(created_doc, 'html')
    markdown_val = get_value(created_doc, 'markdown')
    created_at_val = get_value(created_doc, 'created_at')
    updated_at_val = get_value(created_doc, 'updated_at')
    if None in [id_val, title_val, html_val, markdown_val, created_at_val, updated_at_val]:
        raise HTTPException(status_code=500, detail="Document creation failed: missing required fields.")
    return DocumentResponse(
        id=int(id_val),
        title=str(title_val),
        html=str(html_val),
        markdown=str(markdown_val),
        uri=get_value(created_doc, 'uri'),
        domain_id=get_value(created_doc, 'domain_id'),
        aibot_id=get_value(created_doc, 'aibot_id'),
        created_at=created_at_val,
        updated_at=updated_at_val,
        domain=DomainInfo(id=int(domain.id), domain=str(domain.domain)) if domain else None,
        aibot=AiBotInfo(id=int(aibot.id), name=str(aibot.name)) if aibot else None
    )

# Get manual documents with pagination
@router.get("/manual", response_model=PaginatedDocumentListResponse,
          summary="دریافت اسناد دستی",
          description="این اندپوینت لیست اسناد با نوع دستی را با پشتیبانی از صفحه‌بندی برمی‌گرداند")
def get_manual_documents(
    page: int = Query(1, description="Page number (starting from 1)", ge=1),
    size: int = Query(10, description="Number of documents per page", ge=1, le=100),
    db: Session = Depends(get_db)
):
    document_repo = DocumentRepository(db)
    domain_repo = CrawledDomainRepository(db)
    
    # Query manual documents with pagination
    base_query = document_repo.db.query(document_repo.model_class).filter(
        document_repo.model_class.type == 'manual'
    )
    
    # Calculate total count and pages
    total = base_query.count()
    pages = (total + size - 1) // size  # Ceiling division
    
    # Apply pagination
    offset = (page - 1) * size
    documents = base_query.order_by(document_repo.model_class.created_at.desc()).offset(offset).limit(size).all()
    
    # Create response with domain and aibot info
    items = []
    for doc in documents:
        domain = domain_repo.get(doc.domain_id) if doc.domain_id else None
        aibot = None
        if doc.aibot_id:
            from database.models import AiBot
            aibot = db.query(AiBot).filter(AiBot.id == doc.aibot_id).first()
        
        items.append(DocumentListResponse(
            id=doc.id,
            title=doc.title,
            uri=doc.uri,
            domain_id=doc.domain_id,
            domain=domain,
            aibot_id=doc.aibot_id,
            aibot=AiBotInfo(id=aibot.id, name=aibot.name) if aibot else None,
            created_at=doc.created_at,
            updated_at=doc.updated_at
        ))
    
    return PaginatedDocumentListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages
    )

# Get a document by ID
@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    document_repo = DocumentRepository(db)
    domain_repo = CrawledDomainRepository(db)
    
    document = document_repo.get(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    domain = domain_repo.get(document.domain_id)
    aibot = None
    if document.aibot_id:
        from database.models import AiBot
        aibot = db.query(AiBot).filter(AiBot.id == document.aibot_id).first()
    
    return DocumentResponse(
        id=document.id,
        title=document.title,
        html=document.html,
        markdown=document.markdown,
        uri=document.uri,
        domain_id=document.domain_id,
        aibot_id=document.aibot_id,
        created_at=document.created_at,
        updated_at=document.updated_at,
        domain=DomainInfo(id=domain.id, domain=domain.domain) if domain else None,
        aibot=AiBotInfo(id=aibot.id, name=aibot.name) if aibot else None
    )

# Update a document
@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int, 
    document: DocumentUpdate, 
    update_vector: bool = Query(False, description="Whether to update the vector store with the new content"),
    db: Session = Depends(get_db)
):
    document_repo = DocumentRepository(db)
    domain_repo = CrawledDomainRepository(db)

    # Get current document
    current_doc = document_repo.get(document_id)
    if not current_doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Verify domain exists if being updated
    if document.domain_id:
        domain = domain_repo.get(document.domain_id)
        if not domain:
            raise HTTPException(status_code=400, detail="Domain not found")

    # Verify AiBot exists if being updated
    aibot = None
    if document.aibot_id:
        from database.models import AiBot
        aibot = db.query(AiBot).filter(AiBot.id == document.aibot_id).first()
        if not aibot:
            raise HTTPException(status_code=400, detail="AiBot not found")
        # Verify AiBot belongs to the same workspace as the document
        if aibot.workspace_id != current_doc.workspace_id:
            raise HTTPException(status_code=400, detail="AiBot does not belong to the same workspace as the document")

    # If HTML is being updated, convert it to markdown
    update_data = document.model_dump(exclude_unset=True)
  
    # Update document
    updated_doc = document_repo.update(document_id, update_data)
    if not updated_doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Update vector store if requested
    if update_vector and (document.html or document.markdown):
        try:
            # Convert HTML to Markdown if HTML is provided
            markdown = document.markdown
            if document.html:
                markdown = await html_to_markdown_agent.convert(document.html)
                if markdown is None:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to convert HTML to Markdown"
                    )
            
            # Prepare metadata with proper type handling
            metadata = {
                "document_id": str(document_id),  # Convert to string
                "title": updated_doc.title or "",  # Use empty string if None
                "uri": updated_doc.uri or "",  # Use empty string if None
                "domain_id": str(updated_doc.domain_id) if updated_doc.domain_id else "0",  # Convert to string, use "0" if None
                "updated_at": datetime.now().isoformat()
            }
            
            # Create document for vector store
            vector_doc = {
                "text": markdown,
                "metadata": metadata
            }

            # Add new vector document
            vector_id = vector_store.add_documents([vector_doc])[0]

        except Exception as e:
            print(f"Error updating vector store: {str(e)}")
            traceback.print_exc()
            # Don't raise error, just log it since vector update is optional

    domain = domain_repo.get(updated_doc.domain_id)
    aibot = None
    if updated_doc.aibot_id:
        from database.models import AiBot
        aibot = db.query(AiBot).filter(AiBot.id == updated_doc.aibot_id).first()
    
    return DocumentResponse(
        id=updated_doc.id,
        title=updated_doc.title,
        html=updated_doc.html,
        markdown=updated_doc.markdown,
        uri=updated_doc.uri,
        domain_id=updated_doc.domain_id,
        aibot_id=updated_doc.aibot_id,
        created_at=updated_doc.created_at,
        updated_at=updated_doc.updated_at,
        domain=DomainInfo(id=domain.id, domain=domain.domain) if domain else None,
        aibot=AiBotInfo(id=aibot.id, name=aibot.name) if aibot else None
    )


# Delete a document
@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    document_repo = DocumentRepository(db)
    document = document_repo.get(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    document_repo.delete(document_id)
    return {"message": "Document deleted successfully"}

# List all documents
@router.get("", response_model=PaginatedDocumentListResponse)
def list_documents_no_slash(
    domain_id: Optional[int] = Query(None, description="Filter by domain ID"),
    uri: Optional[str] = Query(None, description="Filter by URI"),
    page: int = Query(1, description="Page number (starting from 1)", ge=1),
    size: int = Query(10, description="Number of documents per page", ge=1, le=100),
    db: Session = Depends(get_db)
):
    return list_documents(domain_id, uri, page, size, db)

@router.get("/", response_model=PaginatedDocumentListResponse)
def list_documents(
    domain_id: Optional[int] = Query(None, description="Filter by domain ID"),
    uri: Optional[str] = Query(None, description="Filter by URI"),
    page: int = Query(1, description="Page number (starting from 1)", ge=1),
    size: int = Query(10, description="Number of documents per page", ge=1, le=100),
    db: Session = Depends(get_db)
):
    document_repo = DocumentRepository(db)
    domain_repo = CrawledDomainRepository(db)
    
    # Base query with domain_id not null filter
    base_query = document_repo.db.query(document_repo.model_class).filter(
        document_repo.model_class.domain_id.isnot(None)
    )
    
    # Get documents based on filters with pagination
    if domain_id:
        query = base_query.filter(document_repo.model_class.domain_id == domain_id)
    elif uri:
        query = base_query.filter(document_repo.model_class.uri == uri)
    else:
        query = base_query
    
    # Calculate total count and pages
    total = query.count()
    pages = (total + size - 1) // size  # Ceiling division
    
    # Apply pagination
    offset = (page - 1) * size
    documents = query.order_by(document_repo.model_class.created_at.desc()).offset(offset).limit(size).all()
    
    # Create response with domain and aibot info
    items = []
    for doc in documents:
        domain = domain_repo.get(doc.domain_id)
        aibot = None
        if doc.aibot_id:
            from database.models import AiBot
            aibot = db.query(AiBot).filter(AiBot.id == doc.aibot_id).first()
        
        items.append(DocumentListResponse(
            id=doc.id,
            title=doc.title,
            uri=doc.uri,
            domain_id=doc.domain_id,
            domain=DomainInfo(id=domain.id, domain=domain.domain) if domain else None,
            aibot_id=doc.aibot_id,
            aibot=AiBotInfo(id=aibot.id, name=aibot.name) if aibot else None,
            created_at=doc.created_at,
            updated_at=doc.updated_at,            
        ))
    
    return PaginatedDocumentListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages
    )

# Get document by URI
@router.get("/uri/{uri}", response_model=DocumentResponse)
def get_document_by_uri(uri: str, db: Session = Depends(get_db)):
    document_repo = DocumentRepository(db)
    domain_repo = CrawledDomainRepository(db)
    
    documents = document_repo.get_by_uri(uri)
    if not documents:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = documents[0]  # Return first document if multiple exist
    domain = domain_repo.get(doc.domain_id)
    aibot = None
    if doc.aibot_id:
        from database.models import AiBot
        aibot = db.query(AiBot).filter(AiBot.id == doc.aibot_id).first()
    
    return DocumentResponse(
        id=doc.id,
        title=doc.title,
        html=doc.html,
        markdown=doc.markdown,
        uri=doc.uri,
        domain_id=doc.domain_id,
        aibot_id=doc.aibot_id,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        domain=DomainInfo(id=domain.id, domain=domain.domain) if domain else None,
        aibot=AiBotInfo(id=aibot.id, name=aibot.name) if aibot else None
    )

# Search documents by title
@router.get("/search/title", response_model=List[DocumentResponse])
def search_documents_by_title(
    query: str = Query(..., description="Search query"),
    domain_id: Optional[int] = Query(None, description="Filter by domain ID"),
    db: Session = Depends(get_db)
):
    document_repo = DocumentRepository(db)
    domain_repo = CrawledDomainRepository(db)
    
    documents = document_repo.search_by_title(query)
    if domain_id:
        documents = [doc for doc in documents if doc.domain_id == domain_id]
    
    response = []
    for doc in documents:
        domain = domain_repo.get(doc.domain_id)
        aibot = None
        if doc.aibot_id:
            from database.models import AiBot
            aibot = db.query(AiBot).filter(AiBot.id == doc.aibot_id).first()
        
        response.append(DocumentResponse(
            id=doc.id,
            title=doc.title,
            html=doc.html,
            markdown=doc.markdown,
            uri=doc.uri,
            domain_id=doc.domain_id,
            aibot_id=doc.aibot_id,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            domain=DomainInfo(id=domain.id, domain=domain.domain) if domain else None,
            aibot=AiBotInfo(id=aibot.id, name=aibot.name) if aibot else None
        ))
    return response



@router.post("/{document_id}/vectorize", tags=["documents"],
          summary="تبدیل و ذخیره سند در پایگاه داده برداری",
          description="این اندپوینت HTML را به Markdown تبدیل کرده و در پایگاه داده برداری ذخیره می‌کند")
async def vectorize_document(
    document_id: int,
    request: VectorizeDocumentRequest
):
    """
    تبدیل HTML به Markdown و ذخیره در پایگاه داده برداری
    
    - **document_id**: شناسه سند
    - **title**: عنوان سند (اختیاری)
    - **html**: محتوای HTML سند
    - **metadata**: متادیتای سند (اختیاری)
    
    **نمونه درخواست:**
    ```json
    {
      "html": "<p>متن HTML</p>",
      "metadata": {
        "source": "https://example.com",
      }
    }
    ```
    
    **نمونه خروجی:**
    ```json
    {
      "message": "سند با موفقیت در پایگاه داده برداری ذخیره شد",
      "document_id": "doc_123",
      "vector_id": "vec_123",
      "markdown": "# متن Markdown"
    }
    ```
    """
    try:
        # Add vectorize task to queue
        redis_con = Redis(host=os.getenv('REDIS_HOST'))
        q = Queue(connection=redis_con)
        job_id = str(uuid.uuid4())
        q.enqueue(vectorize_task, document_id, request.html, request.metadata, request.title, job_id = job_id)

         # Prepare response
        response = VectorizeDocumentResponse(
            message="سند برای انتقال به پایگاه دانش هوش مصنوعی در صف پردازش قرار گرفت.",
            job_id=job_id
        )
        
        return JSONResponse(
            content=response.dict(),
            media_type="application/json; charset=utf-8"
        )
        
        
    except Exception as e:
        print(f"Error in vectorize_document: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

async def vectorize_task(document_id: int, html: str, metadata: Optional[dict] = None, title: Optional[str] = None):
    try:
        from database.models import SessionLocal
        from rq import get_current_job

        job = get_current_job()

        if job is None:
            # fallback or error handling
            pass

        # Update progress metadata
        job.meta['progress'] = {'type' : 'info', 'msg' : "Start vectorizing ..."}
        job.save_meta()

        db = SessionLocal()

        # Get document from database to verify it exists
        document_repo = DocumentRepository(db)
        document = document_repo.get(document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Update progress metadata
        job.meta['progress'] = {'type' : 'info', 'msg' : "Start html to markdown ..."}
        job.save_meta()
        
        # Set markdown from document.markdown database value if html not changed or generate markdown by AI agent
        if(document.ai_markdown and document.html == html and document.markdown):
            markdown = document.markdown
        else:
            markdown = await html_to_markdown_agent.convert(html)
            
            if markdown is None:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to convert HTML to Markdown"
                )
        
        # Update progress metadata
        job.meta['progress'] = {'type' : 'info', 'msg' : "Markdown generated. Storing data ..."}
        job.save_meta()

        # Clean the URI if it exists
        uri = clean_domain(document.uri) if document.uri else None

        # Prepare metadata
        metadata = metadata or {}
        metadata.update({
            "document_id": document_id,
            "title": title or document.title,
            "uri": uri,
            "domain_id": document.domain_id,
            "created_at": datetime.now().isoformat()
        })
        
        # Create document for vector store
        vector_doc = {
            "text": markdown,
            "metadata": metadata
        }
        
        # Add to vector store
        vector_id = await store_vector_document(vector_doc)

        # Update progress metadata
        job.meta['progress'] = {'type' : 'info', 'msg' : "Document added in vector database"}
        job.save_meta()
        
        # Update document
        update_data = {
            "title" : title or document.title,
            "html" : html,
            "markdown" : markdown,
            "vector_id" : vector_id,
            "ai_markdown" : True,
            "uri": uri  # Update with cleaned URI
        }
        document_repo.update(document_id, update_data)

        # Get the vector store data
        vector_data = await get_vector_document(vector_id)
        if not vector_data:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve vector data after storage"
            )

        # Update progress metadata
        job.meta['progress'] = {'type' : 'info', 'msg' : "Finished"}
        job.save_meta()
        
    except Exception as e:
        # Update progress metadata
        job.meta['progress'] = {'type' : 'error', 'msg' : f"Error in vectorize_document: {str(e)}"}
        job.save_meta()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

async def store_vector_document(vector_doc: Dict[str, Any]) -> str:
    """
    Store a document in the vector store using the vector API endpoint
    
    Args:
        vector_doc: Document to store with text and metadata
        
    Returns:
        str: Vector ID of the stored document
    """
    try:
        host = os.getenv('HOST', 'http://localhost:8000')
        if not host.startswith(('http://', 'https://')):
            host = f'http://{host}'

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{host}/vector/store",
                json={"documents": [vector_doc]}
            )
            response.raise_for_status()
            result = response.json()
            return result["document_ids"][0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def get_vector_document(vector_id: str) -> Dict[str, Any]:
    """
    Get a document from the vector store using the vector API endpoint
    
    Args:
        vector_id: ID of the vector document to retrieve
        
    Returns:
        Dict containing the vector document data
    """
    try:
        host = os.getenv('HOST', 'http://localhost:8000')
        if not host.startswith(('http://', 'https://')):
            host = f'http://{host}'

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{host}/vector/{vector_id}"
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

document_websocket_router = APIRouter()

@document_websocket_router.websocket("/ws/documents/vectorize/{job_id}")
async def websocket_vectorize_status(websocket: WebSocket, job_id: str):
    await websocket.accept()

    last_progress = None

    try:
        # Use the existing redis connection
        redis_conn = Redis(host=os.getenv('REDIS_HOST'))
        while True:
            job = Job.fetch(job_id, connection=redis_conn)

            progress = job.meta.get('progress', {'type': 'info', 'msg': 'Queued'})
            print(progress)
            if progress != last_progress:
                last_progress = progress

                await websocket.send_json({
                    'event': 'change_progress',
                    'progress': progress,
                    'status': job.get_status()
                })

            if job.is_finished or job.is_failed:
                # Send final status
                await websocket.send_json({
                    'event': 'finished',
                    'status': job.get_status(),
                    'progress': progress
                })
                break

            await asyncio.sleep(1)  # Poll every second

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        await websocket.send_json({
                    'event': 'error',
                    'msg' : f"Error in websocket for vectorize job {job_id}: {e}"
                })
        traceback.print_exc()
        await websocket.close(code=1011)  # Close with an error code

@router.get("/domain/{domain_id}", response_model=PaginatedDocumentListResponse,
          summary="دریافت اسناد یک دامنه",
          description="این اندپوینت لیست اسناد یک دامنه خاص را با پشتیبانی از صفحه‌بندی برمی‌گرداند")
def get_documents_by_domain(
    domain_id: int,
    page: int = Query(1, description="Page number (starting from 1)", ge=1),
    size: int = Query(10, description="Number of documents per page", ge=1, le=100),
    db: Session = Depends(get_db)
):
    document_repo = DocumentRepository(db)
    domain_repo = CrawledDomainRepository(db)
    
    # Verify domain exists
    domain = domain_repo.get(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    # Query documents for the domain with pagination
    base_query = document_repo.db.query(document_repo.model_class).filter(
        document_repo.model_class.domain_id == domain_id
    )
    
    # Calculate total count and pages
    total = base_query.count()
    pages = (total + size - 1) // size  # Ceiling division
    
    # Apply pagination
    offset = (page - 1) * size
    documents = base_query.order_by(document_repo.model_class.created_at.desc()).offset(offset).limit(size).all()
    
    # Create response with domain and aibot info
    items = []
    for doc in documents:
        aibot = None
        if doc.aibot_id:
            from database.models import AiBot
            aibot = db.query(AiBot).filter(AiBot.id == doc.aibot_id).first()
        
        items.append(DocumentListResponse(
            id=doc.id,
            title=doc.title,
            uri=doc.uri,
            domain_id=doc.domain_id,
            domain=DomainInfo(id=domain.id, domain=domain.domain),
            aibot_id=doc.aibot_id,
            aibot=AiBotInfo(id=aibot.id, name=aibot.name) if aibot else None,
            created_at=doc.created_at,
            updated_at=doc.updated_at
        ))
    
    return PaginatedDocumentListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages
    )

@router.get("/aibot/{aibot_id}", response_model=PaginatedDocumentListResponse,
          summary="دریافت اسناد یک AiBot",
          description="این اندپوینت لیست اسناد یک AiBot خاص را با پشتیبانی از صفحه‌بندی برمی‌گرداند")
def get_documents_by_aibot(
    aibot_id: int,
    page: int = Query(1, description="Page number (starting from 1)", ge=1),
    size: int = Query(10, description="Number of documents per page", ge=1, le=100),
    db: Session = Depends(get_db)
):
    document_repo = DocumentRepository(db)
    domain_repo = CrawledDomainRepository(db)
    
    # Verify aibot exists
    from database.models import AiBot
    aibot = db.query(AiBot).filter(AiBot.id == aibot_id).first()
    if not aibot:
        raise HTTPException(status_code=404, detail="AiBot not found")
    
    # Query documents for the aibot with pagination
    base_query = document_repo.db.query(document_repo.model_class).filter(
        document_repo.model_class.aibot_id == aibot_id
    )
    
    # Calculate total count and pages
    total = base_query.count()
    pages = (total + size - 1) // size  # Ceiling division
    
    # Apply pagination
    offset = (page - 1) * size
    documents = base_query.order_by(document_repo.model_class.created_at.desc()).offset(offset).limit(size).all()
    
    # Create response with domain and aibot info
    items = []
    for doc in documents:
        domain = domain_repo.get(doc.domain_id) if doc.domain_id else None
        items.append(DocumentListResponse(
            id=doc.id,
            title=doc.title,
            uri=doc.uri,
            domain_id=doc.domain_id,
            domain=DomainInfo(id=domain.id, domain=domain.domain) if domain else None,
            aibot_id=doc.aibot_id,
            aibot=AiBotInfo(id=aibot.id, name=aibot.name),
            created_at=doc.created_at,
            updated_at=doc.updated_at
        ))
    
    return PaginatedDocumentListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


