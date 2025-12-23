from fastapi import APIRouter, Depends
from oauth.introspection.dependencies import get_current_user

router = APIRouter()

@router.get("/whoami")
def whoami(current_user: dict = Depends(get_current_user)):
    return current_user

