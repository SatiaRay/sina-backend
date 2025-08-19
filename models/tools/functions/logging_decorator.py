import time
import json
from datetime import datetime
from typing import Dict, Any, Optional, Callable
import functools
from datetime import datetime
from sqlalchemy.orm import Session
from database.models import SessionLocal, FunctionCallLog
import os
from database.repositories.function_call_log_repository import FunctionCallLogRepository

class FunctionCallLogger:
    def __init__(self, user_id: str = "system", session_id: str = "system"):
        self.user_id = user_id
        self.session_id = session_id
    
    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            # Get the tool name safely
            tool_name = "unknown"
            try:
                if hasattr(func, '__qualname__'):
                    tool_name = f"{getattr(func, '__module__', 'unknown')}.{func.__qualname__}"
                elif hasattr(func, '__name__'):
                    tool_name = func.__name__
            except:
                tool_name = "unknown_function"
            
            # Prepare log structure
            log_entry: Dict[str, Any] = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "tool": tool_name,
                "params": self._extract_params(func, args, kwargs),
                "user": {
                    "id": self.user_id,
                    "session": self.session_id
                },
                "metadata": {
                    "duration": 0,
                    "tokens": 0
                }
            }
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                log_entry["response"] = result
                return result
            except Exception as e:
                log_entry["error"] = str(e)
                raise
            finally:
                log_entry["metadata"]["duration"] = int((time.time() - start_time) * 1000)
                self._write_log(log_entry)
        
        return wrapped
    
    def _extract_params(self, func: Callable, args, kwargs) -> Dict[str, Any]:
        """Extract and sanitize parameters for logging"""
        params = {}
        try:
            if args and len(args) > 1:
                if hasattr(func, '__name__') and hasattr(args[0], func.__name__):
                    params["args"] = args[1:]
                else:
                    params["args"] = args
        except:
            params["args"] = args
            
        params.update(kwargs)
        
        for sensitive in ['password', 'token', 'secret', 'bearer_token']:
            if sensitive in params:
                params[sensitive] = "***REDACTED***"
        
        return params
    
    def _write_log(self, log_entry: Dict[str, Any]):
        """Write log entry using the repository"""
        try:
            log_data = {
                'timestamp': datetime.fromisoformat(log_entry['timestamp'].replace('Z', '')),
                'tool': log_entry['tool'],
                'params': log_entry.get('params'),
                'user_id': log_entry['user'].get('id'),
                'session_id': log_entry['user'].get('session'),
                'response': log_entry.get('response'),
                'error': log_entry.get('error'),
                'duration_ms': log_entry['metadata']['duration'],
                'tokens_used': log_entry['metadata'].get('tokens'),
                'additional_metadata': {
                    'source': 'ai_function_call',
                    'environment': os.getenv('ENVIRONMENT', 'development')
                }
            }
            
            with FunctionCallLogRepository() as repo:
                repo.create(log_data)
                
            # Development logging
            if os.getenv('ENVIRONMENT', 'development') == 'development':
                import json
                print(json.dumps(log_entry, indent=2))
                
        except Exception as e:
            print(f"Failed to write function call log: {str(e)}")
            import json
            print(json.dumps(log_entry, indent=2))