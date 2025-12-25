from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database.repository import InstructionRepository
from src.database.models import get_db
from pydantic import BaseModel, Field, validator
from datetime import datetime
from src.oauth.dependencies import get_current_user, get_current_workspace

router = APIRouter()


class InstructionBase(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)
    text: str = Field(..., min_length=1)
    status: bool = True
    workspace_id: Optional[str] = None  # Will be set from current workspace

    @validator("label", "text")
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class InstructionCreate(InstructionBase):
    pass


class InstructionUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=255)
    text: Optional[str] = Field(None, min_length=1)
    status: Optional[bool] = None

    @validator("label", "text")
    def validate_not_empty(cls, v):
        if v is not None:
            if not v or not v.strip():
                raise ValueError("Field cannot be empty")
            return v.strip()
        return v


class InstructionResponse(InstructionBase):
    id: int
    workspace_id: str  # Always required in response
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None  # User ID from token

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    items: List[InstructionResponse]
    total: int
    page: int
    size: int
    pages: int


@router.post("/instructions/", response_model=InstructionResponse)
def create_instruction(
    instruction: InstructionCreate,
    db: Session = Depends(get_db),
    current_workspace_id: str = Depends(get_current_workspace),
    current_user: dict = Depends(get_current_user)
):
    """Create instruction in current workspace"""
    repo = InstructionRepository(db)
    
    # Override workspace_id with current workspace
    instruction_data = instruction.dict()
    instruction_data['workspace_id'] = current_workspace_id
    instruction_data['created_by'] = current_user.get('sub', current_user.get('username'))
    
    return repo.create(instruction_data)


@router.get("/instructions/", response_model=PaginatedResponse)
def get_instructions(
    active_only: bool = False,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_workspace_id: str = Depends(get_current_workspace)
):
    """Get instructions from current workspace"""
    repo = InstructionRepository(db)
    
    if active_only:
        items, total = repo.get_active_instructions_paginated(
            page, size, workspace_id=current_workspace_id
        )
    else:
        items, total = repo.get_all_paginated(
            page, size, workspace_id=current_workspace_id
        )

    pages = (total + size - 1) // size  # Ceiling division

    return PaginatedResponse(
        items=items, total=total, page=page, size=size, pages=pages
    )


@router.get("/instructions/{instruction_id}", response_model=InstructionResponse)
def get_instruction(
    instruction_id: int,
    db: Session = Depends(get_db),
    current_workspace_id: str = Depends(get_current_workspace)
):
    """Get instruction by ID from current workspace"""
    repo = InstructionRepository(db)
    instruction = repo.get(instruction_id, workspace_id=current_workspace_id)
    if not instruction:
        raise HTTPException(status_code=404, detail="Instruction not found")
    return instruction


@router.put("/instructions/{instruction_id}", response_model=InstructionResponse)
def update_instruction(
    instruction_id: int,
    instruction: InstructionUpdate,
    db: Session = Depends(get_db),
    current_workspace_id: str = Depends(get_current_workspace)
):
    """Update instruction in current workspace"""
    repo = InstructionRepository(db)
    
    # Check if instruction exists in current workspace
    existing_instruction = repo.get(instruction_id, workspace_id=current_workspace_id)
    if not existing_instruction:
        raise HTTPException(status_code=404, detail="Instruction not found")
    
    updated_instruction = repo.update(
        instruction_id, 
        instruction.dict(exclude_unset=True),
        workspace_id=current_workspace_id
    )
    return updated_instruction


@router.delete("/instructions/{instruction_id}")
def delete_instruction(
    instruction_id: int,
    db: Session = Depends(get_db),
    current_workspace_id: str = Depends(get_current_workspace)
):
    """Delete instruction from current workspace"""
    repo = InstructionRepository(db)
    
    # The delete method already checks if the instruction exists
    if not repo.delete(instruction_id, workspace_id=current_workspace_id):
        raise HTTPException(status_code=404, detail="Instruction not found")
    
    return {"message": "Instruction deleted successfully"}


@router.patch("/instructions/{instruction_id}/enable", response_model=InstructionResponse)
def enable_instruction(
    instruction_id: int,
    db: Session = Depends(get_db),
    current_workspace_id: str = Depends(get_current_workspace)
):
    """Enable instruction in current workspace"""
    repo = InstructionRepository(db)
    instruction = repo.enable_instruction(instruction_id, workspace_id=current_workspace_id)
    if not instruction:
        raise HTTPException(status_code=404, detail="Instruction not found")
    return instruction


@router.patch("/instructions/{instruction_id}/disable", response_model=InstructionResponse)
def disable_instruction(
    instruction_id: int,
    db: Session = Depends(get_db),
    current_workspace_id: str = Depends(get_current_workspace)
):
    """Disable instruction in current workspace"""
    repo = InstructionRepository(db)
    instruction = repo.disable_instruction(instruction_id, workspace_id=current_workspace_id)
    if not instruction:
        raise HTTPException(status_code=404, detail="Instruction not found")
    return instruction