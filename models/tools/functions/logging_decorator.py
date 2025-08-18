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
                "tool": f"{func.__module__}.{func.__qualname__}",
                "params": self._extract_params(args, kwargs),
                "user": {
                    "id": self.user_id,
                    "session": self.session_id
                },
                "metadata": {
                    "duration": 0,
                    "tokens": 0  # Will be updated later if available
                }
            }
            
            start_time = time.time()
            try:
                # Execute the function
                result = func(*args, **kwargs)
                log_entry["response"] = result
                return result
            except Exception as e:
                log_entry["error"] = str(e)
                raise
            finally:
                # Calculate duration
                log_entry["metadata"]["duration"] = int((time.time() - start_time) * 1000)
                # Write the log
                self._write_log(log_entry)
        
        return wrapped
    
    def _extract_params(self, args, kwargs) -> Dict[str, Any]:
        """Extract and sanitize parameters for logging"""
        params = {}
        
        # Handle positional arguments
        if args and len(args) > 1:  # Skip 'self' for methods
            params["args"] = args[1:] if hasattr(args[0], func.__name__) else args
        
        # Handle keyword arguments
        if kwargs:
            params.update(kwargs)
        
        # Sanitize sensitive data
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