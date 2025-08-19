from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timedelta
from database.repositories.function_call_log_repository import FunctionCallLogRepository
from util.database import model_to_dict

router = APIRouter(
    prefix="/function-calling-logs",
    tags=["Function Call Logs"],
    responses={404: {"description": "Not found"}},
)

class LogQueryParams(BaseModel):
    hours: int = 24
    tool_name: Optional[str] = None
    user_id: Optional[str] = None
    min_duration: Optional[int] = None
    max_duration: Optional[int] = None
    has_errors: bool = False
    limit: int = 100

class ToolStatsResponse(BaseModel):
    tool: str
    call_count: int
    avg_duration: float
    total_tokens: int
    error_count: int

class UserActivityResponse(BaseModel):
    total_calls: int
    avg_duration: float
    total_tokens: int
    error_count: int
    most_used_tools: List[Dict[str, Any]]

class PaginatedLogResponse(BaseModel):
    items: List[Dict[str, Any]]
    total: int
    page: int
    per_page: int
    total_pages: int

@router.get("/", response_model=PaginatedLogResponse)
async def get_logs(
    hours: int = Query(24, description="Time window in hours"),
    tool_name: Optional[str] = Query(None, description="Filter by tool name"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    min_duration: Optional[int] = Query(None, description="Minimum duration in ms"),
    max_duration: Optional[int] = Query(None, description="Maximum duration in ms"),
    has_errors: bool = Query(False, description="Only include failed calls"),
    page: int = Query(1, description="Page number", ge=1),
    per_page: int = Query(50, description="Items per page", ge=1, le=200)
):
    """
    Get paginated function call logs with filtering options
    
    Returns:
    {
        "items": List[LogEntry],
        "total": int,
        "page": int,
        "per_page": int,
        "total_pages": int
    }
    """
    try:
        with FunctionCallLogRepository() as repo:
            # Get total count first
            total = repo.get_logs_count(
                hours=hours,
                tool_name=tool_name,
                user_id=user_id,
                min_duration=min_duration,
                max_duration=max_duration,
                has_errors=has_errors
            )
            
            # Calculate offset
            offset = (page - 1) * per_page
            
            # Get paginated logs
            logs = repo.get_paginated_logs(
                hours=hours,
                tool_name=tool_name,
                user_id=user_id,
                min_duration=min_duration,
                max_duration=max_duration,
                has_errors=has_errors,
                offset=offset,
                limit=per_page
            )
            
            # Calculate total pages
            total_pages = (total + per_page - 1) // per_page
            
            return {
                "items": [model_to_dict(log) if hasattr(log, '__table__') else log for log in logs],
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve logs: {str(e)}"
        )

@router.get("/stats/tools", response_model=List[ToolStatsResponse])
async def get_tool_usage_stats(
    days: int = Query(7, description="Time window in days"),
    top_n: int = Query(10, description="Number of top tools to return")
):
    try:
        with FunctionCallLogRepository() as repo:
            stats = repo.get_tool_usage_stats(days=days, top_n=top_n)
            return stats
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve tool statistics: {str(e)}"
        )

@router.get("/stats/user/{user_id}", response_model=UserActivityResponse)
async def get_user_activity(
    user_id: str,
    days: int = Query(30, description="Time window in days")
):
    try:
        with FunctionCallLogRepository() as repo:
            activity = repo.get_user_activity(user_id, days=days)
            return activity  # Assuming this already returns a dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/search", response_model=List[Dict[str, Any]])
async def search_logs(
    query: str = Query(..., description="Search term"),
    limit: int = Query(50, description="Maximum results to return")
):
    """
    Search logs by tool name, error message, or parameters
    """
    try:
        with FunctionCallLogRepository() as repo:
            results = repo.search_logs(search_term=query, limit=limit)
            
            # Convert results to serializable format
            serialized_results = []
            for log in results:
                if hasattr(log, '__table__'):  # SQLAlchemy model
                    result = {
                        "id": log.id,
                        "timestamp": log.timestamp.isoformat(),
                        "tool": log.tool,
                        "params": log.params,
                        "user_id": log.user_id,
                        "session_id": log.session_id,
                        # Clean response data by removing Ellipsis
                        "response": clean_response_data(log.response),
                        "error": log.error,
                        "duration_ms": log.duration_ms,
                        "tokens_used": log.tokens_used,
                        "additional_metadata": log.additional_metadata
                    }
                else:  # Already a dict
                    result = {
                        **log,
                        "response": clean_response_data(log.get("response"))
                    }
                
                serialized_results.append(result)
            
            return serialized_results
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search logs: {str(e)}"
        )

def clean_response_data(response_data: Any) -> Any:
    """Remove any non-serializable elements from response data"""
    if response_data is None:
        return None
    if isinstance(response_data, dict):
        return {k: clean_response_data(v) for k, v in response_data.items()}
    if isinstance(response_data, list):
        return [clean_response_data(item) for item in response_data]
    if isinstance(response_data, (str, int, float, bool)):
        return response_data
    # Remove Ellipsis and other non-serializable objects
    return None

@router.get("/{log_id}")
async def get_log_by_id(log_id: int):
    """
    Get a specific log entry by ID
    
    - **log_id**: ID of the log entry
    """
    try:
        with FunctionCallLogRepository() as repo:
            log = repo.get_by_id(log_id)
            if not log:
                raise HTTPException(status_code=404, detail="Log not found")
            
            # Convert to dictionary format
            log_dict = {
                "id": log.id,
                "timestamp": log.timestamp.isoformat() if hasattr(log, 'timestamp') else None,
                "tool": log.tool,
                "params": log.params,
                "user_id": log.user_id,
                "session_id": log.session_id,
                "response": log.response,
                "error": log.error,
                "duration_ms": log.duration_ms,
                "tokens_used": log.tokens_used,
                "additional_metadata": log.additional_metadata
            }
            
            return log_dict
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve log: {str(e)}"
        )