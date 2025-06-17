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
    children: List['WizardResponse'] = []

    class Config:
        from_attributes = True

# Update the forward reference for children
WizardResponse.model_rebuild()

# Get root wizards - This must come BEFORE the {wizard_id} route
@router.get("/hierarchy/roots", response_model=List[WizardResponse])
async def get_root_wizards(
    enable_only: bool = True,
    db: Session = Depends(get_db)
):
    """
    Get all root wizards (wizards without parents)
    
    - **enable_only**: If True, only return enabled wizards
    """
    try:
        repo = WizardRepository(db)
        wizards = repo.get_root_wizards(enable_only=enable_only)
        return wizards
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

# Create a new wizard
@router.post("/", response_model=WizardResponse)
def create_wizard(wizard: WizardCreate, db: Session = Depends(get_db)):
    wizard_repo = WizardRepository(db)
    return wizard_repo.create(wizard.model_dump())

# Add a route for the root path without trailing slash
@router.post("", response_model=WizardResponse)
def create_wizard_no_slash(wizard: WizardCreate, db: Session = Depends(get_db)):
    wizard_repo = WizardRepository(db)
    return wizard_repo.create(wizard.model_dump())

# Add a route for the root path without trailing slash
@router.get("", response_model=List[WizardResponse])
def list_wizards_no_slash(
    enable_only: bool = Query(False, description="Only return enabled wizards"),
    parent_id: Optional[int] = Query(None, description="Filter by parent ID"),
    db: Session = Depends(get_db)
):
    return list_wizards(enable_only, parent_id, db)

# Original route with trailing slash
@router.get("/", response_model=List[WizardResponse])
def list_wizards(
    enable_only: bool = Query(False, description="Only return enabled wizards"),
    parent_id: Optional[int] = Query(None, description="Filter by parent ID"),
    db: Session = Depends(get_db)
):
    wizard_repo = WizardRepository(db)
    if parent_id is not None:
        return wizard_repo.get_by_parent(parent_id, enable_only)
    return wizard_repo.get_heads(enable_only=enable_only)

# Get a wizard by ID - This must come AFTER all specific paths
@router.get("/{wizard_id}", response_model=WizardResponse)
async def get_wizard(
    wizard_id: int,
    enable_only: bool = Query(False, description="Only return enabled wizards"),
    db: Session = Depends(get_db)
):
    """
    Get a specific wizard by ID
    
    - **wizard_id**: The ID of the wizard to retrieve
    - **enable_only**: If True, only return enabled wizards
    """
    try:
        repo = WizardRepository(db)
        wizard = repo.get(wizard_id, enable_only=enable_only)
        if not wizard:
            raise HTTPException(status_code=404, detail="Wizard not found")
        if enable_only and not wizard.enabled:
            raise HTTPException(status_code=404, detail="Wizard is disabled")
        return wizard
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

# Get wizard hierarchy
@router.get("/{wizard_id}/hierarchy", response_model=List[WizardResponse])
def get_wizard_hierarchy(
    wizard_id: int,
    enable_only: bool = Query(True, description="Only return enabled wizards"),
    db: Session = Depends(get_db)
):
    wizard_repo = WizardRepository(db)
    hierarchy = wizard_repo.get_wizard_hierarchy(wizard_id, enable_only)
    if not hierarchy:
        raise HTTPException(status_code=404, detail="Wizard not found")
    return hierarchy

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

