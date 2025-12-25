import json
from io import BytesIO
from typing import List, Optional
import re
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.database.models import Workflow, get_db
from database.repository import WorkflowRepository
from pydantic import BaseModel, Field, field_validator
from src.oauth.dependencies import (
    get_current_user,
    get_current_workspace
)

router = APIRouter(prefix="/workflows", tags=["workflows"])

# ------------------ Pydantic Schemas ------------------ #

class WorkflowNode(BaseModel):
    id: str = Field(..., min_length=1, description="Node ID")
    label: str = Field(..., min_length=1, description="Node label")
    type: str = Field(..., min_length=1, description="Node type")
    position: Optional[dict] = None
    conditions: Optional[list] = None
    next: Optional[str] = None
    description: Optional[str] = None
    ele: Optional[str] = None
    
    @field_validator('id', 'label', 'type')
    @classmethod
    def validate_non_empty_strings(cls, v):
        """Ensure strings are not empty or only whitespace"""
        if isinstance(v, str) and v.strip() == "":
            raise ValueError("must not be empty or whitespace only")
        return v.strip() if isinstance(v, str) else v

class WorkflowBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Workflow name")
    flow: List[WorkflowNode] = Field(..., min_length=1, description="Workflow nodes")
    status: bool = True
    
    @field_validator('name')
    @classmethod
    def validate_name_non_empty(cls, v):
        """Ensure name is not empty or only whitespace"""
        if v.strip() == "":
            raise ValueError("name must not be empty or whitespace only")
        return v.strip()
    
    @field_validator('flow')
    @classmethod
    def validate_flow_non_empty(cls, v):
        """Ensure flow has at least one node"""
        if not v:
            raise ValueError("flow must contain at least one node")
        return v

class WorkflowCreate(WorkflowBase):
    pass

class WorkflowUpdate(WorkflowBase):
    pass

class WorkflowResponse(WorkflowBase):
    id: int
    workspace_id: Optional[str] = None
    created_by: Optional[str] = None
    
    class Config:
        from_attributes = True


# ------------------ API Endpoints ------------------ #

@router.post("", response_model=WorkflowResponse)
def create_workflow(
    workflow: WorkflowCreate,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace),
    token_info: dict = Depends(get_current_user)
):
    """Create a new workflow in the current workspace"""
    repo = WorkflowRepository(db)
    
    # Validate unique name within workspace
    if repo.get_by_name(workflow.name, workspace_id=workspace_id):
        raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workflow with this name already exists in this workspace"
            )
    
    # Prepare workflow data
    workflow_data = workflow.model_dump()
    workflow_data["created_by"] = token_info.get("sub", "unknown")
    
    # Create workflow
    return repo.create(workflow_data, workspace_id)

@router.get("", response_model=List[WorkflowResponse])
def get_workflows(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace)
):
    """Get all workflows in the current workspace"""
    repo = WorkflowRepository(db)
    workflows = repo.get_all(workspace_id)
    return workflows[skip:skip + limit]

@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace)
):
    """Get a specific workflow from the current workspace"""
    repo = WorkflowRepository(db)
    workflow = repo.get(workflow_id, workspace_id)
    
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found in this workspace"
        )
    
    return workflow

@router.put("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(
    workflow_id: int,
    workflow: WorkflowUpdate,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace),
    token_info: dict = Depends(get_current_user)
):
    """Update a workflow in the current workspace"""
    repo = WorkflowRepository(db)
    
    # Check if workflow exists
    existing = repo.get(workflow_id, workspace_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found in this workspace"
        )
    
    # Validate unique name within workspace
    # Get workflow with the same name in this workspace
    found_with_name = repo.get_by_name(workflow.name, workspace_id)
    
    # If found and it's not the same workflow we're updating
    if found_with_name and found_with_name.id != workflow_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow with this name already exists in this workspace"
        )
    
    # Update workflow
    update_data = workflow.model_dump()
    updated = repo.update(workflow_id, update_data, workspace_id)
    
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found in this workspace"
        )
    
    return updated

@router.delete("/{workflow_id}")
def delete_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace)
):
    """Delete a workflow from the current workspace"""
    repo = WorkflowRepository(db)
    
    if not repo.delete(workflow_id, workspace_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found in this workspace"
        )
    
    return {"message": "Workflow deleted successfully"}

# ------------------ Export/Import ------------------ #

@router.get("/{workflow_id}/export")
def export_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace)
):
    """Export a workflow from the current workspace"""
    repo = WorkflowRepository(db)
    workflow = repo.get(workflow_id, workspace_id)
    
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found in this workspace"
        )

    # Convert to dict and remove workspace-specific fields
    workflow_dict = WorkflowResponse.model_validate(workflow).model_dump()
    export_dict = {k: v for k, v in workflow_dict.items() 
                   if k not in ['id', 'workspace_id', 'created_by']}
    
    # Create export file
    json_data = json.dumps(export_dict, ensure_ascii=False, indent=2)
    file_stream = BytesIO(json_data.encode("utf-8"))

    # Prepare filename
    safe_name = re.sub(r"[^\w\-]+", "_", workflow.name)
    ascii_name = safe_name.encode("ascii", "ignore").decode() or "workflow"
    quoted_name = urllib.parse.quote(workflow.name)

    headers = {
        "Content-Disposition": (
            f"attachment; filename=\"{ascii_name}.json\"; "
            f"filename*=UTF-8''{quoted_name}.json"
        )
    }

    return StreamingResponse(
        file_stream,
        media_type="application/json",
        headers=headers,
    )

@router.post("/import", response_model=WorkflowResponse)
def import_workflow(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_current_workspace),
    token_info: dict = Depends(get_current_user)
):
    """Import a workflow into the current workspace"""
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .json files are allowed"
        )

    # Parse JSON file
    try:
        contents = file.file.read()
        workflow_data = json.loads(contents)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON file: {str(e)}"
        )

    # Validate structure
    try:
        workflow_model = WorkflowCreate(**workflow_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid workflow structure: {str(e)}"
        )

    repo = WorkflowRepository(db)
    
       # Validate unique name within workspace
    if repo.get_by_name(workflow_model.name):
        raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workflow with this name already exists in this workspace"
            )
    
    # Prepare data
    workflow_dict = workflow_model.model_dump()
    workflow_dict["created_by"] = token_info.get("sub", "unknown")
    
    # Create workflow
    return repo.create(workflow_dict, workspace_id)