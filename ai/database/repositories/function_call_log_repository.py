from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, String, case
import uuid
from database.models import FunctionCallLog, SessionLocal


class FunctionCallLogRepository:
    def __init__(self, db: Session = None, workspace_id: Optional[Union[str, uuid.UUID]] = None):
        self.db = db or SessionLocal()
        self.workspace_id = workspace_id
        if workspace_id and isinstance(workspace_id, str):
            self.workspace_id = uuid.UUID(workspace_id)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()

    def _apply_workspace_filter(self, query):
        """Apply workspace filter to query if workspace_id is set"""
        if self.workspace_id:
            query = query.filter(FunctionCallLog.workspace_id == self.workspace_id)
        return query

    def _ensure_workspace_id(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure workspace_id is included in data"""
        if self.workspace_id and 'workspace_id' not in data:
            data['workspace_id'] = self.workspace_id
        elif not self.workspace_id and 'workspace_id' not in data:
            raise ValueError("workspace_id must be provided either in constructor or in data")
        return data

    def create(self, log_data: Dict[str, Any]) -> FunctionCallLog:
        """Create a new function call log entry with workspace isolation"""
        log_data = self._ensure_workspace_id(log_data)
        
        log_record = FunctionCallLog(
            timestamp=log_data.get('timestamp'),
            tool=log_data.get('tool'),
            params=log_data.get('params'),
            session_id=log_data.get('session_id'),
            response=log_data.get('response'),
            error=log_data.get('error'),
            duration_ms=log_data.get('duration_ms'),
            tokens_used=log_data.get('tokens_used'),
            additional_metadata=log_data.get('additional_metadata'),
            workspace_id=log_data.get('workspace_id')
        )
        self.db.add(log_record)
        self.db.commit()
        self.db.refresh(log_record)
        return log_record

    def get_by_id(self, log_id: int) -> Optional[FunctionCallLog]:
        """Get a log entry by its ID within current workspace"""
        query = self.db.query(FunctionCallLog).filter(FunctionCallLog.id == log_id)
        query = self._apply_workspace_filter(query)
        return query.first()

    def get_recent_logs(
        self,
        hours: int = 24,
        tool_name: Optional[str] = None,
        session_id: Optional[str] = None,
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
        has_errors: bool = False,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent logs with filtering options within current workspace"""
        query = self.db.query(FunctionCallLog)
        query = self._apply_workspace_filter(query)
        
        # Time filter
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        query = query.filter(FunctionCallLog.timestamp >= time_threshold)
        
        # Additional filters
        if tool_name:
            query = query.filter(FunctionCallLog.tool == tool_name)
        if session_id:
            query = query.filter(FunctionCallLog.session_id == session_id)
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
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "tool": log.tool,
            "params": log.params,
            "session_id": log.session_id,
            "response": log.response,
            "error": log.error,
            "duration_ms": log.duration_ms,
            "tokens_used": log.tokens_used,
            "additional_metadata": log.additional_metadata,
            "workspace_id": str(log.workspace_id) if log.workspace_id else None
        } for log in results]

    def get_tool_usage_stats(self, days: int, top_n: int) -> List[Dict[str, Any]]:
        """Get tool usage statistics within current workspace"""
        time_threshold = datetime.utcnow() - timedelta(days=days)
        
        query = self.db.query(
            FunctionCallLog.tool,
            func.count(FunctionCallLog.id).label('call_count'),
            func.avg(FunctionCallLog.duration_ms).label('avg_duration'),
            func.sum(FunctionCallLog.tokens_used).label('total_tokens'),
            func.sum(
                case(
                    (FunctionCallLog.error.isnot(None), 1),
                    else_=0
                )
            ).label('error_count')
        ).filter(
            FunctionCallLog.timestamp >= time_threshold
        )
        
        query = self._apply_workspace_filter(query)
        
        results = query.group_by(
            FunctionCallLog.tool
        ).order_by(
            func.count(FunctionCallLog.id).desc()
        ).limit(top_n).all()
        
        # Convert SQLAlchemy result tuples to dictionaries
        return [{
            "tool": r[0],
            "call_count": r[1],
            "avg_duration": float(r[2]) if r[2] is not None else 0.0,
            "total_tokens": int(r[3]) if r[3] is not None else 0,
            "error_count": int(r[4]) if r[4] is not None else 0
        } for r in results]

    def get_session_activity(self, session_id: str, days: int = 7) -> Dict[str, Any]:
        """Get session activity statistics within current workspace"""
        time_threshold = datetime.utcnow() - timedelta(days=days)
        
        # Query for session stats
        query = self.db.query(
            func.count(FunctionCallLog.id).label('total_calls'),
            func.avg(FunctionCallLog.duration_ms).label('avg_duration'),
            func.sum(FunctionCallLog.tokens_used).label('total_tokens'),
            func.sum(
                case(
                    (FunctionCallLog.error.isnot(None), 1),
                    else_=0
                )
            ).label('error_count')
        ).filter(
            FunctionCallLog.timestamp >= time_threshold,
            FunctionCallLog.session_id == session_id
        )
        
        query = self._apply_workspace_filter(query)
        stats = query.first()
        
        # Query for most used tools in this session
        tools_query = self.db.query(
            FunctionCallLog.tool,
            func.count(FunctionCallLog.id).label('tool_count')
        ).filter(
            FunctionCallLog.timestamp >= time_threshold,
            FunctionCallLog.session_id == session_id
        )
        
        tools_query = self._apply_workspace_filter(tools_query)
        most_used_tools = tools_query.group_by(
            FunctionCallLog.tool
        ).order_by(
            func.count(FunctionCallLog.id).desc()
        ).limit(5).all()
        
        return {
            'total_calls': stats.total_calls if stats.total_calls else 0,
            'avg_duration': float(stats.avg_duration) if stats.avg_duration else 0.0,
            'total_tokens': int(stats.total_tokens) if stats.total_tokens else 0,
            'error_count': int(stats.error_count) if stats.error_count else 0,
            'most_used_tools': [{'tool': t[0], 'count': t[1]} for t in most_used_tools]
        }

    def search_logs(self, search_term: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search logs within current workspace by tool name, error message, or parameters"""
        query = self.db.query(FunctionCallLog).filter(
            or_(
                FunctionCallLog.tool.ilike(f"%{search_term}%"),
                FunctionCallLog.error.ilike(f"%{search_term}%"),
                FunctionCallLog.params.cast(String).ilike(f"%{search_term}%")
            )
        )
        
        query = self._apply_workspace_filter(query)
        
        results = query.order_by(
            FunctionCallLog.timestamp.desc()
        ).limit(limit).all()
        
        return [{
            "id": log.id,
            "timestamp": log.timestamp,
            "tool": log.tool,
            "params": log.params,
            "session_id": log.session_id,
            "response": log.response,
            "error": log.error,
            "duration_ms": log.duration_ms,
            "tokens_used": log.tokens_used,
            "additional_metadata": log.additional_metadata,
            "workspace_id": str(log.workspace_id) if log.workspace_id else None
        } for log in results]

    def get_logs_count(
        self,
        hours: int,
        tool_name: Optional[str] = None,
        session_id: Optional[str] = None,
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
        has_errors: bool = False
    ) -> int:
        """Get total count of logs matching filters within current workspace"""
        query = self._build_base_query(
            hours=hours,
            tool_name=tool_name,
            session_id=session_id,
            min_duration=min_duration,
            max_duration=max_duration,
            has_errors=has_errors
        )
        return query.count()

    def get_paginated_logs(
        self,
        hours: int,
        tool_name: Optional[str] = None,
        session_id: Optional[str] = None,
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
        has_errors: bool = False,
        offset: int = 0,
        limit: int = 50
    ) -> List[FunctionCallLog]:
        """Get paginated logs matching filters within current workspace"""
        query = self._build_base_query(
            hours=hours,
            tool_name=tool_name,
            session_id=session_id,
            min_duration=min_duration,
            max_duration=max_duration,
            has_errors=has_errors
        )
        return query.offset(offset).limit(limit).all()

    def _build_base_query(
        self,
        hours: int,
        tool_name: Optional[str] = None,
        session_id: Optional[str] = None,
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
        has_errors: bool = False
    ):
        """Build base query with filters and workspace isolation"""
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        query = self.db.query(FunctionCallLog).filter(
            FunctionCallLog.timestamp >= time_threshold
        )
        
        # Apply workspace filter
        query = self._apply_workspace_filter(query)
        
        # Apply additional filters
        if tool_name:
            query = query.filter(FunctionCallLog.tool == tool_name)
        if session_id:
            query = query.filter(FunctionCallLog.session_id == session_id)
        if min_duration:
            query = query.filter(FunctionCallLog.duration_ms >= min_duration)
        if max_duration:
            query = query.filter(FunctionCallLog.duration_ms <= max_duration)
        if has_errors:
            query = query.filter(FunctionCallLog.error.isnot(None))
            
        return query.order_by(FunctionCallLog.timestamp.desc())

    def delete_by_id(self, log_id: int) -> bool:
        """Delete a log entry by ID within current workspace"""
        log = self.get_by_id(log_id)
        if log:
            self.db.delete(log)
            self.db.commit()
            return True
        return False

    def update_log(self, log_id: int, update_data: Dict[str, Any]) -> Optional[FunctionCallLog]:
        """Update a log entry within current workspace"""
        log = self.get_by_id(log_id)
        if log:
            # Don't allow changing workspace_id
            if 'workspace_id' in update_data:
                del update_data['workspace_id']
                
            for key, value in update_data.items():
                setattr(log, key, value)
            self.db.commit()
            self.db.refresh(log)
        return log