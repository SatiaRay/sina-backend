import asyncio
from provider.service_container import container
import traceback
import sys
from models.tools.functions.logging_decorator import FunctionCallLogger
from typing import Union, Dict, Any
from fastapi import WebSocket
from provider.service_container import container

async def call_function(
    function_name: str,
    *args,
    clinet_websocket_connection: WebSocket,
    user_context: Dict[str, str] = None,
    **kwargs
) -> Any:
    """
    Enhanced function caller with logging support.
    
    Args:
        function_name: Format "{class_name}-{method_name}"
        *args: Positional arguments
        clinet_websocket_connection: websocket connection object
        user_context: Dictionary with 'user_id' and 'session_id'
        **kwargs: Keyword arguments
    
    Supports both legacy style:
        call_function("Mayoral-submitRequest", {"mobile": "...", ...})
    
    And new style:
        call_function("Mayoral-submitRequest", mobile="...", ...)
    """
    # bind websocket connection object to service container to make it available for for function tools
    container.instance('client_websocket_connection', clinet_websocket_connection)
    
    # Initialize logger with user context
    user_id = (user_context or {}).get('user_id', 'system')
    session_id = (user_context or {}).get('session_id', 'system')
    logger = FunctionCallLogger(user_id=user_id, session_id=session_id)
    
    try:
        class_name, method_name = function_name.split('-')
        instance = container.make(class_name)
        if not instance:
            print(f"Class {class_name} not found in service container")
            return None
            
        method = getattr(instance, method_name, None)
        if not method:
            print(f"Method {method_name} not found in class {class_name}")
            return None
        
        # Apply logging decorator
        logged_method = logger(method)
        
        # Handle both legacy (single dict) and new style arguments
        if len(args) == 1 and isinstance(args[0], dict) and not kwargs:
            return await logged_method(**args[0])
        elif not args and kwargs:
            return await logged_method(**kwargs)
        else:
            return await logged_method(*args)

    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        stack_trace = traceback.format_exception(exc_type, exc_value, exc_traceback)
        print(f"Error calling {function_name}: {str(e)}")
        print(f"Stack trace: {''.join(stack_trace)}")
        return None