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

@router.get("/", response_model=List[Dict[str, Any]])
async def get_logs(
    hours: int = Query(24, description="Time window in hours"),
    tool_name: Optional[str] = Query(None, description="Filter by tool name"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    min_duration: Optional[int] = Query(None, description="Minimum duration in ms"),
    max_duration: Optional[int] = Query(None, description="Maximum duration in ms"),
    has_errors: bool = Query(False, description="Only include failed calls"),
    limit: int = Query(100, description="Maximum results to return")
):
    """
    Get function call logs with filtering options
    """
    try:
        with FunctionCallLogRepository() as repo:
            logs = repo.get_recent_logs(
                hours=hours,
                tool_name=tool_name,
                user_id=user_id,
                min_duration=min_duration,
                max_duration=max_duration,
                has_errors=has_errors,
                limit=limit
            )
            # Ensure proper serialization
            return [model_to_dict(log) if hasattr(log, '__table__') else log for log in logs]
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
            return [dict(stat) for stat in stats]  # Convert Row objects to dicts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

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

@router.get("/search")
async def search_logs(
    query: str = Query(..., description="Search term"),
    limit: int = Query(50, description="Maximum results to return")
):
    try:
        with FunctionCallLogRepository() as repo:
            results = repo.search_logs(search_term=query, limit=limit)
            return [model_to_dict(log) for log in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{log_id}")
async def get_log_by_id(log_id: int):
    try:
        with FunctionCallLogRepository() as repo:
            log = repo.get_by_id(log_id)
            if not log:
                raise HTTPException(status_code=404, detail="Log not found")
            return model_to_dict(log)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))