from fastapi import APIRouter, HTTPException
import json
from pathlib import Path

# Import the dynamic function caller
from models.tools.functions import call_function

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


@router.post("/call", summary="Call a tool function dynamically")
async def call_tool_function(request: ToolCallRequest):
    """
    Dynamically call a tool function for manual testing.
    Request body: {"function_name": "ClassName-methodName", "args": [ ... ]}
    """
    try:
        args = request.args or []
        result = call_function(request.function_name, *args)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calling function: {str(e)}")
