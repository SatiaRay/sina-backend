from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from database.models import get_db
from database.repository import CrawledDomainRepository, DocumentRepository

router = APIRouter(prefix="/domains", tags=["domains"])

# Pydantic models for request/response
class CrawledDomainBase(BaseModel):
    domain: str

class CrawledDomainCreate(CrawledDomainBase):
    pass

class CrawledDomainUpdate(BaseModel):
    domain: Optional[str] = None

class CrawledDomainResponse(CrawledDomainBase):
    id: int
    created_at: datetime
    updated_at: datetime
    document_count: int = 0

    class Config:
        from_attributes = True

# Create a new domain
@router.post("/", response_model=CrawledDomainResponse)
def create_domain(domain: CrawledDomainCreate, db: Session = Depends(get_db)):
    domain_repo = CrawledDomainRepository(db)
    try:
        return domain_repo.create(domain.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Get a domain by ID
@router.get("/{domain_id}", response_model=CrawledDomainResponse)
def get_domain(domain_id: int, db: Session = Depends(get_db)):
    domain_repo = CrawledDomainRepository(db)
    domain = domain_repo.get(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    # Get document count
    document_repo = DocumentRepository(db)
    document_count = len(document_repo.get_by_domain(domain_id))
    
    response = CrawledDomainResponse(
        id=domain.id,
        domain=domain.domain,
        created_at=domain.created_at,
        updated_at=domain.updated_at,
        document_count=document_count
    )
    return response

# Update a domain
@router.put("/{domain_id}", response_model=CrawledDomainResponse)
def update_domain(domain_id: int, domain: CrawledDomainUpdate, db: Session = Depends(get_db)):
    domain_repo = CrawledDomainRepository(db)
    updated_domain = domain_repo.update(domain_id, domain.model_dump(exclude_unset=True))
    if not updated_domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return updated_domain

# Delete a domain
@router.delete("/{domain_id}")
def delete_domain(domain_id: int, db: Session = Depends(get_db)):
    domain_repo = CrawledDomainRepository(db)
    domain = domain_repo.get(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    # Check if domain has documents
    document_repo = DocumentRepository(db)
    documents = document_repo.get_by_domain(domain_id)
    if documents:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete domain with existing documents. Delete documents first."
        )
    
    domain_repo.delete(domain_id)
    return {"message": "Domain deleted successfully"}

# List all domains
@router.get("/", response_model=List[CrawledDomainResponse])
def list_domains(
    db: Session = Depends(get_db)
):
    domain_repo = CrawledDomainRepository(db)
    document_repo = DocumentRepository(db)
    
    domains = domain_repo.get_all()
    response = []
    for domain in domains:
        document_count = len(document_repo.get_by_domain(domain.id))
        response.append(CrawledDomainResponse(
            id=domain.id,
            domain=domain.domain,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
            document_count=document_count
        ))
    return response

# Get domain by domain name
@router.get("/by-domain/{domain_name}", response_model=CrawledDomainResponse)
def get_domain_by_name(domain_name: str, db: Session = Depends(get_db)):
    domain_repo = CrawledDomainRepository(db)
    domain = domain_repo.get_by_domain(domain_name)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    # Get document count
    document_repo = DocumentRepository(db)
    document_count = len(document_repo.get_by_domain(domain.id))
    
    response = CrawledDomainResponse(
        id=domain.id,
        domain=domain.domain,
        created_at=domain.created_at,
        updated_at=domain.updated_at,
        document_count=document_count
    )
    return response

# Add a route for the root path without trailing slash
@router.get("", response_model=List[CrawledDomainResponse])
def list_domains_no_slash(
    db: Session = Depends(get_db)
):
    return list_domains(db) 