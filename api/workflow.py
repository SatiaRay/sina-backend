from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.models import Workflow
from database.repositories.workflow_repository import WorkflowRepository
from database.models import get_db
from pydantic import BaseModel

router = APIRouter(prefix="/workflows", tags=["workflows"])

class WorkflowNode(BaseModel):
    id: str
    label: str
    type: str
    position: Optional[dict] = None
    conditions: Optional[list] = None
    next: Optional[str] = None
    description: Optional[str] = None

class WorkflowBase(BaseModel):
    name: str
    flow: List[WorkflowNode]
    status: bool = True

class WorkflowCreate(WorkflowBase):
    pass

class WorkflowUpdate(WorkflowBase):
    pass

class WorkflowResponse(WorkflowBase):
    id: int

    class Config:
        from_attributes = True

@router.post("", response_model=WorkflowResponse)
def create_workflow(workflow: WorkflowCreate, db: Session = Depends(get_db)):
    repo = WorkflowRepository(db)
    # Check if workflow with same name exists
    if repo.get_by_name(workflow.name):
        raise HTTPException(status_code=400, detail="Workflow with this name already exists")
    
    db_workflow = Workflow(**workflow.model_dump())
    return repo.create(db_workflow)

@router.get("", response_model=List[WorkflowResponse])
def get_workflows(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    repo = WorkflowRepository(db)
    workflows = repo.get_all()
    return workflows[skip : skip + limit]

@router.get("/active", response_model=List[WorkflowResponse])
def get_active_workflows(db: Session = Depends(get_db)):
    repo = WorkflowRepository(db)
    return repo.get_active_workflows()

@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(workflow_id: int, db: Session = Depends(get_db)):
    repo = WorkflowRepository(db)
    workflow = repo.get_by_id(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow

@router.put("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(workflow_id: int, workflow: WorkflowUpdate, db: Session = Depends(get_db)):
    print(workflow)
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
