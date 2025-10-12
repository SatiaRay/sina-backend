from fastapi import APIRouter, HTTPException
import json
from pathlib import Path

# Import the dynamic function caller
from models.tools.functions import call_function
from util.redis_binding_manager import binding_manager

router = APIRouter(
    prefix="/ai-functions",
    tags=["AI Functions"],
    responses={404: {"description": "Not found"}},
)

@router.get("/map", summary="Get AI Functions Map")
async def get_functions_map():
    """
    Returns the JSON map of available AI functions and their descriptions.
    """
    try:
        map_path = Path(__file__).parent.parent / "models" / "tools" / "functions" / "map.json"
        with open(map_path, 'r', encoding='utf-8') as f:
            functions_map = json.load(f)
        return functions_map
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading functions map: {str(e)}")


# New API endpoint to call tool functions for manual testing
from fastapi import Request
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

class ToolCallRequest(BaseModel):
    function_name: str
    args: Optional[List[Any]] = None
    dependencies: Optional[Dict] = None


@router.post("/call", summary="Call a tool function dynamically")
async def call_tool_function(request: ToolCallRequest):
    """
    Dynamically call a tool function for manual testing.
    Request body: {"function_name": "ClassName-methodName", "args": [ ... ]}
    """
    try:
        # Binding Service Data Dependencies To Redis
        classname = request.function_name.split('-')[0]
        binding_token = binding_manager.generate_binding_token()
        binding_manager.store_binding(binding_token, classname, request.dependencies)

        args = request.args or []
        result = await call_function(request.function_name, binding_token=binding_token, *args)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calling function: {str(e)}")
