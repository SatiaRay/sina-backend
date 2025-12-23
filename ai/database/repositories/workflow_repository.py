from typing import Any, Dict, List, Optional, Union
from sqlalchemy.orm import Session
import uuid
from database.models import Workflow


class WorkflowRepository:
    def __init__(self, db: Session, workspace_id: Optional[Union[str, uuid.UUID]] = None):
        self.db = db
        self.workspace_id = workspace_id
        if workspace_id and isinstance(workspace_id, str):
            self.workspace_id = uuid.UUID(workspace_id)

    def _apply_workspace_filter(self, query):
        """Apply workspace filter to query if workspace_id is set"""
        if self.workspace_id:
            query = query.filter(Workflow.workspace_id == self.workspace_id)
        return query

    def _ensure_workspace_id(self, workflow: Workflow) -> Workflow:
        """Ensure workspace_id is set on workflow"""
        if self.workspace_id and not workflow.workspace_id:
            workflow.workspace_id = self.workspace_id
        elif not self.workspace_id and not workflow.workspace_id:
            raise ValueError("workspace_id must be provided either in constructor or on workflow object")
        return workflow

    def create(self, workflow: Workflow) -> Workflow:
        """Create a new workflow with workspace isolation"""
        workflow = self._ensure_workspace_id(workflow)
        self.db.add(workflow)
        self.db.commit()
        self.db.refresh(workflow)
        return workflow

    def get_by_id(self, workflow_id: int) -> Optional[Workflow]:
        """Get workflow by ID within current workspace"""
        query = self.db.query(Workflow).filter(Workflow.id == workflow_id)
        query = self._apply_workspace_filter(query)
        return query.first()

    def get_by_name(self, name: str) -> Optional[Workflow]:
        """Get workflow by name within current workspace"""
        query = self.db.query(Workflow).filter(Workflow.name == name)
        query = self._apply_workspace_filter(query)
        return query.first()

    def get_all(self) -> List[Workflow]:
        """Get all workflows within current workspace"""
        query = self.db.query(Workflow)
        query = self._apply_workspace_filter(query)
        return query.all()

    def update(self, workflow_id: int, workflow_data: dict) -> Optional[Workflow]:
        """Update workflow within current workspace"""
        workflow = self.get_by_id(workflow_id)
        if workflow:
            # Don't allow changing workspace_id
            if 'workspace_id' in workflow_data:
                del workflow_data['workspace_id']
                
            for key, value in workflow_data.items():
                setattr(workflow, key, value)
            self.db.commit()
            self.db.refresh(workflow)
        return workflow

    def delete(self, workflow_id: int) -> bool:
        """Delete workflow within current workspace"""
        workflow = self.get_by_id(workflow_id)
        if workflow:
            self.db.delete(workflow)
            self.db.commit()
            return True
        return False

    def get_active_workflows(self) -> List[Workflow]:
        """Get all active workflows within current workspace"""
        query = self.db.query(Workflow).filter(Workflow.status == True)
        query = self._apply_workspace_filter(query)
        return query.all()

    def get_active_workflows_flows(self) -> List[Dict[str, Any]]:
        """
        Retrieve flows of all active workflows from the database within current workspace.
        
        Returns:
            List[Dict[str, Any]]: List of flows from active workflows
        """
        try:
            # Query active workflows and extract only their flows
            query = self.db.query(Workflow.flow).filter(Workflow.status == True)
            query = self._apply_workspace_filter(query)

            workflows = query.all()
            
            # Extract flows from the query results
            return [workflow[0] for workflow in workflows if workflow[0] is not None]
        except Exception as e:
            self.db.rollback()
            raise e

    def get_by_status(self, status: bool) -> List[Workflow]:
        """Get workflows by status within current workspace"""
        query = self.db.query(Workflow).filter(Workflow.status == status)
        query = self._apply_workspace_filter(query)
        return query.all()

    def count(self) -> int:
        """Count workflows within current workspace"""
        query = self.db.query(Workflow)
        query = self._apply_workspace_filter(query)
        return query.count()

    def get_paginated(self, page: int = 1, per_page: int = 20) -> List[Workflow]:
        """Get paginated workflows within current workspace"""
        offset = (page - 1) * per_page
        query = self.db.query(Workflow)
        query = self._apply_workspace_filter(query)
        return query.offset(offset).limit(per_page).all()

    def search_by_name(self, name_part: str) -> List[Workflow]:
        """Search workflows by name within current workspace"""
        query = self.db.query(Workflow).filter(
            Workflow.name.ilike(f"%{name_part}%")
        )
        query = self._apply_workspace_filter(query)
        return query.all()