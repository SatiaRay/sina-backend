from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, validator
from datetime import datetime
import json
from pathlib import Path
import traceback
from fastapi.responses import JSONResponse
from urllib.parse import urlparse

from database.models import get_db
from database.repository import DocumentRepository, CrawledDomainRepository
from models.html_to_markdown_agent import HTMLToMarkdownAgent
from database.vector_store import VectorStore

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

class DocumentCreate(DocumentBase):
    pass

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    html: Optional[str] = None
    markdown: Optional[str] = None
    uri: Optional[str] = None
    domain_id: Optional[int] = None

class VectorizeDocumentRequest(BaseModel):
    html: str
    metadata: Optional[dict] = None

class DomainInfo(BaseModel):
    id: int
    domain: str

    class Config:
        from_attributes = True

class DocumentResponse(DocumentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    domain: Optional[DomainInfo] = None

    class Config:
        from_attributes = True

# Create a new document
@router.post("/", response_model=DocumentResponse)
def create_document(document: DocumentCreate, db: Session = Depends(get_db)):
    document_repo = DocumentRepository(db)
    domain_repo = CrawledDomainRepository(db)
    
    # Verify domain exists
    domain = domain_repo.get(document.domain_id)
    if not domain:
        raise HTTPException(status_code=400, detail="Domain not found")
    
    # Create document
    created_doc = document_repo.create(document.model_dump())
    return DocumentResponse(
        id=created_doc.id,
        title=created_doc.title,
        html=created_doc.html,
        markdown=created_doc.markdown,
        uri=created_doc.uri,
        domain_id=created_doc.domain_id,
        created_at=created_doc.created_at,
        updated_at=created_doc.updated_at,
        domain=DomainInfo(id=domain.id, domain=domain.domain) if domain else None
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
    return DocumentResponse(
        id=document.id,
        title=document.title,
        html=document.html,
        markdown=document.markdown,
        uri=document.uri,
        domain_id=document.domain_id,
        created_at=document.created_at,
        updated_at=document.updated_at,
        domain=DomainInfo(id=domain.id, domain=domain.domain) if domain else None
    )

# Update a document
@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(document_id: int, document: DocumentUpdate, db: Session = Depends(get_db)):
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

    # If HTML is being updated, convert it to markdown
    update_data = document.model_dump(exclude_unset=True)
  
    print(f"Updated document")

    # Update document
    updated_doc = document_repo.update(document_id, update_data)
    if not updated_doc:
        raise HTTPException(status_code=404, detail="Document not found")

    domain = domain_repo.get(updated_doc.domain_id)
    return DocumentResponse(
        id=updated_doc.id,
        title=updated_doc.title,
        html=updated_doc.html,
        markdown=updated_doc.markdown,
        uri=updated_doc.uri,
        domain_id=updated_doc.domain_id,
        created_at=updated_doc.created_at,
        updated_at=updated_doc.updated_at,
        domain=DomainInfo(id=domain.id, domain=domain.domain) if domain else None
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
@router.get("", response_model=List[DocumentResponse])
def list_documents_no_slash(
    domain_id: Optional[int] = Query(None, description="Filter by domain ID"),
    uri: Optional[str] = Query(None, description="Filter by URI"),
    db: Session = Depends(get_db)
):
    return list_documents(domain_id, uri, db)

@router.get("/", response_model=List[DocumentResponse])
def list_documents(
    domain_id: Optional[int] = Query(None, description="Filter by domain ID"),
    uri: Optional[str] = Query(None, description="Filter by URI"),
    db: Session = Depends(get_db)
):
    document_repo = DocumentRepository(db)
    domain_repo = CrawledDomainRepository(db)
    
    # Get documents based on filters
    if domain_id:
        documents = document_repo.get_by_domain(domain_id)
    elif uri:
        documents = document_repo.get_by_uri(uri)
    else:
        documents = document_repo.get_all()
    
    # Create response with domain info
    response = []
    for doc in documents:
        domain = domain_repo.get(doc.domain_id)
        response.append(DocumentResponse(
            id=doc.id,
            title=doc.title,
            html=doc.html,
            markdown=doc.markdown,
            uri=doc.uri,
            domain_id=doc.domain_id,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            domain=DomainInfo(id=domain.id, domain=domain.domain) if domain else None
        ))
    return response

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
    return DocumentResponse(
        id=doc.id,
        title=doc.title,
        html=doc.html,
        markdown=doc.markdown,
        uri=doc.uri,
        domain_id=doc.domain_id,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        domain=DomainInfo(id=domain.id, domain=domain.domain) if domain else None
    )

# Search documents by content
@router.get("/search/content", response_model=List[DocumentResponse])
def search_documents_by_content(
    query: str = Query(..., description="Search query"),
    domain_id: Optional[int] = Query(None, description="Filter by domain ID"),
    db: Session = Depends(get_db)
):
    document_repo = DocumentRepository(db)
    domain_repo = CrawledDomainRepository(db)
    
    documents = document_repo.search_by_content(query)
    if domain_id:
        documents = [doc for doc in documents if doc.domain_id == domain_id]
    
    response = []
    for doc in documents:
        domain = domain_repo.get(doc.domain_id)
        response.append(DocumentResponse(
            id=doc.id,
            title=doc.title,
            html=doc.html,
            markdown=doc.markdown,
            uri=doc.uri,
            domain_id=doc.domain_id,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            domain=DomainInfo(id=domain.id, domain=domain.domain) if domain else None
        ))
    return response

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
        response.append(DocumentResponse(
            id=doc.id,
            title=doc.title,
            html=doc.html,
            markdown=doc.markdown,
            uri=doc.uri,
            domain_id=doc.domain_id,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            domain=DomainInfo(id=domain.id, domain=domain.domain) if domain else None
        ))
    return response

@router.post("/{document_id}/vectorize", tags=["documents"],
          summary="تبدیل و ذخیره سند در پایگاه داده برداری",
          description="این اندپوینت HTML را به Markdown تبدیل کرده و در پایگاه داده برداری ذخیره می‌کند")
async def vectorize_document(
    document_id: int,
    request: VectorizeDocumentRequest,
    db: Session = Depends(get_db)
):
    """
    تبدیل HTML به Markdown و ذخیره در پایگاه داده برداری
    
    - **document_id**: شناسه سند
    - **html**: محتوای HTML سند
    - **metadata**: متادیتای سند (اختیاری)
    
    **نمونه درخواست:**
    ```json
    {
      "html": "<p>متن HTML</p>",
      "metadata": {
        "source": "https://example.com",
        "title": "عنوان سند"
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
        # Get document from database to verify it exists
        document_repo = DocumentRepository(db)
        document = document_repo.get(document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Convert HTML to Markdown
        markdown = await html_to_markdown_agent.convert(request.html)
        if markdown is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to convert HTML to Markdown"
            )
        
        # Prepare metadata
        metadata = request.metadata or {}
        metadata.update({
            "document_id": document_id,
            "title": document.title,
            "uri": document.uri,
            "domain_id": document.domain_id,
            "created_at": datetime.now().isoformat()
        })
        
        # Create document for vector store
        vector_doc = {
            "text": markdown,
            "metadata": metadata
        }
        
        # Add to vector store
        vector_id = vector_store.add_documents([vector_doc])[0]
        
        # Update document with vector_id
        update_data = {
            "vector_id": vector_id
        }
        document_repo.update(document_id, update_data)
        
        return JSONResponse(
            content={
                "message": "سند با موفقیت در پایگاه داده برداری ذخیره شد",
                "document_id": f"doc_{document_id}",
                "vector_id": vector_id,
                "markdown": markdown
            },
            media_type="application/json; charset=utf-8"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error in vectorize_document: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Get document by vector_id
@router.get("/vector/{vector_id}", response_model=DocumentResponse,
          summary="دریافت سند با استفاده از شناسه برداری",
          description="این اندپوینت سندی که شناسه برداری آن با مقدار ورودی برابر است را برمی‌گرداند")
def get_document_by_vector_id(vector_id: str, db: Session = Depends(get_db)):
    document_repo = DocumentRepository(db)
    domain_repo = CrawledDomainRepository(db)
    
    # Query document with matching vector_id
    query = document_repo.db.query(document_repo.model_class).filter(
        document_repo.model_class.vector_id == vector_id
    )
    document = query.first()
    
    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"No document found with vector_id: {vector_id}"
        )
    
    # Get domain info if domain_id exists
    domain = None
    if document.domain_id:
        domain = domain_repo.get(document.domain_id)
    
    return DocumentResponse(
        id=document.id,
        title=document.title,
        html=document.html,
        markdown=document.markdown,
        uri=document.uri,
        domain_id=document.domain_id,
        created_at=document.created_at,
        updated_at=document.updated_at,
        domain=DomainInfo(id=domain.id, domain=domain.domain) if domain else None
    )


