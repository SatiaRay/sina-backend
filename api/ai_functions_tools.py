from fastapi import APIRouter, HTTPException
import json
from pathlib import Path

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
