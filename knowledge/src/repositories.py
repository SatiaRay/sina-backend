from sqlalchemy.orm import Session
from typing import List, Optional, Type, TypeVar, Generic

from src import database
from src.database import get_db
from .models import (
    BaseModel,
    Document
)
from .vector import VectorStore

vector = VectorStore()

T = TypeVar("T", bound=BaseModel)

class Repository(Generic[T]):
    def __init__(self, model_class: Type[T]):
        self.model_class = model_class
        self.db = next(get_db())

    def get_all(self) -> List[T]:
        return self.db.query(self.model_class).all()

    def get(self, id: int) -> Optional[T]:
        return self.db.query(self.model_class).filter(self.model_class.id == id).first()

    def create(self, data: dict) -> T:
        vector_id = vector.add_documents([data])[0]
        instance = self.model_class(**{"vector_id" : vector_id})
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
            vector.delete_documents([instance.vector_id])
            self.db.delete(instance)
            self.db.commit()
            return True

        raise Exception(f"Delete document failed: Document with id {id} not found !")

class DocumentRepository(Repository[Document]):
    def __init__(self):
        super().__init__(Document)