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

    def _merge_vector_data(self, doc, vector_doc):
        """
        Merge vector data (from ChromaDB) into SQL document object.
        - Flattens the structure.
        - Preserves all SQL fields.
        - Injects text and metadata keys at top level.
        """
        if not vector_doc:
            return doc

        # Merge text
        doc.text = vector_doc.get("text")

        # Merge metadata fields
        metadata = vector_doc.get("metadata", {})
        for key, value in metadata.items():
            setattr(doc, key, value)

        return doc

    def _to_vector_data(self, data: dict) -> dict:
        """
        Convert input data dict to {'text': ..., 'metadata': {...}} format for the vector store.
        'text' is a top-level field, all others are placed under 'metadata'.
        """
        vector_data = {'text': data.get('text')}
        # Place all other fields except 'text' into metadata
        vector_data['metadata'] = {k: v for k, v in data.items() if k != 'text'}
        return vector_data


    def get_all(self, db, without_vector: bool = False, offset: int = 0, limit: int = 100):
        # Use offset and limit for pagination
        documents = db.query(self.model_class).offset(offset).limit(limit).all()
        if without_vector or not documents:
            return documents
        # Collect all vector IDs
        vector_ids = [doc.vector_id for doc in documents if doc.vector_id]
        if not vector_ids:
            return documents
        # Batch fetch from ChromaDB
        vector_data = vector.get_all_documents(vector_ids)
        # Create lookup map
        vector_map = {v["id"]: v for v in vector_data}
        # Merge data into each document
        for doc in documents:
            vector_doc = vector_map.get(doc.vector_id)
            self._merge_vector_data(doc, vector_doc)
        return documents


    def get(self, db, id: int, without_vector: bool = False):
        doc = db.query(self.model_class).filter(self.model_class.id == id).first()
        if not doc or without_vector or not doc.vector_id:
            return doc

        vector_doc = vector.get_document_by_id(doc.vector_id)
        return self._merge_vector_data(doc, vector_doc)

    def create(self, db, data: dict) -> T:
        vector_id = vector.add_documents([self._to_vector_data(data)])[0]
        instance = self.model_class(**{"vector_id" : vector_id})
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance

    def update(self, db, id: int, data: dict) -> Optional[T]:
        instance = self.get(db, id)
        vector.update_document(instance.vector_id, self._to_vector_data(data))
        if instance:
            for key, value in data.items():
                setattr(instance, key, value)
            db.commit()
            db.refresh(instance)
        return instance

    def delete(self, db, id: int) -> bool:
        instance = self.get(db, id)

        if instance:
            vector.delete_documents([instance.vector_id])
            db.delete(instance)
            db.commit()
            return True

        raise Exception(f"Delete document failed: Document with id {id} not found !")

    def count(self, db):
        return db.query(self.model_class).count()