# src/main.py (updated)
import os
from pathlib import Path
import sys

from fastapi import FastAPI, Depends, Request, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.schemas import StoreDocumentRequest, UpdateDocumentRequest
from src.database import get_db
from sqlalchemy.orm import Session


root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

app = FastAPI()

# ✅ CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Keep existing guard_middleware for now
from src.util import auth_validate

@app.middleware("http")
async def guard_middleware(request: Request, call_next):    
    # Skip auth for preflight CORS requests
    if request.method == "OPTIONS":
        return await call_next(request)
    
    auth = await auth_validate(credential=request)

    if not auth:
        return JSONResponse(
            status_code=401,
            content={
                "msg": "Unauthorized - No token provided",
            }
        ) 
    
    # Extract workspace_id from scopes and add to request state
    scopes = getattr(request.state, "scopes", [])
    workspace_id = None
    
    for scope in scopes:
        if scope.startswith('workspace:'):
            workspace_id = scope.split(':')[1]
            break
    
    if workspace_id:
        # Add tenant context to request state
        request.state.tenant_context = {
            'workspace_id': workspace_id,
            'user_id': getattr(request.state, "user_id", None),
            'scopes': scopes
        }
    else:
        return JSONResponse(
            status_code=403,
            content={
                "msg": "Unauthorized - No workspace_id provided",
            }
        ) 
    
    response = await call_next(auth)
    return response


def get_session():
    from src.util import authorized_http_session_factory
    return authorized_http_session_factory()


@app.get("/test")
async def test():
    return {"msg": "The service is up !"}


@app.get("/whoami")
async def whoami(request: Request = None):
    # Return both old and new format for backward compatibility
    response = {
        "scopes": getattr(request.state, "scopes", []),
        "user_id": getattr(request.state, "user_id", None),
    }
    
    # Add tenant context if available
    if hasattr(request.state, 'tenant_context'):
        response['tenant_context'] = request.state.tenant_context
        response['workspace_id'] = request.state.tenant_context.get('workspace_id')
    
    return response


@app.post("/")
async def store(
    document: StoreDocumentRequest,
    db: Session = Depends(get_db),
    response: Response = None
):
    from src.repositories import DocumentRepository
    repo = DocumentRepository()
    try:
        repo.create(db, document.dict())
        return {"msg": "succeed"}
    except Exception as e:
        print("Error in storing document:", e)
        response.status_code = 500
        return {"msg": "Store document failed !"}


@app.get("/search")
async def search(
    query: str,
    db: Session = Depends(get_db),
):
    return vector.search(query=query)


@app.delete("/{id}")
async def delete(
    id: int,
    db: Session = Depends(get_db),
    response: Response = None
):
    from src.repositories import DocumentRepository
    repo = DocumentRepository()
    try:
        repo.delete(db, id)
        return {"msg": "succeed"}
    except Exception as e:
        print("Error deleting document:", e)
        response.status_code = 500
        return {"msg": "Delete documents failed !"}


@app.put("/{id}")
async def update(
    id: int,
    document: UpdateDocumentRequest,
    db: Session = Depends(get_db),
    response: Response = None
):
    from src.repositories import DocumentRepository
    repo = DocumentRepository()
    try:
        repo.update(db, id, document.dict())
        return {"msg": "succeed"}
    except Exception as e:
        print("Error updating document:", e)
        response.status_code = 500
        return {"msg": "Update documents failed !"}


@app.get("/")
async def all(
    response: Response,
    page: int = 1,
    perpage: int = 20,
    db: Session = Depends(get_db),
):
    from src.repositories import DocumentRepository
    repo = DocumentRepository()
    try:
        offset = (page - 1) * perpage
        documents = repo.get_all(db, offset=offset, limit=perpage)
        total_docs = repo.count(db)
        total_pages = (total_docs + perpage - 1) // perpage
        return {
            "documents": [doc.__dict__ for doc in documents],
            "pages": total_pages,
            "total": total_docs,
        }
    except Exception as e:
        print("Error in get all documents:", e)
        response.status_code = 500
        return {"msg": "Get all documents failed !"}

@app.get("/{id}")
async def find(
    id: int,
    response: Response,
    db: Session = Depends(get_db),
):
    from src.repositories import DocumentRepository
    repo = DocumentRepository()
    try:
        return repo.get(db, id)
    except Exception as e:
        print("Error finding document:", e)
        response.status_code = 500
        return {"msg": "Find document failed !"}