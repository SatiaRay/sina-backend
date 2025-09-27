import asyncio
from provider.service_container import container
import traceback
import sys
from models.tools.functions.logging_decorator import FunctionCallLogger
from typing import Union, Dict, Any, Optional
from fastapi import WebSocket
from provider.service_container import container
from util.redis_binding_manager import binding_manager
from models.tools.functions.app_satia_co import AppSatiaCo
import os
import json

# Cache for map.json content
_map_json_cache = None


def get_map_json():
    global _map_json_cache
    if _map_json_cache is None:
        map_path = os.path.join(os.path.dirname(__file__), "map.json")
        with open(map_path, encoding="utf-8") as f:
            _map_json_cache = json.load(f)
    return _map_json_cache


async def call_function(
    function_name: str,
    *args,
    client_websocket_connection: WebSocket = None,
    binding_token: str = None,
    **kwargs
) -> Any:
    """
    Enhanced function caller with logging support and Redis-based binding.
    
    Args:
        function_name: Format "{class_name}-{method_name}"
        *args: Positional arguments
        client_websocket_connection: websocket connection object
        binding_token: Unique token for this WebSocket session to retrieve bindings
        **kwargs: Keyword arguments
    
    Supports both legacy style:
        call_function("Mayoral-submitRequest", {"mobile": "...", ...})
    
    And new style:
        call_function("Mayoral-submitRequest", mobile="...", ...)
    """
    # bind websocket connection object to service container to make it available for for function tools
    if client_websocket_connection:
        container.instance('client_websocket_connection', client_websocket_connection)
        
        map_json = get_map_json()
        lables = map_json.get("lables", {})
        lable = lables.get(function_name)
        if lable:
            await client_websocket_connection.send_json(
                {"event": "call_function", "lable": lable}
            )


    # Initialize logger with user context
    logger = FunctionCallLogger()
    
    try:
        class_name, method_name = function_name.split('-')
        
        # Try to get instance from Redis binding first, then fall back to service container
        instance = None
        if binding_token:
            binding_data = binding_manager.get_binding(binding_token, class_name)
            if binding_data:
                # Create instance from Redis binding data
                if class_name == "AppSatiaCo":
                    instance = AppSatiaCo(
                        token=binding_data.get("token", ""),
                        customer=binding_data.get("customer", "")
                    )
                # Add other classes here as needed
        
        # Fallback to service container if Redis binding not found
        if not instance:
            instance = container.make(class_name)
        
        if not instance:
            print(f"Class {class_name} not found in Redis bindings or service container")
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