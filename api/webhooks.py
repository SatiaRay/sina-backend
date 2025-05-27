from fastapi import APIRouter, HTTPException, Request, Body
from typing import Dict, Any
import logging
from util.event_bus import event_bus, VectorStoreEvent

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks"],
    responses={404: {"description": "Not found"}},
)

@router.post("/update_vector")
async def handle_vector_update():
    """
    Handle vector store update notifications
    
    Args:
        payload: The webhook payload containing document_id, vector_id, and status
        
    Returns:
        Dict containing status and message
    """
    try:    
        # Publish vector store update event
        event_bus.publish(VectorStoreEvent.COLLECTION_MODIFIED)
        
        return {
            "status": "success",
            "message": "Vector update notification processed successfully"
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error processing vector update webhook: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing vector update webhook: {str(e)}"
        )
