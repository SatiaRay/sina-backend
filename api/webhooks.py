from fastapi import APIRouter, HTTPException, Request, Body
from typing import Dict, Any, List
import logging
from util.event_bus import event_bus, VectorStoreEvent
from database.vector_store import VectorStore
from pydantic import BaseModel

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks"],
    responses={404: {"description": "Not found"}},
)

class VectorStoreUpdateRequest(BaseModel):
    ids: List[str]
    documents: List[str]
    metadatas: List[Dict[str, Any]]
    embeddings: List[List[float]]

@router.post("/on_vector_new_doc")
async def handle_vector_update(request: VectorStoreUpdateRequest):
    """
    Handle vector store update notifications
    
    Args:
        request: The webhook payload containing vector store update data
        
    Returns:
        Dict containing status and message
    """
    try:
        # Log the incoming webhook
        logger.info(f"Received vector store update: {len(request.ids)} documents")

        # Initialize vector store
        vector_store = VectorStore()

        vector_store.save_documents(ids=request.ids, documents=request.documents, metadatas=request.metadatas, embeddings=request.embeddings)
        
        # Publish vector store update event
        event_bus.publish(VectorStoreEvent.COLLECTION_MODIFIED)
        
        return {
            "status": "success",
            "message": "Vector store update notification processed successfully",
            "document_count": len(request.ids)
        }
        
    except Exception as e:
        logger.error(f"Error processing vector store update: {str(e)}")
        print(e)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing vector store update: {str(e)}"
        )
