from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone

from src.database.models import get_db
from src.database.repository import WizardRepository
from src.api.dependencies.oauth import get_current_user, get_current_workspace

router = APIRouter(prefix="/wizards", tags=["wizards"])


# Pydantic models for request/response
class WizardBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    context: Optional[str] = None
    parent_id: Optional[int] = None
    enabled: bool = True
    wizard_type: Literal["answer", "question"]

    @field_validator('title')
    @classmethod
    def validate_title_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()


class WizardCreate(WizardBase):
    pass


class WizardUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    context: Optional[str] = None
    parent_id: Optional[int] = None
    enabled: Optional[bool] = None
    wizard_type: Optional[Literal["answer", "question"]] = None

    @field_validator('title')
    @classmethod
    def validate_title_not_empty(cls, v):
        if v is not None:
            if not v or not v.strip():
                raise ValueError('Title cannot be empty')
            return v.strip()
        return v


class WizardResponse(WizardBase):
    id: int
    created_by: str
    workspace_id: str
    created_at: datetime
    updated_at: datetime
    children: List["WizardResponse"] = []

    class Config:
        from_attributes = True


WizardResponse.model_rebuild()


# Get root wizards
@router.get("/", response_model=List[WizardResponse])
async def get_root_wizards(
    db: Session = Depends(get_db),
    current_workspace_id: str = Depends(get_current_workspace)
):
    """Get all root wizards (wizards without parents)"""
    try:
        repo = WizardRepository(db)
        wizards = repo.get_root_wizards(workspace_id=current_workspace_id)
        return wizards
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Create a new wizard
@router.post("/", response_model=WizardResponse)
def create_wizard(
    wizard: WizardCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    current_workspace_id: str = Depends(get_current_workspace)
):
    wizard_repo = WizardRepository(db)
    
    wizard_data = wizard.model_dump()
    wizard_data['created_by'] = current_user.get('sub', current_user.get('username', 'unknown'))
    wizard_data['workspace_id'] = current_workspace_id
    
    return wizard_repo.create(wizard_data)


# Get a wizard by ID
@router.get("/{wizard_id}", response_model=WizardResponse)
async def get_wizard(
    wizard_id: int,
    db: Session = Depends(get_db),
    current_workspace_id: str = Depends(get_current_workspace)
):
    """Get a wizard by ID with its children"""
    try:
        repo = WizardRepository(db)
        wizard = repo.get(id=wizard_id, workspace_id=current_workspace_id)
        
        if not wizard:
            raise HTTPException(status_code=404, detail="Wizard not found")
        
        return wizard
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Update a wizard
@router.put("/{wizard_id}", response_model=WizardResponse)
def update_wizard(
    wizard_id: int,
    wizard: WizardUpdate,
    db: Session = Depends(get_db),
    current_workspace_id: str = Depends(get_current_workspace)
):
    """Update a wizard"""
    wizard_repo = WizardRepository(db)
    
    # BaseRepository.update expects 'id' parameter, not 'wizard_id'
    updated_wizard = wizard_repo.update(
        id=wizard_id,  # Changed from wizard_id to id
        data=wizard.model_dump(exclude_unset=True),
        workspace_id=current_workspace_id
    )
    
    if not updated_wizard:
        raise HTTPException(status_code=404, detail="Wizard not found")
    
    return updated_wizard


# Delete a wizard
@router.delete("/{wizard_id}")
def delete_wizard(
    wizard_id: int,
    db: Session = Depends(get_db),
    current_workspace_id: str = Depends(get_current_workspace)
):
    """Delete a wizard"""
    wizard_repo = WizardRepository(db)
    
    # BaseRepository.delete expects 'id' parameter, not 'wizard_id'
    if not wizard_repo.delete(id=wizard_id, workspace_id=current_workspace_id):
        raise HTTPException(status_code=404, detail="Wizard not found")
    
    return {"message": "Wizard deleted successfully"}