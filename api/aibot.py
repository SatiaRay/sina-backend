from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database.models import AiBot, User, Workspace, Document, Chat, Workflow, Instruction, SessionLocal, get_db
from pydantic import BaseModel
from datetime import datetime

from database.vector_store import VectorStore
from .auth import get_current_user

router = APIRouter(prefix="/aibots", tags=["aibots"])

# Pydantic Schemas
class AiBotCreate(BaseModel):
    name: str
    workspace_id: Optional[int] = None
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
    token: str  # Add this line
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
def create_aibot(aibot: AiBotCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Validate workspace exists
    workspace = db.query(Workspace).filter(Workspace.id == aibot.workspace_id).first() if aibot.workspace_id else user.current_workspace
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Validate owner exists and is a customer
    owner = db.query(User).filter(User.id == aibot.owner_id, User.user_type == 'customer').first()
    if not owner:
        raise HTTPException(status_code=400, detail="Owner must be a valid customer user.")
    
    # Create new Bot's vector database
    try:
        # TODO: Refactor to support custom parameters if needed
        container.make('vector_store')
    except:
        raise HTTPException(status_code=500, detail="Init database for new Ai Bot failed.")
    
    # Check if owner has access to the workspace
    workspace_user = db.query(Workspace).filter(
        Workspace.id == workspace.id,
        Workspace.owner_id == aibot.owner_id
    ).first()
    if not workspace_user:
        raise HTTPException(status_code=403, detail="Owner must have access to the workspace.")
    
    # Create AiBot
    new_aibot = AiBot(
        name=aibot.name,
        workspace_id=workspace.id,
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
    if doc.aibot_id == aibot_id:
        raise HTTPException(status_code=400, detail="Document already associated with this AiBot")
    
    # Update document to associate with this AiBot
    doc.aibot_id = aibot_id
    doc.vector_id = document.vectorize_id
    db.commit()
    db.refresh(doc)
    
    return AiBotDocumentOut(
        document_id=doc.id,
        vectorize_id=doc.vector_id,
        created_at=doc.updated_at
    )

# Remove document from AiBot
@router.delete("/{aibot_id}/documents/{document_id}", status_code=204)
def remove_document_from_aibot(aibot_id: int, document_id: int, db: Session = Depends(get_db)):
    # Validate AiBot exists
    aibot = db.query(AiBot).filter(AiBot.id == aibot_id).first()
    if not aibot:
        raise HTTPException(status_code=404, detail="AiBot not found")
    
    # Find document and check if it's associated with this AiBot
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.aibot_id == aibot_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not associated with this AiBot")
    
    # Remove association
    doc.aibot_id = None
    doc.vector_id = None
    db.commit()
    return

# List documents in AiBot
@router.get("/{aibot_id}/documents", response_model=List[AiBotDocumentOut])
def list_aibot_documents(aibot_id: int, db: Session = Depends(get_db)):
    # Validate AiBot exists
    aibot = db.query(AiBot).filter(AiBot.id == aibot_id).first()
    if not aibot:
        raise HTTPException(status_code=404, detail="AiBot not found")
    
    # Get documents associated with this AiBot
    documents = db.query(Document).filter(Document.aibot_id == aibot_id).all()
    
    # Convert to AiBotDocumentOut format
    aibot_docs = []
    for doc in documents:
        aibot_docs.append(AiBotDocumentOut(
            document_id=doc.id,
            vectorize_id=doc.vector_id,
            created_at=doc.updated_at
        ))
    
    return aibot_docs

# Get AiBot statistics
@router.get("/{aibot_id}/stats")
def get_aibot_stats(aibot_id: int, db: Session = Depends(get_db)):
    aibot = db.query(AiBot).filter(AiBot.id == aibot_id).first()
    if not aibot:
        raise HTTPException(status_code=404, detail="AiBot not found")
    
    # Count related records
    documents_count = db.query(Document).filter(Document.aibot_id == aibot_id).count()
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