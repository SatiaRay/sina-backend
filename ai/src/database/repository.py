# repositories/base.py
from json import dumps
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic, Tuple
from .models import BaseModel, Wizard, Chat, ChatHistory, Workflow, Instruction

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    """Base repository with workspace isolation"""
    
    def __init__(self, db: Session, model_class: Type[T]):
        self.db = db
        self.model_class = model_class
    
    def _apply_workspace_filter(self, query, workspace_id: Optional[str] = None):
        """Apply workspace filter to query"""
        if workspace_id:
            query = query.filter(self.model_class.workspace_id == workspace_id)
        return query
    
    def _validate_workspace(self, data: dict, workspace_id: Optional[str] = None):
        """Validate and add workspace_id to data"""
        if workspace_id:
            data['workspace_id'] = workspace_id
        elif 'workspace_id' not in data:
            raise ValueError("workspace_id is required for workspace isolation. Data: " + dumps(data))
        return data
    
    def get_all(self, workspace_id: Optional[str] = None) -> List[T]:
        """Get all records for a workspace"""
        query = self.db.query(self.model_class)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
    def get(self, id: int, workspace_id: Optional[str] = None) -> Optional[T]:
        """Get a record by ID within a workspace"""
        query = self.db.query(self.model_class).filter(self.model_class.id == id)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.first()
    
    def create(self, data: dict, workspace_id: Optional[str] = None) -> T:
        """Create a new record within a workspace"""
        data = self._validate_workspace(data, workspace_id)
        instance = self.model_class(**data)
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance
    
    def update(self, id: int, data: dict, workspace_id: Optional[str] = None) -> Optional[T]:
        """Update a record within a workspace"""
        instance = self.get(id, workspace_id)
        if instance:
            # Don't allow changing workspace_id through update
            if 'workspace_id' in data:
                del data['workspace_id']
            
            for key, value in data.items():
                setattr(instance, key, value)
            self.db.commit()
            self.db.refresh(instance)
        return instance
    
    def delete(self, id: int, workspace_id: Optional[str] = None) -> bool:
        """Delete a record within a workspace"""
        instance = self.get(id, workspace_id)
        if instance:
            self.db.delete(instance)
            self.db.commit()
            return True
        return False
    
    def count(self, workspace_id: Optional[str] = None) -> int:
        """Count records in a workspace"""
        query = self.db.query(self.model_class)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.count()
    
    def exists(self, id: int, workspace_id: Optional[str] = None) -> bool:
        """Check if a record exists in a workspace"""
        return self.get(id, workspace_id) is not None


class WizardRepository(BaseRepository[Wizard]):
    def __init__(self, db: Session):
        super().__init__(db, Wizard)
    
    def get(self, id: int, workspace_id: Optional[str] = None) -> Optional[Wizard]:
        """Get a wizard with its children"""
        query = self.db.query(Wizard).filter(Wizard.id == id)
        query = self._apply_workspace_filter(query, workspace_id)
        
        wizard = query.first()
        
        if wizard:
            # Load children within the same workspace
            children_query = self.db.query(Wizard).filter(
                Wizard.parent_id == wizard.id
            )
            children_query = self._apply_workspace_filter(children_query, workspace_id)
            wizard.children = children_query.all()
        
        return wizard
    
    def get_root_wizards(self, workspace_id: Optional[str] = None) -> List[Wizard]:
        """Get root wizards for a workspace"""
        query = self.db.query(Wizard).filter(Wizard.parent_id.is_(None))
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
 
    
class ChatRepository(BaseRepository[Chat]):
    def __init__(self, db: Session):
        super().__init__(db, Chat)
    
    def get_with_messages(self, id: int, 
                          workspace_id: Optional[str] = None) -> Optional[Chat]:
        """Get chat with its messages within a workspace"""
        query = self.db.query(Chat).filter(Chat.session_id == id)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.first()
    
    def get_all_with_messages(self, workspace_id: Optional[str] = None) -> List[Chat]:
        """Get all chats with messages for a workspace"""
        query = self.db.query(Chat)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
    def get_by_session_id(self, session_id: str, 
                          workspace_id: Optional[str] = None) -> Optional[Chat]:
        """Get chat by session ID within a workspace"""
        query = self.db.query(Chat).filter(Chat.session_id == session_id)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.first()
    
    def get_recent_chats(self, limit: int = 10,
                         workspace_id: Optional[str] = None) -> List[Chat]:
        """Get recent chats for a workspace"""
        query = self.db.query(Chat).order_by(Chat.created_at.desc())
        query = self._apply_workspace_filter(query, workspace_id)
        return query.limit(limit).all()
    
class ChatHistoryRepository(BaseRepository[ChatHistory]):
    def __init__(self, db: Session):
        super().__init__(db, ChatHistory)
    
    def get_chat_history_by_chat_id(self, chat_id: int, 
                                    workspace_id: Optional[str] = None,
                                    limit: int = 20) -> List[ChatHistory]:
        """Get chat history for a specific chat within a workspace"""
        # First verify the chat belongs to the workspace
        chat_query = self.db.query(Chat).filter(Chat.id == chat_id)
        chat_query = self._apply_workspace_filter(chat_query, workspace_id)
        chat = chat_query.first()
        
        if not chat:
            return []
        
        # Get chat history
        return (
            self.db.query(ChatHistory)
            .filter(ChatHistory.chat_id == chat_id)
            .limit(limit=limit)
            .all()
        )
    
    def get_with_chat_history(self, id: int, 
                              workspace_id: Optional[str] = None) -> Optional[Chat]:
        """Get a Chat and its associated ChatHistory within a workspace"""
        query = self.db.query(Chat).filter(Chat.id == id)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.join(Chat.chat_history).first()
    
    def get_recent_messages(self, limit: int = 50,
                            workspace_id: Optional[str] = None) -> List[ChatHistory]:
        """Get recent chat messages for a workspace"""
        query = self.db.query(ChatHistory).order_by(ChatHistory.created_at.desc())
        query = self._apply_workspace_filter(query, workspace_id)
        return query.limit(limit).all()
    
    def get_messages_by_role(self, role: str, 
                             workspace_id: Optional[str] = None) -> List[ChatHistory]:
        """Get messages by role within a workspace"""
        query = self.db.query(ChatHistory).filter(ChatHistory.role == role)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
class WorkflowRepository(BaseRepository[Workflow]):
    def __init__(self, db: Session):
        super().__init__(db, Workflow)
        
    def get_by_name(self, name: str, workspace_id: Optional[str] = None) -> Optional[Chat]:
        """Get workflow by name"""
        query = self.db.query(Workflow).filter(Workflow.name == name)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.first()
    
    def get_active_workflows(self, workspace_id: Optional[str] = None) -> List[Workflow]:
        """Get active workflows for a workspace"""
        query = self.db.query(Workflow).filter(Workflow.status == True)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
    def get_active_workflows_flows(self, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve flows of all active workflows from the database.
            
        Returns:
            List[Dict[str, Any]]: List of flows from active workflows
        """
        try:
            # Query active workflows and extract only their flows
            query = self.db.query(Workflow.flow).filter(Workflow.status == True)
            query = self._apply_workspace_filter(query, workspace_id)

            workflows = query.all()
                
            # Extract flows from the query results
            return [workflow[0] for workflow in workflows]
        except Exception as e:
            self.db.rollback()
            raise e 
    
class InstructionRepository(BaseRepository[Instruction]):
    def __init__(self, db: Session):
        super().__init__(db, Instruction)
    
    def get_all_paginated(self, page: int = 1, size: int = 10,
                          workspace_id: Optional[str] = None) -> Tuple[List[Instruction], int]:
        """Get paginated instructions for a workspace"""
        query = self.db.query(Instruction).filter(
            Instruction.label != "", Instruction.text != ""
        )
        query = self._apply_workspace_filter(query, workspace_id)
        
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total
    
    def get_active_instructions_paginated(self, page: int = 1, size: int = 10,
                                          workspace_id: Optional[str] = None) -> Tuple[List[Instruction], int]:
        """Get paginated active instructions for a workspace"""
        query = self.db.query(Instruction).filter(
            Instruction.status == True, Instruction.label != "", Instruction.text != ""
        )
        query = self._apply_workspace_filter(query, workspace_id)
        
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total
    
    def get_inactive_instructions_paginated(self, page: int = 1, size: int = 10,
                                            workspace_id: Optional[str] = None) -> Tuple[List[Instruction], int]:
        """Get paginated inactive instructions for a workspace"""
        query = self.db.query(Instruction).filter(
            Instruction.status == False, Instruction.label != "", Instruction.text != ""
        )
        query = self._apply_workspace_filter(query, workspace_id)
        
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total
    
    def get_all(self, workspace_id: Optional[str] = None) -> List[Instruction]:
        """Get all instructions for a workspace"""
        query = self.db.query(Instruction).filter(
            Instruction.label != "", Instruction.text != ""
        )
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
    def get_active_instructions(self, workspace_id: Optional[str] = None) -> List[Instruction]:
        """Get active instructions for a workspace"""
        query = self.db.query(Instruction).filter(
            Instruction.status == True,
            Instruction.label != "",
            Instruction.text != "",
        )
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
    def get_inactive_instructions(self, workspace_id: Optional[str] = None) -> List[Instruction]:
        """Get inactive instructions for a workspace"""
        query = self.db.query(Instruction).filter(
            Instruction.status == False,
            Instruction.label != "",
            Instruction.text != "",
        )
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
    def get_by_label(self, label: str, 
                     workspace_id: Optional[str] = None) -> Optional[Instruction]:
        """Get instruction by label within a workspace"""
        query = self.db.query(Instruction).filter(
            Instruction.label == label,
            Instruction.label != "",
            Instruction.text != "",
        )
        query = self._apply_workspace_filter(query, workspace_id)
        return query.first()
    
    def enable_instruction(self, id: int, 
                           workspace_id: Optional[str] = None) -> Optional[Instruction]:
        """Enable an instruction within a workspace"""
        return self.update(id, {"status": True}, workspace_id)
    
    def disable_instruction(self, id: int, 
                            workspace_id: Optional[str] = None) -> Optional[Instruction]:
        """Disable an instruction within a workspace"""
        return self.update(id, {"status": False}, workspace_id)
    
    def search_by_text(self, search_term: str, 
                       workspace_id: Optional[str] = None) -> List[Instruction]:
        """Search instructions by text content within a workspace"""
        query = self.db.query(Instruction).filter(
            Instruction.text.ilike(f"%{search_term}%"),
            Instruction.label != "",
            Instruction.text != "",
        )
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
class RepositoryFactory:
    """Factory for creating repository instances"""
    
    def __init__(self, db: Session):
        self.db = db
    
    @property
    def wizards(self) -> WizardRepository:
        return WizardRepository(self.db)
    
    @property
    def chats(self) -> ChatRepository:
        return ChatRepository(self.db)
    
    @property
    def chat_history(self) -> ChatHistoryRepository:
        return ChatHistoryRepository(self.db)
    
    @property
    def workflows(self) -> WorkflowRepository:
        return WorkflowRepository(self.db)
    
    @property
    def instructions(self) -> InstructionRepository:
        return InstructionRepository(self.db)


# Convenience function for FastAPI dependency
def get_repository_factory(db: Session) -> RepositoryFactory:
    return RepositoryFactory(db)