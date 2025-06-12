from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel
from database.vector_store import VectorStore
# from util.logging_config import log_error, error_logger

router = APIRouter(
    prefix="/vector",
    tags=["Vector Store"],
    responses={404: {"description": "Not found"}},
)

class VectorSearchRequest(BaseModel):
    query: str
    limit: int = 5

class VectorDocument(BaseModel):
    text: str
    metadata: Dict[str, Any]

class VectorStoreRequest(BaseModel):
    documents: List[VectorDocument]

@router.post("/search")
async def search_vectors(request: VectorSearchRequest):
    """
    Search for similar vectors in the vector store
    
    - **query**: Search query text
    - **limit**: Maximum number of results to return
    """
    try:
        vector_store = VectorStore()
        results = vector_store.search(request.query, request.limit)
        return {
            "query": request.query,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        # log_error(error_logger, e, f"Vector search failed for query: {request.query}")
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/store")
async def store_vectors(request: VectorStoreRequest):
    """
    Store documents in the vector store
    
    - **documents**: List of documents to store, each containing text and metadata
    """
    try:
        vector_store = VectorStore()
        documents = [{"text": doc.text, "metadata": doc.metadata} for doc in request.documents]
        
        print(request.documents)
        ids = vector_store.add_documents(documents)
        return {
            "message": f"Successfully stored {len(ids)} documents",
            "document_ids": ids
        }
    except Exception as e:
        # log_error(error_logger, e, "Failed to store vectors")
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{vector_id}")
async def delete_vector(vector_id: str):
    """
    Delete a vector from the store
    
    - **vector_id**: ID of the vector to delete
    """
    try:
        vector_store = VectorStore()
        vector_store.delete_vector(vector_id)
        return {"message": f"Successfully deleted vector {vector_id}"}
    except Exception as e:
        # log_error(error_logger, e, f"Failed to delete vector {vector_id}")
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{vector_id}")
async def get_vector(vector_id: str):
    """
    Get a vector from the store
    
    - **vector_id**: ID of the vector to retrieve
    """
    try:
        vector_store = VectorStore()
        doc = vector_store.get_document(vector_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Vector not found")
        return doc
    except HTTPException as e:
        raise e
    except Exception as e:
        # log_error(error_logger, e, f"Failed to get vector {vector_id}")
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{vector_id}")
async def update_vector(vector_id: str, document: VectorDocument):
    """
    Update a vector in the store
    
    - **vector_id**: ID of the vector to update
    - **document**: New document content and metadata
    """
    try:
        vector_store = VectorStore()
        vector_store.update_document(
            document_id=vector_id,
            text=document.text,
            metadata=document.metadata
        )
        return {"message": f"Successfully updated vector {vector_id}"}
    except Exception as e:
        # log_error(error_logger, e, f"Failed to update vector {vector_id}")
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
