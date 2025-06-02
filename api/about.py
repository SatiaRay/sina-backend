from fastapi import APIRouter
import tomli

router = APIRouter()

@router.get("/version")
async def get_version():
    with open("pyproject.toml", "rb") as f:
        pyproject = tomli.load(f)
        version = pyproject["project"]["version"]
    return {"version": version}
