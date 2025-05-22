from sqlalchemy.orm import Session
from typing import List, Optional, Type, TypeVar, Generic
from datetime import datetime
from .models import BaseModel, Chat, ChatHistory, Document, Wizard, CrawledDomain

T = TypeVar('T', bound=BaseModel)

class BaseRepository(Generic[T]):
    def __init__(self, model_class: Type[T], db: Session):
        self.model_class = model_class
        self.db = db

    def get(self, id: int) -> Optional[T]:
        return self.db.query(self.model_class).filter(self.model_class.id == id).first()

    def get_all(self) -> List[T]:
        return self.db.query(self.model_class).all()

    def create(self, data: dict):
        db_obj = self.model_class(**data)
        self.db.add(db_obj)
        self.db.commit()
        return db_obj

    def update(self, id: int, obj_in: dict) -> Optional[T]:
        db_obj = self.get(id)
        if db_obj:
            for key, value in obj_in.items():
                setattr(db_obj, key, value)
            self.db.commit()
            self.db.refresh(db_obj)
        return db_obj

    def delete(self, id: int) -> bool:
        db_obj = self.get(id)
        if db_obj:
            self.db.delete(db_obj)
            self.db.commit()
            return True
        return False

class WizardRepository(BaseRepository[Wizard]):
    def __init__(self, db: Session):
        super().__init__(Wizard, db)

    def get_by_parent(self, parent_id: Optional[int], enabled_only: bool = True) -> List[Wizard]:
        query = self.db.query(Wizard).filter(Wizard.parent_id == parent_id)
        if enabled_only:
            query = query.filter(Wizard.enabled == True)
        return query.all()

    def get_with_children(self, id: int, enabled_only: bool = True) -> Optional[Wizard]:
        query = self.db.query(Wizard).filter(Wizard.id == id)
        if enabled_only:
            query = query.filter(Wizard.enabled == True)
        return query.first()

    def get_root_wizards(self, enabled_only: bool = True) -> List[Wizard]:
        query = self.db.query(Wizard).filter(Wizard.parent_id.is_(None))
        if enabled_only:
            query = query.filter(Wizard.enabled == True)
        return query.all()

    def get_wizard_hierarchy(self, id: int, enabled_only: bool = True) -> List[Wizard]:
        """Get a wizard and all its descendants"""
        wizard = self.get_with_children(id, enabled_only)
        if not wizard:
            return []
        
        result = [wizard]
        children = self.get_by_parent(id, enabled_only)
        for child in children:
            result.extend(self.get_wizard_hierarchy(child.id, enabled_only))
        return result

    def enable_wizard(self, id: int) -> Optional[Wizard]:
        return self.update(id, {"enabled": True})

    def disable_wizard(self, id: int) -> Optional[Wizard]:
        return self.update(id, {"enabled": False})

    def get_enabled_wizards(self) -> List[Wizard]:
        return self.db.query(Wizard).filter(Wizard.enabled == True).all()

    def get_disabled_wizards(self) -> List[Wizard]:
        return self.db.query(Wizard).filter(Wizard.enabled == False).all()

class ChatRepository(BaseRepository[Chat]):
    def __init__(self, db: Session):
        super().__init__(Chat, db)

    def get_with_messages(self, id: int) -> Optional[Chat]:
        return self.db.query(Chat).filter(Chat.session_id == id).first()

    def get_all_with_messages(self) -> List[Chat]:
        return self.db.query(Chat).all()
    
class ChatHistoryRepository(BaseRepository[ChatHistory]):
    def __init__(self, db: Session):
        super().__init__(ChatHistory, db)

    def get_chat_history_by_chat_id(self, chat_id: int, limit:int = 20) -> List[ChatHistory]:
        """
        Retrieves all chat history messages associated with a specific chat.
        """
        return self.db.query(ChatHistory).filter(ChatHistory.chat_id == chat_id).limit(limit=limit).all()

    def get_with_chat_history(self, id: int) -> Optional[Chat]:
        """
        Retrieves a Chat and its associated ChatHistory messages.
        """
        return self.db.query(Chat).filter(Chat.id == id).join(Chat.chat_history).first()

class CrawledDomainRepository(BaseRepository[CrawledDomain]):
    def __init__(self, db: Session):
        super().__init__(CrawledDomain, db)

    def get_by_domain(self, domain: str) -> Optional[CrawledDomain]:
        return self.db.query(CrawledDomain).filter(CrawledDomain.domain == domain).first()

    def get_or_create(self, domain: str) -> CrawledDomain:
        existing = self.get_by_domain(domain)
        if existing:
            return existing
        return self.create({"domain": domain})

class DocumentRepository(BaseRepository[Document]):
    def __init__(self, db: Session):
        super().__init__(Document, db)

    def get_by_uri(self, uri: str) -> List[Document]:
        return self.db.query(Document).filter(Document.uri == uri).all()

    def get_by_domain(self, domain_id: int) -> List[Document]:
        return self.db.query(Document).filter(Document.domain_id == domain_id).all()

    def search_by_content(self, query: str) -> List[Document]:
        return self.db.query(Document).filter(Document.content.ilike(f"%{query}%")).all()

    def search_by_title(self, query: str) -> List[Document]:
        return self.db.query(Document).filter(Document.title.ilike(f"%{query}%")).all() 