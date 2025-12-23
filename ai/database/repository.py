# repositories/base.py
from sqlalchemy import desc
from sqlalchemy.orm import Session
from typing import List, Optional, Type, TypeVar, Generic, Union, Tuple
from datetime import datetime
import uuid
from .models import BaseModel, Wizard, Chat, ChatHistory, Workflow, Instruction, FunctionCallLog

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    """Base repository with workspace isolation"""
    
    def __init__(self, db: Session, model_class: Type[T]):
        self.db = db
        self.model_class = model_class
    
    def _apply_workspace_filter(self, query, workspace_id: Optional[Union[str, uuid.UUID]] = None):
        """Apply workspace filter to query"""
        if workspace_id:
            # Convert string UUID to UUID object if needed
            if isinstance(workspace_id, str):
                workspace_id = uuid.UUID(workspace_id)
            query = query.filter(self.model_class.workspace_id == workspace_id)
        return query
    
    def _validate_workspace(self, data: dict, workspace_id: Optional[Union[str, uuid.UUID]] = None):
        """Validate and add workspace_id to data"""
        if workspace_id:
            if isinstance(workspace_id, str):
                workspace_id = uuid.UUID(workspace_id)
            data['workspace_id'] = workspace_id
        elif 'workspace_id' not in data:
            raise ValueError("workspace_id is required for workspace isolation")
        return data
    
    def get_all(self, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[T]:
        """Get all records for a workspace"""
        query = self.db.query(self.model_class)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
    def get(self, id: int, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> Optional[T]:
        """Get a record by ID within a workspace"""
        query = self.db.query(self.model_class).filter(self.model_class.id == id)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.first()
    
    def create(self, data: dict, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> T:
        """Create a new record within a workspace"""
        data = self._validate_workspace(data, workspace_id)
        instance = self.model_class(**data)
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance
    
    def update(self, id: int, data: dict, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> Optional[T]:
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
    
    def delete(self, id: int, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> bool:
        """Delete a record within a workspace"""
        instance = self.get(id, workspace_id)
        if instance:
            self.db.delete(instance)
            self.db.commit()
            return True
        return False
    
    def count(self, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> int:
        """Count records in a workspace"""
        query = self.db.query(self.model_class)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.count()
    
    def exists(self, id: int, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> bool:
        """Check if a record exists in a workspace"""
        return self.get(id, workspace_id) is not None


class WizardRepository(BaseRepository[Wizard]):
    def __init__(self, db: Session):
        super().__init__(db, Wizard)
    
    def get_all(self, workspace_id: Optional[Union[str, uuid.UUID]] = None, 
                enable_only: bool = False) -> List[Wizard]:
        """Get all wizards for a workspace"""
        query = self.db.query(Wizard)
        query = self._apply_workspace_filter(query, workspace_id)
        
        if enable_only:
            query = query.filter(Wizard.enabled == True)
        
        return query.all()
    
    def get_heads(self, workspace_id: Optional[Union[str, uuid.UUID]] = None, 
                  enable_only: bool = False) -> List[Wizard]:
        """Get all head wizards (no parent) for a workspace"""
        query = self.db.query(Wizard).filter(Wizard.parent_id.is_(None))
        query = self._apply_workspace_filter(query, workspace_id)
        
        if enable_only:
            query = query.filter(Wizard.enabled == True)
        
        return query.all()
    
    def get(self, id: int, workspace_id: Optional[Union[str, uuid.UUID]] = None, 
            enable_only: bool = False) -> Optional[Wizard]:
        """Get a wizard with its children"""
        query = self.db.query(Wizard).filter(Wizard.id == id)
        query = self._apply_workspace_filter(query, workspace_id)
        
        if enable_only:
            query = query.filter(Wizard.enabled == True)
        
        wizard = query.first()
        
        if wizard:
            # Load children within the same workspace
            children_query = self.db.query(Wizard).filter(
                Wizard.parent_id == wizard.id
            )
            children_query = self._apply_workspace_filter(children_query, workspace_id)
            
            if enable_only:
                children_query = children_query.filter(Wizard.enabled == True)
            
            wizard.children = children_query.all()
        
        return wizard
    
    def get_by_parent(self, parent_id: Optional[int], 
                      workspace_id: Optional[Union[str, uuid.UUID]] = None,
                      enable_only: bool = True) -> List[Wizard]:
        """Get child wizards by parent ID within a workspace"""
        query = self.db.query(Wizard).filter(Wizard.parent_id == parent_id)
        query = self._apply_workspace_filter(query, workspace_id)
        
        if enable_only:
            query = query.filter(Wizard.enabled == True)
        
        return query.all()
    
    def get_with_children(self, id: int, 
                          workspace_id: Optional[Union[str, uuid.UUID]] = None,
                          enable_only: bool = True) -> Optional[Wizard]:
        """Get wizard with eager-loaded children"""
        query = self.db.query(Wizard).filter(Wizard.id == id)
        query = self._apply_workspace_filter(query, workspace_id)
        
        if enable_only:
            query = query.filter(Wizard.enabled == True)
        
        return query.first()
    
    def get_root_wizards(self, workspace_id: Optional[Union[str, uuid.UUID]] = None,
                         enable_only: bool = True) -> List[Wizard]:
        """Get root wizards for a workspace"""
        query = self.db.query(Wizard).filter(Wizard.parent_id.is_(None))
        query = self._apply_workspace_filter(query, workspace_id)
        
        if enable_only:
            query = query.filter(Wizard.enabled == True)
        
        return query.all()
    
    def get_wizard_hierarchy(self, id: int, 
                             workspace_id: Optional[Union[str, uuid.UUID]] = None,
                             enable_only: bool = True) -> List[Wizard]:
        """Get a wizard and all its descendants within a workspace"""
        wizard = self.get_with_children(id, workspace_id, enable_only)
        if not wizard:
            return []
        
        result = [wizard]
        children = self.get_by_parent(id, workspace_id, enable_only)
        for child in children:
            result.extend(self.get_wizard_hierarchy(child.id, workspace_id, enable_only))
        
        return result
    
    def enable_wizard(self, id: int, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> Optional[Wizard]:
        """Enable a wizard within a workspace"""
        return self.update(id, {"enabled": True}, workspace_id)
    
    def disable_wizard(self, id: int, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> Optional[Wizard]:
        """Disable a wizard within a workspace"""
        return self.update(id, {"enabled": False}, workspace_id)
    
    def get_enabled_wizards(self, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[Wizard]:
        """Get all enabled wizards for a workspace"""
        query = self.db.query(Wizard).filter(Wizard.enabled == True)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
    def get_disabled_wizards(self, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[Wizard]:
        """Get all disabled wizards for a workspace"""
        query = self.db.query(Wizard).filter(Wizard.enabled == False)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
    def get_by_name(self, name: str, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> Optional[Wizard]:
        """Get wizard by name within a workspace"""
        query = self.db.query(Wizard).filter(Wizard.name == name)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.first()

class ChatRepository(BaseRepository[Chat]):
    def __init__(self, db: Session):
        super().__init__(db, Chat)
    
    def get_with_messages(self, id: int, 
                          workspace_id: Optional[Union[str, uuid.UUID]] = None) -> Optional[Chat]:
        """Get chat with its messages within a workspace"""
        query = self.db.query(Chat).filter(Chat.session_id == id)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.first()
    
    def get_all_with_messages(self, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[Chat]:
        """Get all chats with messages for a workspace"""
        query = self.db.query(Chat)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
    def get_by_session_id(self, session_id: str, 
                          workspace_id: Optional[Union[str, uuid.UUID]] = None) -> Optional[Chat]:
        """Get chat by session ID within a workspace"""
        query = self.db.query(Chat).filter(Chat.session_id == session_id)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.first()
    
    def get_recent_chats(self, limit: int = 10,
                         workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[Chat]:
        """Get recent chats for a workspace"""
        query = self.db.query(Chat).order_by(Chat.created_at.desc())
        query = self._apply_workspace_filter(query, workspace_id)
        return query.limit(limit).all()
    
class ChatHistoryRepository(BaseRepository[ChatHistory]):
    def __init__(self, db: Session):
        super().__init__(db, ChatHistory)
    
    def get_chat_history_by_chat_id(self, chat_id: int, 
                                    workspace_id: Optional[Union[str, uuid.UUID]] = None,
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
                              workspace_id: Optional[Union[str, uuid.UUID]] = None) -> Optional[Chat]:
        """Get a Chat and its associated ChatHistory within a workspace"""
        query = self.db.query(Chat).filter(Chat.id == id)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.join(Chat.chat_history).first()
    
    def get_recent_messages(self, limit: int = 50,
                            workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[ChatHistory]:
        """Get recent chat messages for a workspace"""
        query = self.db.query(ChatHistory).order_by(ChatHistory.created_at.desc())
        query = self._apply_workspace_filter(query, workspace_id)
        return query.limit(limit).all()
    
    def get_messages_by_role(self, role: str, 
                             workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[ChatHistory]:
        """Get messages by role within a workspace"""
        query = self.db.query(ChatHistory).filter(ChatHistory.role == role)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
class WorkflowRepository(BaseRepository[Workflow]):
    def __init__(self, db: Session):
        super().__init__(db, Workflow)
    
    def get_all(self, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[Workflow]:
        """Get all workflows for a workspace"""
        query = self.db.query(Workflow)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
    def get_active_workflows(self, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[Workflow]:
        """Get active workflows for a workspace"""
        query = self.db.query(Workflow).filter(Workflow.status == True)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
    def get_by_name(self, name: str, 
                    workspace_id: Optional[Union[str, uuid.UUID]] = None) -> Optional[Workflow]:
        """Get workflow by name within a workspace"""
        query = self.db.query(Workflow).filter(Workflow.name == name)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.first()
    
    def activate_workflow(self, id: int, 
                          workspace_id: Optional[Union[str, uuid.UUID]] = None) -> Optional[Workflow]:
        """Activate a workflow within a workspace"""
        return self.update(id, {"status": True}, workspace_id)
    
    def deactivate_workflow(self, id: int, 
                            workspace_id: Optional[Union[str, uuid.UUID]] = None) -> Optional[Workflow]:
        """Deactivate a workflow within a workspace"""
        return self.update(id, {"status": False}, workspace_id)
    
    def get_by_status(self, status: bool, 
                      workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[Workflow]:
        """Get workflows by status within a workspace"""
        query = self.db.query(Workflow).filter(Workflow.status == status)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
class InstructionRepository(BaseRepository[Instruction]):
    def __init__(self, db: Session):
        super().__init__(db, Instruction)
    
    def get_all_paginated(self, page: int = 1, size: int = 10,
                          workspace_id: Optional[Union[str, uuid.UUID]] = None) -> Tuple[List[Instruction], int]:
        """Get paginated instructions for a workspace"""
        query = self.db.query(Instruction).filter(
            Instruction.label != "", Instruction.text != ""
        )
        query = self._apply_workspace_filter(query, workspace_id)
        
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total
    
    def get_active_instructions_paginated(self, page: int = 1, size: int = 10,
                                          workspace_id: Optional[Union[str, uuid.UUID]] = None) -> Tuple[List[Instruction], int]:
        """Get paginated active instructions for a workspace"""
        query = self.db.query(Instruction).filter(
            Instruction.status == True, Instruction.label != "", Instruction.text != ""
        )
        query = self._apply_workspace_filter(query, workspace_id)
        
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total
    
    def get_inactive_instructions_paginated(self, page: int = 1, size: int = 10,
                                            workspace_id: Optional[Union[str, uuid.UUID]] = None) -> Tuple[List[Instruction], int]:
        """Get paginated inactive instructions for a workspace"""
        query = self.db.query(Instruction).filter(
            Instruction.status == False, Instruction.label != "", Instruction.text != ""
        )
        query = self._apply_workspace_filter(query, workspace_id)
        
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total
    
    def get_all(self, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[Instruction]:
        """Get all instructions for a workspace"""
        query = self.db.query(Instruction).filter(
            Instruction.label != "", Instruction.text != ""
        )
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
    def get_active_instructions(self, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[Instruction]:
        """Get active instructions for a workspace"""
        query = self.db.query(Instruction).filter(
            Instruction.status == True,
            Instruction.label != "",
            Instruction.text != "",
        )
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
    def get_inactive_instructions(self, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[Instruction]:
        """Get inactive instructions for a workspace"""
        query = self.db.query(Instruction).filter(
            Instruction.status == False,
            Instruction.label != "",
            Instruction.text != "",
        )
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
    def get_by_label(self, label: str, 
                     workspace_id: Optional[Union[str, uuid.UUID]] = None) -> Optional[Instruction]:
        """Get instruction by label within a workspace"""
        query = self.db.query(Instruction).filter(
            Instruction.label == label,
            Instruction.label != "",
            Instruction.text != "",
        )
        query = self._apply_workspace_filter(query, workspace_id)
        return query.first()
    
    def enable_instruction(self, id: int, 
                           workspace_id: Optional[Union[str, uuid.UUID]] = None) -> Optional[Instruction]:
        """Enable an instruction within a workspace"""
        return self.update(id, {"status": True}, workspace_id)
    
    def disable_instruction(self, id: int, 
                            workspace_id: Optional[Union[str, uuid.UUID]] = None) -> Optional[Instruction]:
        """Disable an instruction within a workspace"""
        return self.update(id, {"status": False}, workspace_id)
    
    def search_by_text(self, search_term: str, 
                       workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[Instruction]:
        """Search instructions by text content within a workspace"""
        query = self.db.query(Instruction).filter(
            Instruction.text.ilike(f"%{search_term}%"),
            Instruction.label != "",
            Instruction.text != "",
        )
        query = self._apply_workspace_filter(query, workspace_id)
        return query.all()
    
class FunctionCallLogRepository(BaseRepository[FunctionCallLog]):
    def __init__(self, db: Session):
        super().__init__(db, FunctionCallLog)
    
    def get_recent_logs(self, limit: int = 100,
                        workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[FunctionCallLog]:
        """Get recent function call logs for a workspace"""
        query = self.db.query(FunctionCallLog).order_by(desc(FunctionCallLog.created_at))
        query = self._apply_workspace_filter(query, workspace_id)
        return query.limit(limit).all()
    
    def get_by_function_name(self, function_name: str,
                             workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[FunctionCallLog]:
        """Get logs by function name within a workspace"""
        query = self.db.query(FunctionCallLog).filter(
            FunctionCallLog.function_name == function_name
        )
        query = self._apply_workspace_filter(query, workspace_id)
        return query.order_by(desc(FunctionCallLog.created_at)).all()
    
    def get_by_status(self, status: str,
                      workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[FunctionCallLog]:
        """Get logs by status within a workspace"""
        query = self.db.query(FunctionCallLog).filter(FunctionCallLog.status == status)
        query = self._apply_workspace_filter(query, workspace_id)
        return query.order_by(desc(FunctionCallLog.created_at)).all()
    
    def get_failed_calls(self, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[FunctionCallLog]:
        """Get failed function calls for a workspace"""
        return self.get_by_status("failed", workspace_id)
    
    def get_successful_calls(self, workspace_id: Optional[Union[str, uuid.UUID]] = None) -> List[FunctionCallLog]:
        """Get successful function calls for a workspace"""
        return self.get_by_status("success", workspace_id)