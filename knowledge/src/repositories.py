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

class DocumentRepository(Generic[T]):
    def __init__(self):
        self.model_class = Document
        self.db = next(get_db())

    def get_all(self, without_vector: bool = False):
        documents = self.db.query(self.model_class).all()
        if without_vector or not len(documents):
            return documents

        # Collect all vector IDs
        vector_ids = [doc.vector_id for doc in documents if doc.vector_id]

        # Batch fetch from vector DB (implement a batch get)
        vector_data = vector.get_all_documents(vector_ids)

        # Merge by vector_id (map join)
        vector_map = {v["id"]: v for v in vector_data}

        for doc in documents:
            if doc.vector_id in vector_map:
                doc.vector_data = vector_map[doc.vector_id]

        return documents

    def get(self, id: int, without_vector: bool = False):
        doc = self.db.query(self.model_class).filter(self.model_class.id == id).first()
        if doc and not without_vector and doc.vector_id:
            vector_doc = vector.get_document_by_id(doc.vector_id)
            doc.vector_data = vector_doc
        return doc

    def create(self, data: dict) -> T:
        vector_id = vector.add_documents([data])[0]
        instance = self.model_class(**{"vector_id" : vector_id})
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def update(self, id: int, data: dict) -> Optional[T]:
        instance = self.get(id)
        vector.update_document(instance.vector_id, data)
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