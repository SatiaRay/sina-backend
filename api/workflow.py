import json
from io import BytesIO
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database.models import Workflow, get_db
from database.repositories.workflow_repository import WorkflowRepository
from pydantic import BaseModel, Field

router = APIRouter(prefix="/workflows", tags=["workflows"])

# ------------------ Pydantic Schemas ------------------ #

class WorkflowNode(BaseModel):
    id: str
    label: str
    type: str
    position: Optional[dict] = None
    conditions: Optional[list] = None
    next: Optional[str] = None
    description: Optional[str] = None
    ele: Optional[str] = None

class WorkflowBase(BaseModel):
    name: str
    flow: List[WorkflowNode]
    status: bool = True
    agent_type: Literal['voice_agent', 'text_agent', 'both'] = Field('text_agent', description='Agent type')

class WorkflowCreate(WorkflowBase):
    pass

class WorkflowUpdate(WorkflowBase):
    pass

class WorkflowResponse(WorkflowBase):
    id: int
    class Config:
        from_attributes = True

# ------------------ Existing APIs ------------------ #

@router.post("", response_model=WorkflowResponse)
def create_workflow(workflow: WorkflowCreate, db: Session = Depends(get_db)):
    repo = WorkflowRepository(db)
    if repo.get_by_name(workflow.name):
        raise HTTPException(status_code=400, detail="Workflow with this name already exists")
    db_workflow = Workflow(**workflow.model_dump())
    return repo.create(db_workflow)

@router.get("", response_model=List[WorkflowResponse])
def get_workflows(skip: int = 0, limit: int = 100, agent_type: str = 'text_agent', db: Session = Depends(get_db)):
    repo = WorkflowRepository(db)
    workflows = repo.get_all(agent_type=agent_type)
    return workflows[skip : skip + limit]

@router.get("/active", response_model=List[WorkflowResponse])
def get_active_workflows(agent_type: str = 'text_agent', db: Session = Depends(get_db)):
    repo = WorkflowRepository(db)
    return repo.get_active_workflows(agent_type=agent_type)

@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(workflow_id: int, db: Session = Depends(get_db)):
    repo = WorkflowRepository(db)
    workflow = repo.get_by_id(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow

@router.put("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(workflow_id: int, workflow: WorkflowUpdate, db: Session = Depends(get_db)):
    repo = WorkflowRepository(db)
    updated_workflow = repo.update(workflow_id, workflow.model_dump())
    if updated_workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return updated_workflow

@router.delete("/{workflow_id}")
def delete_workflow(workflow_id: int, db: Session = Depends(get_db)):
    repo = WorkflowRepository(db)
    if not repo.delete(workflow_id):
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"message": "Workflow deleted successfully"}

# ------------------ NEW Export API ------------------ #

@router.get("/{workflow_id}/export")
def export_workflow(workflow_id: int, db: Session = Depends(get_db)):
    """
    Export a workflow as a downloadable JSON file.
    """
    repo = WorkflowRepository(db)
    workflow = repo.get_by_id(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Serialize to dict
    workflow_dict = WorkflowResponse.model_validate(workflow).model_dump()
    json_data = json.dumps(workflow_dict, ensure_ascii=False, indent=2)

    # In-memory file
    file_stream = BytesIO(json_data.encode("utf-8"))
    filename = f"workflow_{workflow_id}.json"

    return StreamingResponse(
        file_stream,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

# ------------------ NEW Import API ------------------ #

@router.post("/import", response_model=WorkflowResponse)
def import_workflow(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Import a workflow from an exported JSON file.
    """
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files are allowed")

    try:
        contents = file.file.read()
        workflow_data = json.loads(contents)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON file format")

    try:
        workflow_model = WorkflowCreate(**workflow_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON structure is invalid: {str(e)}")

    repo = WorkflowRepository(db)

    if repo.get_by_name(workflow_model.name):
        raise HTTPException(status_code=400, detail="Workflow with this name already exists")

    db_workflow = Workflow(**workflow_model.model_dump())
    return repo.create(db_workflow)
