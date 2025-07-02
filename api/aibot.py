from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database.models import AiBot, User, Workspace, Document, Chat, Workflow, Instruction, AiBotDocument, SessionLocal, get_db
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/aibots", tags=["aibots"])

# Pydantic Schemas
class AiBotCreate(BaseModel):
    name: str
    workspace_id: int
    owner_id: int

class AiBotUpdate(BaseModel):
    name: Optional[str] = None

class AiBotDocumentAdd(BaseModel):
    document_id: int
    vectorize_id: Optional[str] = None

class AiBotDocumentOut(BaseModel):
    document_id: int
    vectorize_id: Optional[str]
    created_at: Optional[datetime]
    class Config:
        from_attributes = True

class AiBotOut(BaseModel):
    id: int
    name: str
    workspace_id: int
    owner_id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    class Config:
        from_attributes = True

class PaginatedAiBotResponse(BaseModel):
    aibots: List[AiBotOut]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool

# Create AiBot
@router.post("/", response_model=AiBotOut)
def create_aibot(aibot: AiBotCreate, db: Session = Depends(get_db)):
    # Validate workspace exists
    workspace = db.query(Workspace).filter(Workspace.id == aibot.workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Validate owner exists and is a customer
    owner = db.query(User).filter(User.id == aibot.owner_id, User.user_type == 'customer').first()
    if not owner:
        raise HTTPException(status_code=400, detail="Owner must be a valid customer user.")
    
    # Check if owner has access to the workspace
    workspace_user = db.query(Workspace).filter(
        Workspace.id == aibot.workspace_id,
        Workspace.owner_id == aibot.owner_id
    ).first()
    if not workspace_user:
        raise HTTPException(status_code=403, detail="Owner must have access to the workspace.")
    
    # Create AiBot
    new_aibot = AiBot(
        name=aibot.name,
        workspace_id=aibot.workspace_id,
        owner_id=aibot.owner_id
    )
    db.add(new_aibot)
    db.commit()
    db.refresh(new_aibot)
    return new_aibot

# Get all AiBots with pagination
@router.get("/", response_model=PaginatedAiBotResponse)
def list_aibots(
    page: int = Query(1, description="Page number (starting from 1)", ge=1),
    per_page: int = Query(10, description="Number of AiBots per page", ge=1, le=100),
    workspace_id: Optional[int] = Query(None, description="Filter by workspace ID"),
    owner_id: Optional[int] = Query(None, description="Filter by owner ID"),
    db: Session = Depends(get_db)
):
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Build query with filters
    query = db.query(AiBot)
    if workspace_id:
        query = query.filter(AiBot.workspace_id == workspace_id)
    if owner_id:
        query = query.filter(AiBot.owner_id == owner_id)
    
    # Get total count
    total = query.count()
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    
    # Get AiBots for current page
    aibots = query.offset(offset).limit(per_page).all()
    
    return PaginatedAiBotResponse(
        aibots=aibots,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )

# Get AiBot by id
@router.get("/{aibot_id}", response_model=AiBotOut)
def get_aibot(aibot_id: int, db: Session = Depends(get_db)):
    aibot = db.query(AiBot).filter(AiBot.id == aibot_id).first()
    if not aibot:
        raise HTTPException(status_code=404, detail="AiBot not found")
    return aibot

# Update AiBot
@router.put("/{aibot_id}", response_model=AiBotOut)
def update_aibot(aibot_id: int, update: AiBotUpdate, db: Session = Depends(get_db)):
    aibot = db.query(AiBot).filter(AiBot.id == aibot_id).first()
    if not aibot:
        raise HTTPException(status_code=404, detail="AiBot not found")
    
    for field, value in update.dict(exclude_unset=True).items():
        setattr(aibot, field, value)
    
    db.commit()
    db.refresh(aibot)
    return aibot

# Delete AiBot
@router.delete("/{aibot_id}", status_code=204)
def delete_aibot(aibot_id: int, db: Session = Depends(get_db)):
    aibot = db.query(AiBot).filter(AiBot.id == aibot_id).first()
    if not aibot:
        raise HTTPException(status_code=404, detail="AiBot not found")
    
    # Delete associated AiBotDocument relationships
    db.query(AiBotDocument).filter(AiBotDocument.aibot_id == aibot_id).delete()
    
    # Delete the AiBot (cascade will handle related records)
    db.delete(aibot)
    db.commit()
    return

# Add document to AiBot
@router.post("/{aibot_id}/documents", response_model=AiBotDocumentOut)
def add_document_to_aibot(aibot_id: int, document: AiBotDocumentAdd, db: Session = Depends(get_db)):
    # Validate AiBot exists
    aibot = db.query(AiBot).filter(AiBot.id == aibot_id).first()
    if not aibot:
        raise HTTPException(status_code=404, detail="AiBot not found")
    
    # Validate document exists and belongs to the same workspace
    doc = db.query(Document).filter(
        Document.id == document.document_id,
        Document.workspace_id == aibot.workspace_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or not accessible")
    
    # Check if document is already associated with this AiBot
    existing = db.query(AiBotDocument).filter_by(
        aibot_id=aibot_id, 
        document_id=document.document_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Document already associated with this AiBot")
    
    # Create association
    aibot_doc = AiBotDocument(
        aibot_id=aibot_id,
        document_id=document.document_id,
        vectorize_id=document.vectorize_id
    )
    db.add(aibot_doc)
    db.commit()
    db.refresh(aibot_doc)
    return aibot_doc

# Remove document from AiBot
@router.delete("/{aibot_id}/documents/{document_id}", status_code=204)
def remove_document_from_aibot(aibot_id: int, document_id: int, db: Session = Depends(get_db)):
    aibot_doc = db.query(AiBotDocument).filter_by(
        aibot_id=aibot_id, 
        document_id=document_id
    ).first()
    if not aibot_doc:
        raise HTTPException(status_code=404, detail="Document not associated with this AiBot")
    
    db.delete(aibot_doc)
    db.commit()
    return

# List documents in AiBot
@router.get("/{aibot_id}/documents", response_model=List[AiBotDocumentOut])
def list_aibot_documents(aibot_id: int, db: Session = Depends(get_db)):
    # Validate AiBot exists
    aibot = db.query(AiBot).filter(AiBot.id == aibot_id).first()
    if not aibot:
        raise HTTPException(status_code=404, detail="AiBot not found")
    
    aibot_docs = db.query(AiBotDocument).filter_by(aibot_id=aibot_id).all()
    return aibot_docs

# Get AiBot statistics
@router.get("/{aibot_id}/stats")
def get_aibot_stats(aibot_id: int, db: Session = Depends(get_db)):
    aibot = db.query(AiBot).filter(AiBot.id == aibot_id).first()
    if not aibot:
        raise HTTPException(status_code=404, detail="AiBot not found")
    
    # Count related records
    documents_count = db.query(AiBotDocument).filter_by(aibot_id=aibot_id).count()
    chats_count = db.query(Chat).filter_by(aibot_id=aibot_id).count()
    workflows_count = db.query(Workflow).filter_by(aibot_id=aibot_id).count()
    instructions_count = db.query(Instruction).filter_by(aibot_id=aibot_id).count()
    
    return {
        "aibot_id": aibot_id,
        "name": aibot.name,
        "documents_count": documents_count,
        "chats_count": chats_count,
        "workflows_count": workflows_count,
        "instructions_count": instructions_count,
        "created_at": aibot.created_at,
        "updated_at": aibot.updated_at
    } 