from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, validator
from datetime import datetime
import json

from database.models import get_db
from database.repository import DocumentRepository, CrawledDomainRepository

router = APIRouter(prefix="/documents", tags=["documents"])

# Pydantic models for request/response
class DocumentBase(BaseModel):
    title: str
    html: str
    markdown: str
    uri: str
    domain_id: int
    embedding_id: Optional[int] = None

class DocumentCreate(DocumentBase):
    pass

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    html: Optional[str] = None
    markdown: Optional[str] = None
    uri: Optional[str] = None
    domain_id: Optional[int] = None
    embedding_id: Optional[int] = None

class DomainInfo(BaseModel):
    id: int
    domain: str

    class Config:
        from_attributes = True

class DocumentResponse(DocumentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    domain: DomainInfo

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
        embedding_id=created_doc.embedding_id,
        created_at=created_doc.created_at,
        updated_at=created_doc.updated_at,
        domain=DomainInfo(id=domain.id, domain=domain.domain)
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
        embedding_id=document.embedding_id,
        created_at=document.created_at,
        updated_at=document.updated_at,
        domain=DomainInfo(id=domain.id, domain=domain.domain)
    )

# Update a document
@router.put("/{document_id}", response_model=DocumentResponse)
def update_document(document_id: int, document: DocumentUpdate, db: Session = Depends(get_db)):
    document_repo = DocumentRepository(db)
    domain_repo = CrawledDomainRepository(db)
    
    # Verify domain exists if being updated
    if document.domain_id:
        domain = domain_repo.get(document.domain_id)
        if not domain:
            raise HTTPException(status_code=400, detail="Domain not found")
    
    updated_doc = document_repo.update(document_id, document.model_dump(exclude_unset=True))
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
        embedding_id=updated_doc.embedding_id,
        created_at=updated_doc.created_at,
        updated_at=updated_doc.updated_at,
        domain=DomainInfo(id=domain.id, domain=domain.domain)
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
            embedding_id=doc.embedding_id,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            domain=DomainInfo(id=domain.id, domain=domain.domain)
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
        embedding_id=doc.embedding_id,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        domain=DomainInfo(id=domain.id, domain=domain.domain)
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
            embedding_id=doc.embedding_id,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            domain=DomainInfo(id=domain.id, domain=domain.domain)
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
            embedding_id=doc.embedding_id,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            domain=DomainInfo(id=domain.id, domain=domain.domain)
        ))
    return response 