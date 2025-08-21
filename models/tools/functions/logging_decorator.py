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
            # Prepare log structure
            log_entry: Dict[str, Any] = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "tool": self._get_clean_tool_name(func),
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
    
    def _get_clean_tool_name(self, func: Callable) -> str:
        """Extract a clean tool name in format ClassName.method_name"""
        try:
            if hasattr(func, '__qualname__'):
                # Get the full qualname (e.g., 'models.tools.functions.neshan.Neshan.search_address')
                qualname = func.__qualname__
                
                # Split into parts and get the last two components
                parts = qualname.split('.')
                if len(parts) >= 2:
                    # Join the last two parts (class and method)
                    return f"{parts[-2]}.{parts[-1]}"
                else:
                    # If there's only one part (just function name)
                    return qualname
            elif hasattr(func, '__name__'):
                return func.__name__
        except:
            return "unknown_function"
    
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