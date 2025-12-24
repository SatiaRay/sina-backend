# repositories/__init__.py
from sqlalchemy.orm import Session
from .repository import WizardRepository, ChatRepository, ChatHistoryRepository, WorkflowRepository, InstructionRepository

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