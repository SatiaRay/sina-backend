from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database.models import Workspace, User, WorkspaceUser, SessionLocal, get_db
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

# Pydantic Schemas
class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    owner_id: int

class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class WorkspaceUserAdd(BaseModel):
    user_id: int
    role: Optional[str] = "member"

class WorkspaceUserOut(BaseModel):
    user_id: int
    role: str
    joined_at: Optional[datetime]
    class Config:
        from_attributes = True

class WorkspaceOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    is_active: bool
    class Config:
        from_attributes = True

class PaginatedWorkspaceResponse(BaseModel):
    workspaces: List[WorkspaceOut]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool

# Create workspace
@router.post("/", response_model=WorkspaceOut)
def create_workspace(workspace: WorkspaceCreate, db: Session = Depends(get_db)):
    owner = db.query(User).filter(User.id == workspace.owner_id, User.user_type == 'customer').first()
    if not owner:
        raise HTTPException(status_code=400, detail="Owner must be a valid customer user.")
    ws = Workspace(name=workspace.name, description=workspace.description, owner_id=workspace.owner_id)
    db.add(ws)
    db.commit()
    db.refresh(ws)
    # Add owner to workspace_users as 'owner'
    ws_user = WorkspaceUser(workspace_id=ws.id, user_id=workspace.owner_id, role='owner')
    db.add(ws_user)
    db.commit()
    return ws

# Get all workspaces with pagination
@router.get("/", response_model=PaginatedWorkspaceResponse)
def list_workspaces(
    page: int = Query(1, description="Page number (starting from 1)", ge=1),
    per_page: int = Query(10, description="Number of workspaces per page", ge=1, le=100),
    db: Session = Depends(get_db)
):
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Get total count
    total = db.query(Workspace).count()
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    
    # Get workspaces for current page
    workspaces = db.query(Workspace).offset(offset).limit(per_page).all()
    
    return PaginatedWorkspaceResponse(
        workspaces=workspaces,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )

# Get workspace by id
@router.get("/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(workspace_id: int, db: Session = Depends(get_db)):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws

# Update workspace
@router.put("/{workspace_id}", response_model=WorkspaceOut)
def update_workspace(workspace_id: int, update: WorkspaceUpdate, db: Session = Depends(get_db)):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    for field, value in update.dict(exclude_unset=True).items():
        setattr(ws, field, value)
    db.commit()
    db.refresh(ws)
    return ws

# Delete workspace
@router.delete("/{workspace_id}", status_code=204)
def delete_workspace(workspace_id: int, db: Session = Depends(get_db)):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Delete all workspace users first to avoid foreign key constraint issues
    db.query(WorkspaceUser).filter(WorkspaceUser.workspace_id == workspace_id).delete()
    
    # Now delete the workspace
    db.delete(ws)
    db.commit()
    return

# Add user to workspace
@router.post("/{workspace_id}/users", response_model=WorkspaceUserOut)
def add_user_to_workspace(workspace_id: int, user: WorkspaceUserAdd, db: Session = Depends(get_db)):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    u = db.query(User).filter(User.id == user.user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    existing = db.query(WorkspaceUser).filter_by(workspace_id=workspace_id, user_id=user.user_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already in workspace")
    ws_user = WorkspaceUser(workspace_id=workspace_id, user_id=user.user_id, role=user.role)
    db.add(ws_user)
    db.commit()
    db.refresh(ws_user)
    return ws_user

# Remove user from workspace
@router.delete("/{workspace_id}/users/{user_id}", status_code=204)
def remove_user_from_workspace(workspace_id: int, user_id: int, db: Session = Depends(get_db)):
    ws_user = db.query(WorkspaceUser).filter_by(workspace_id=workspace_id, user_id=user_id).first()
    if not ws_user:
        raise HTTPException(status_code=404, detail="User not in workspace")
    db.delete(ws_user)
    db.commit()
    return

# List users in workspace
@router.get("/{workspace_id}/users", response_model=List[WorkspaceUserOut])
def list_workspace_users(workspace_id: int, db: Session = Depends(get_db)):
    ws_users = db.query(WorkspaceUser).filter_by(workspace_id=workspace_id).all()
    return ws_users 