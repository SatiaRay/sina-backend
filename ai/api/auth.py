from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/whoami")
def whoami(request: Request):
    return {
        "scopes": getattr(request.state, "scopes", []),
        "user_id": getattr(request.state, "user_id", None),
    }

