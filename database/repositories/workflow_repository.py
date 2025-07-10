from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from database.models import Workflow
from database.repositories.tenancy_repository import TenancyRepository

class WorkflowRepository(TenancyRepository):
    def __init__(self, db: Session):
        super().__init__(db, Workflow)

    def get_by_id(self, workflow_id: int) -> Optional[Workflow]:
        return self.db.query(Workflow).filter(Workflow.id == workflow_id).first()

    def get_by_name(self, name: str) -> Optional[Workflow]:
        return self.db.query(Workflow).filter(Workflow.name == name).first()

    def get_all(self) -> List[Workflow]:
        return self.db.query(Workflow).all()

    def get_active_workflows(self) -> List[Workflow]:
        return self.db.query(Workflow).filter(Workflow.status == True).all()

    def get_active_workflows_flows(self) -> List[Dict[str, Any]]:
        """
        Retrieve flows of all active workflows from the database.
            
        Returns:
            List[Dict[str, Any]]: List of flows from active workflows
        """
        try:
            # Query active workflows as objects, not just the flow column
            workflows = self.db.query(Workflow).filter(Workflow.status == True).all()
            # Extract flows from the query results
            return [workflow.flow for workflow in workflows]
        except Exception as e:
            self.db.rollback()
            raise e 