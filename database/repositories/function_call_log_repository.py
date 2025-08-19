from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from database.models import FunctionCallLog, SessionLocal

class FunctionCallLogRepository:
    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()

    def create(self, log_data: Dict[str, Any]) -> FunctionCallLog:
        """Create a new function call log entry"""
        log_record = FunctionCallLog(
            timestamp=log_data.get('timestamp'),
            tool=log_data.get('tool'),
            params=log_data.get('params'),
            user_id=log_data.get('user_id'),
            session_id=log_data.get('session_id'),
            response=log_data.get('response'),
            error=log_data.get('error'),
            duration_ms=log_data.get('duration_ms'),
            tokens_used=log_data.get('tokens_used'),
            additional_metadata=log_data.get('additional_metadata')
        )
        self.db.add(log_record)
        self.db.commit()
        self.db.refresh(log_record)
        return log_record

    def get_by_id(self, log_id: int) -> Optional[FunctionCallLog]:
        """Get a log entry by its ID"""
        return self.db.query(FunctionCallLog).filter(FunctionCallLog.id == log_id).first()

    
    def get_recent_logs(
    self,
    hours: int = 24,
    tool_name: Optional[str] = None,
    user_id: Optional[str] = None,
    min_duration: Optional[int] = None,
    max_duration: Optional[int] = None,
    has_errors: bool = False,
    limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent logs with filtering options"""
        query = self.db.query(FunctionCallLog)
        
        # Time filter
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        query = query.filter(FunctionCallLog.timestamp >= time_threshold)
        
        # Additional filters
        if tool_name:
            query = query.filter(FunctionCallLog.tool == tool_name)
        if user_id:
            query = query.filter(FunctionCallLog.user_id == user_id)
        if min_duration:
            query = query.filter(FunctionCallLog.duration_ms >= min_duration)
        if max_duration:
            query = query.filter(FunctionCallLog.duration_ms <= max_duration)
        if has_errors:
            query = query.filter(FunctionCallLog.error.isnot(None))
        
        results = query.order_by(FunctionCallLog.timestamp.desc()).limit(limit).all()
        
        # Convert to list of dictionaries
        return [{
            "id": log.id,
            "timestamp": log.timestamp.isoformat(),
            "tool": log.tool,
            "params": log.params,
            "user_id": log.user_id,
            "session_id": log.session_id,
            "response": log.response,
            "error": log.error,
            "duration_ms": log.duration_ms,
            "tokens_used": log.tokens_used,
            "additional_metadata": log.additional_metadata
        } for log in results]

    def get_tool_usage_stats(self, days: int, top_n: int) -> List[Dict[str, Any]]:
        time_threshold = datetime.utcnow() - timedelta(days=days)
        
        results = self.db.query(
            FunctionCallLog.tool,
            func.count(FunctionCallLog.id).label('call_count'),
            func.avg(FunctionCallLog.duration_ms).label('avg_duration'),
            func.sum(FunctionCallLog.tokens_used).label('total_tokens'),
            func.sum(case(
                [(FunctionCallLog.error.isnot(None), 1)],
                else_=0
            )).label('error_count')
        ).filter(
            FunctionCallLog.timestamp >= time_threshold
        ).group_by(
            FunctionCallLog.tool
        ).order_by(
            func.count(FunctionCallLog.id).desc()
        ).limit(top_n).all()
        
        return results

    def get_user_activity(self, user_id, days):
        # Ensure this returns a dict, not SQLAlchemy objects
        return {
            'total_calls': stats.total_calls,
            'avg_duration': float(stats.avg_duration),
            'total_tokens': stats.total_tokens,
            'error_count': stats.error_count,
            'most_used_tools': [dict(t) for t in most_used_tools]
        }

    def search_logs(
        self,
        search_term: str,
        limit: int = 50
    ) -> List[FunctionCallLog]:
        """Search logs by tool name, error message, or params"""
        return self.db.query(FunctionCallLog).filter(
            or_(
                FunctionCallLog.tool.ilike(f"%{search_term}%"),
                FunctionCallLog.error.ilike(f"%{search_term}%"),
                FunctionCallLog.params.cast(String).ilike(f"%{search_term}%")
            )
        ).order_by(
            FunctionCallLog.timestamp.desc()
        ).limit(limit).all()