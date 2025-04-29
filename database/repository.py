from sqlalchemy.orm import Session
from typing import List, Optional, Type, TypeVar, Generic
from datetime import datetime
from .models import BaseModel, Chat, Message, Document, Wizard

T = TypeVar('T', bound=BaseModel)

class BaseRepository(Generic[T]):
    def __init__(self, model_class: Type[T], db: Session):
        self.model_class = model_class
        self.db = db

    def get(self, id: int) -> Optional[T]:
        return self.db.query(self.model_class).filter(self.model_class.id == id).first()

    def get_all(self) -> List[T]:
        return self.db.query(self.model_class).all()

    def create(self, obj_in: dict) -> T:
        db_obj = self.model_class(**obj_in)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
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
        return self.db.query(Chat).filter(Chat.id == id).first()

    def get_all_with_messages(self) -> List[Chat]:
        return self.db.query(Chat).all()

class MessageRepository(BaseRepository[Message]):
    def __init__(self, db: Session):
        super().__init__(Message, db)

    def get_by_chat(self, chat_id: int) -> List[Message]:
        return self.db.query(Message).filter(Message.chat_id == chat_id).all()

class DocumentRepository(BaseRepository[Document]):
    def __init__(self, db: Session):
        super().__init__(Document, db)

    def get_by_source(self, source: str) -> List[Document]:
        return self.db.query(Document).filter(Document.source == source).all()

    def get_by_embedding_id(self, embedding_id: str) -> Optional[Document]:
        return self.db.query(Document).filter(Document.embedding_id == embedding_id).first() 