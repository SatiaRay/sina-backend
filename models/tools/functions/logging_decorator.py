import time
import json
from datetime import datetime
from typing import Dict, Any, Optional, Callable
import functools

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
        """Write log entry to appropriate destination"""
        # In production, you might want to use a proper logging system
        print(json.dumps(log_entry, indent=2))  # For development
        
        # TODO: Add actual logging transport (file, database, etc.)
        # Example: self.logging_client.log(log_entry)