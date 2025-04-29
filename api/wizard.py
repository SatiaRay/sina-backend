from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from database.models import get_db
from database.repository import WizardRepository

router = APIRouter(prefix="/wizards", tags=["wizards"])

# Pydantic models for request/response
class WizardBase(BaseModel):
    title: str
    context: Optional[str] = None
    parent_id: Optional[int] = None
    enabled: bool = True

class WizardCreate(WizardBase):
    pass

class WizardUpdate(WizardBase):
    title: Optional[str] = None
    enabled: Optional[bool] = None

class WizardResponse(WizardBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Create a new wizard
@router.post("/", response_model=WizardResponse)
def create_wizard(wizard: WizardCreate, db: Session = Depends(get_db)):
    wizard_repo = WizardRepository(db)
    return wizard_repo.create(wizard.model_dump())

# Get a wizard by ID
@router.get("/{wizard_id}", response_model=WizardResponse)
def get_wizard(wizard_id: int, db: Session = Depends(get_db)):
    wizard_repo = WizardRepository(db)
    wizard = wizard_repo.get(wizard_id)
    if not wizard:
        raise HTTPException(status_code=404, detail="Wizard not found")
    return wizard

# Update a wizard
@router.put("/{wizard_id}", response_model=WizardResponse)
def update_wizard(wizard_id: int, wizard: WizardUpdate, db: Session = Depends(get_db)):
    wizard_repo = WizardRepository(db)
    updated_wizard = wizard_repo.update(wizard_id, wizard.model_dump(exclude_unset=True))
    if not updated_wizard:
        raise HTTPException(status_code=404, detail="Wizard not found")
    return updated_wizard

# Delete a wizard
@router.delete("/{wizard_id}")
def delete_wizard(wizard_id: int, db: Session = Depends(get_db)):
    wizard_repo = WizardRepository(db)
    if not wizard_repo.delete(wizard_id):
        raise HTTPException(status_code=404, detail="Wizard not found")
    return {"message": "Wizard deleted successfully"}

# List all wizards
@router.get("/", response_model=List[WizardResponse])
def list_wizards(
    enabled_only: bool = Query(True, description="Only return enabled wizards"),
    parent_id: Optional[int] = Query(None, description="Filter by parent ID"),
    db: Session = Depends(get_db)
):
    wizard_repo = WizardRepository(db)
    if parent_id is not None:
        return wizard_repo.get_by_parent(parent_id, enabled_only)
    return wizard_repo.get_all()

# Get wizard hierarchy
@router.get("/{wizard_id}/hierarchy", response_model=List[WizardResponse])
def get_wizard_hierarchy(
    wizard_id: int,
    enabled_only: bool = Query(True, description="Only return enabled wizards"),
    db: Session = Depends(get_db)
):
    wizard_repo = WizardRepository(db)
    hierarchy = wizard_repo.get_wizard_hierarchy(wizard_id, enabled_only)
    if not hierarchy:
        raise HTTPException(status_code=404, detail="Wizard not found")
    return hierarchy

# Get root wizards
@router.get("/roots", response_model=List[WizardResponse])
def get_root_wizards(
    enabled_only: bool = Query(True, description="Only return enabled wizards"),
    db: Session = Depends(get_db)
):
    wizard_repo = WizardRepository(db)
    return wizard_repo.get_root_wizards(enabled_only)

# Enable a wizard
@router.post("/{wizard_id}/enable", response_model=WizardResponse)
def enable_wizard(wizard_id: int, db: Session = Depends(get_db)):
    wizard_repo = WizardRepository(db)
    wizard = wizard_repo.enable_wizard(wizard_id)
    if not wizard:
        raise HTTPException(status_code=404, detail="Wizard not found")
    return wizard

# Disable a wizard
@router.post("/{wizard_id}/disable", response_model=WizardResponse)
def disable_wizard(wizard_id: int, db: Session = Depends(get_db)):
    wizard_repo = WizardRepository(db)
    wizard = wizard_repo.disable_wizard(wizard_id)
    if not wizard:
        raise HTTPException(status_code=404, detail="Wizard not found")
    return wizard

# Get enabled wizards
@router.get("/enabled", response_model=List[WizardResponse])
def get_enabled_wizards(db: Session = Depends(get_db)):
    wizard_repo = WizardRepository(db)
    return wizard_repo.get_enabled_wizards()

# Get disabled wizards
@router.get("/disabled", response_model=List[WizardResponse])
def get_disabled_wizards(db: Session = Depends(get_db)):
    wizard_repo = WizardRepository(db)
    return wizard_repo.get_disabled_wizards() 