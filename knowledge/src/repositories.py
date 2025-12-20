# src/repositories/__init__.py (or document_repository.py)
from sqlalchemy.orm import Session
from typing import List, Optional
from fastapi import Request
from .models import Document
from .vector import VectorStore

vector = VectorStore()

class DocumentRepository:
    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
        self.model_class = Document
    
    def _apply_tenant_filter(self, query):
        """Apply workspace filter to query"""
        if hasattr(self.model_class, 'workspace_id'):
            return query.filter(self.model_class.workspace_id == self.workspace_id)
        return query
    
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
        Convert input data dict to vector store format.
        Ensure workspace_id is included in metadata.
        """
        # Extract text separately
        text = data.get('text', '')
        
        # All other fields go to metadata
        metadata = {k: v for k, v in data.items() if k != 'text'}
        
        # Ensure workspace_id is in metadata (use from data or repo)
        if 'workspace_id' not in metadata:
            metadata['workspace_id'] = self.workspace_id
            
        return {
            'text': text,
            'metadata': metadata
        }

    def get_all(self, db: Session, without_vector: bool = False, 
                offset: int = 0, limit: int = 100) -> List[Document]:
        """Get all documents for current workspace"""
        # Apply tenant filter
        query = self._apply_tenant_filter(db.query(self.model_class))
        documents = query.offset(offset).limit(limit).all()
        
        if without_vector or not documents:
            return documents
        
        # Get vector data
        vector_ids = [doc.vector_id for doc in documents if doc.vector_id]
        if not vector_ids:
            return documents
        
        # Get vector documents
        vector_data = vector.get_all_documents(vector_ids)
        
        # Filter by workspace_id and merge
        for doc in documents:
            # Find corresponding vector document
            vector_doc = None
            for vd in vector_data:
                if vd.get("id") == doc.vector_id:
                    metadata = vd.get("metadata", {})
                    # Check workspace_id
                    workspace_id_from_meta = metadata.get('workspace_id') if isinstance(metadata, dict) else None
                    if workspace_id_from_meta == self.workspace_id:
                        vector_doc = vd
                    break
            
            if vector_doc:
                self._merge_vector_data(doc, vector_doc)
        
        return documents

    def get(self, db: Session, id: int, without_vector: bool = False) -> Optional[Document]:
        """Get specific document from current workspace"""
        # Apply tenant filter (both id and workspace)
        query = db.query(self.model_class)
        query = query.filter(self.model_class.id == id)
        query = self._apply_tenant_filter(query)
        
        doc = query.first()
        
        if not doc or without_vector or not doc.vector_id:
            return doc

        # Get vector document
        vector_doc = vector.get_document_by_id(doc.vector_id)
        
        # Verify workspace access
        if vector_doc:
            metadata = vector_doc.get("metadata", {})
            workspace_id_from_meta = metadata.get("workspace_id") if isinstance(metadata, dict) else None
            if workspace_id_from_meta != self.workspace_id:
                raise Exception(f"Workspace mismatch: document belongs to workspace {workspace_id_from_meta}, not {self.workspace_id}")
            
            # Merge data
            self._merge_vector_data(doc, vector_doc)
        
        return doc

    def create(self, db: Session, data: dict) -> Document:
        """Create document in current workspace"""
        # Prepare vector data with workspace_id
        vector_data = self._to_vector_data(data)
        
        # Store in vector database
        vector_id = vector.add_document(vector_data)
        
        # Store in SQL database
        instance = self.model_class(
            vector_id=vector_id,
            workspace_id=self.workspace_id
        )
        
        # Add other fields from data that exist in Document model
        for key, value in data.items():
            if hasattr(instance, key) and key not in ['id', 'created_at', 'updated_at', 'vector_id', 'workspace_id']:
                setattr(instance, key, value)
        
        db.add(instance)
        db.commit()
        db.refresh(instance)
        
        # Get vector data to merge text
        vector_doc = vector.get_document_by_id(vector_id)
        if vector_doc and vector_doc.get("text"):
            instance.text = vector_doc["text"]
        
        return instance

    def update(self, db: Session, id: int, data: dict) -> Optional[Document]:
        """Update document in current workspace"""
        # Get document with tenant filter
        query = db.query(self.model_class).filter(self.model_class.id == id)
        query = self._apply_tenant_filter(query)
        instance = query.first()
        
        if not instance:
            return None
        
        # Prepare vector data with workspace_id
        vector_data = self._to_vector_data(data)
        
        # Update vector store
        vector.update_document(instance.vector_id, vector_data)
        
        # Update SQL fields
        for key, value in data.items():
            if hasattr(instance, key) and key not in ['id', 'created_at', 'updated_at', 'vector_id', 'workspace_id']:
                setattr(instance, key, value)
        
        db.commit()
        db.refresh(instance)
        
        # Get updated vector data for text
        vector_doc = vector.get_document_by_id(instance.vector_id)
        if vector_doc and vector_doc.get("text"):
            instance.text = vector_doc["text"]
        
        return instance

    def delete(self, db: Session, id: int) -> bool:
        """Delete document from current workspace"""
        # Get document with tenant filter
        query = db.query(self.model_class).filter(self.model_class.id == id)
        query = self._apply_tenant_filter(query)
        instance = query.first()
        
        if not instance:
            raise Exception(f"Document with id {id} not found in workspace {self.workspace_id}")
        
        # Delete from vector store
        try:
            vector.delete_documents([instance.vector_id])
        except Exception as e:
            print(f"Warning: Failed to delete from vector store: {e}")
        
        # Delete from SQL
        db.delete(instance)
        db.commit()
        return True

    def count(self, db: Session) -> int:
        """Count documents in current workspace"""
        query = self._apply_tenant_filter(db.query(self.model_class))
        return query.count()


# Repository factory
def get_document_repository(request: Request):
    """Factory function to create repository with workspace_id from request"""
    workspace_id = None
    if hasattr(request.state, 'tenant_context'):
        workspace_id = request.state.tenant_context.get('workspace_id')
    
    if not workspace_id:
        # Fallback for testing or legacy code
        workspace_id = "default-workspace"
    
    return DocumentRepository(workspace_id=workspace_id)