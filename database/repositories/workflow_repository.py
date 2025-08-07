from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from database.models import Workflow

class WorkflowRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, workflow: Workflow) -> Workflow:
        self.db.add(workflow)
        self.db.commit()
        self.db.refresh(workflow)
        return workflow

    def get_by_id(self, workflow_id: int) -> Optional[Workflow]:
        return self.db.query(Workflow).filter(Workflow.id == workflow_id).first()

    def get_by_name(self, name: str) -> Optional[Workflow]:
        return self.db.query(Workflow).filter(Workflow.name == name).first()

    def get_all(self, agent_type: str = None) -> List[Workflow]:
        q = self.db.query(Workflow)
        if agent_type:
            q = q.filter(Workflow.agent_type == agent_type)
        return q.all()

    def update(self, workflow_id: int, workflow_data: dict) -> Optional[Workflow]:
        workflow = self.get_by_id(workflow_id)
        if workflow:
            for key, value in workflow_data.items():
                setattr(workflow, key, value)
            self.db.commit()
            self.db.refresh(workflow)
        return workflow

    def delete(self, workflow_id: int) -> bool:
        workflow = self.get_by_id(workflow_id)
        if workflow:
            self.db.delete(workflow)
            self.db.commit()
            return True
        return False

    def get_active_workflows(self, agent_type: str = None) -> List[Workflow]:
        q = self.db.query(Workflow).filter(Workflow.status == True)
        if agent_type:
            q = q.filter(Workflow.agent_type == agent_type)
        return q.all()

    def get_active_workflows_flows(self, agent_type: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve flows of all active workflows from the database.
            
        Returns:
            List[Dict[str, Any]]: List of flows from active workflows
        """
        try:
            # Query active workflows and extract only their flows
            query = self.db.query(Workflow.flow).filter(Workflow.status == True)

            if(agent_type):
                query = query.filter(Workflow.agent_type == agent_type)

            workflows = query.all()
                
            # Extract flows from the query results
            return [workflow[0] for workflow in workflows]
        except Exception as e:
            self.db.rollback()
            raise e 