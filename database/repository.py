from sqlalchemy.orm import Session
from typing import List, Optional, Type, TypeVar, Generic
from datetime import datetime
from .models import BaseModel, Chat, ChatHistory, Document, Wizard, CrawledDomain

T = TypeVar('T', bound=BaseModel)

class Repository(Generic[T]):
    def __init__(self, db: Session, model_class: Type[T]):
        self.db = db
        self.model_class = model_class

    def get_all(self) -> List[T]:
        return self.db.query(self.model_class).all()

    def get(self, id: int) -> Optional[T]:
        return self.db.query(self.model_class).filter(self.model_class.id == id).first()

    def create(self, data: dict) -> T:
        instance = self.model_class(**data)
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def update(self, id: int, data: dict) -> Optional[T]:
        instance = self.get(id)
        if instance:
            for key, value in data.items():
                setattr(instance, key, value)
            self.db.commit()
            self.db.refresh(instance)
        return instance

    def delete(self, id: int) -> bool:
        instance = self.get(id)
        if instance:
            self.db.delete(instance)
            self.db.commit()
            return True
        return False

class WizardRepository(Repository[Wizard]):
    def __init__(self, db: Session):
        super().__init__(db, Wizard)

    def get_all(self, enable_only: bool = False) -> List[Wizard]:
        query = self.db.query(Wizard)
        if enable_only:
            query = query.filter(Wizard.enabled == True)
        return query.all()

    def get(self, id: int, enable_only: bool = False) -> Optional[T]:
        query = self.db.query(self.model_class).filter(self.model_class.id == id)
        
        if enable_only:
            query = query.filter(self.model_class.enabled == True)
            
        wizard = query.first()

        if wizard:
            children_query = self.db.query(self.model_class).filter(self.model_class.parent_id == wizard.id)
            if enable_only:
                children_query = children_query.filter(self.model_class.enabled == True)
            wizard.children = children_query.all()
        
        return wizard

    def get_by_parent(self, parent_id: Optional[int], enable_only: bool = True) -> List[Wizard]:
        query = self.db.query(Wizard).filter(Wizard.parent_id == parent_id)
        if enable_only:
            query = query.filter(Wizard.enabled == True)
        return query.all()

    def get_with_children(self, id: int, enable_only: bool = True) -> Optional[Wizard]:
        query = self.db.query(Wizard).filter(Wizard.id == id)
        if enable_only:
            query = query.filter(Wizard.enabled == True)
        return query.first()

    def get_root_wizards(self, enable_only: bool = True) -> List[Wizard]:
        query = self.db.query(Wizard).filter(Wizard.parent_id.is_(None))
        if enable_only:
            query = query.filter(Wizard.enabled == True)
        return query.all()

    def get_wizard_hierarchy(self, id: int, enable_only: bool = True) -> List[Wizard]:
        """Get a wizard and all its descendants"""
        wizard = self.get_with_children(id, enable_only)
        if not wizard:
            return []
        
        result = [wizard]
        children = self.get_by_parent(id, enable_only)
        for child in children:
            result.extend(self.get_wizard_hierarchy(child.id, enable_only))
        return result

    def enable_wizard(self, id: int) -> Optional[Wizard]:
        return self.update(id, {"enabled": True})

    def disable_wizard(self, id: int) -> Optional[Wizard]:
        return self.update(id, {"enabled": False})

    def get_enabled_wizards(self) -> List[Wizard]:
        return self.db.query(Wizard).filter(Wizard.enabled == True).all()

    def get_disabled_wizards(self) -> List[Wizard]:
        return self.db.query(Wizard).filter(Wizard.enabled == False).all()

class ChatRepository(Repository[Chat]):
    def __init__(self, db: Session):
        super().__init__(db, Chat)

    def get_with_messages(self, id: int) -> Optional[Chat]:
        return self.db.query(Chat).filter(Chat.session_id == id).first()

    def get_all_with_messages(self) -> List[Chat]:
        return self.db.query(Chat).all()
    
class ChatHistoryRepository(Repository[ChatHistory]):
    def __init__(self, db: Session):
        super().__init__(db, ChatHistory)

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

class CrawledDomainRepository(Repository[CrawledDomain]):
    def __init__(self, db: Session):
        super().__init__(db, CrawledDomain)

    def get_by_domain(self, domain: str) -> Optional[CrawledDomain]:
        return self.db.query(CrawledDomain).filter(CrawledDomain.domain == domain).first()

    def get_or_create(self, domain: str) -> CrawledDomain:
        existing = self.get_by_domain(domain)
        if existing:
            return existing
        return self.create({"domain": domain})

class DocumentRepository(Repository[Document]):
    def __init__(self, db: Session):
        super().__init__(db, Document)

    def get_by_uri(self, uri: str) -> List[Document]:
        return self.db.query(Document).filter(Document.uri == uri).all()

    def get_by_domain(self, domain_id: int) -> List[Document]:
        return self.db.query(Document).filter(Document.domain_id == domain_id).all()

    def search_by_content(self, query: str) -> List[Document]:
        return self.db.query(Document).filter(Document.content.ilike(f"%{query}%")).all()

    def search_by_title(self, query: str) -> List[Document]:
        return self.db.query(Document).filter(Document.title.ilike(f"%{query}%")).all() 