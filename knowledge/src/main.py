import os
from pathlib import Path
import sys

from fastapi import FastAPI, Depends, Request, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.repositories import DocumentRepository
from src.schemas import StoreDocumentRequest, UpdateDocumentRequest
from src.util import auth_validate, authorized_http_session_factory
from src.vector import VectorStore


root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

app = FastAPI()
vector = VectorStore()
repo = DocumentRepository()


# ✅ CORS middleware stays unchanged
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Checking authentication access_token and bind to service container if is valid
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
                "msg": "Unauthorized",
            }
        ) 
    
    response = await call_next(auth)
        
    return response


def get_session():
    return authorized_http_session_factory()


@app.get("/test")
async def test():
    return {"msg": "The service is up !"}


@app.get("/whoami")
async def whoami(request: Request = None):
    return {
        "scopes": getattr(request.state, "scopes", []),
        "user_id": getattr(request.state, "user_id", None),
    }


@app.post("/")
async def store(
    document: StoreDocumentRequest,
    session=Depends(get_session),
    response: Response = None
):
    try:
        repo.create(document.dict())
        return {"msg": "succeed"}
    except Exception as e:
        print("Error in storing document:", e)
        response.status_code = 500
        return {"msg": "Store document failed !"}


@app.get("/search")
async def search(
    query: str,
    session=Depends(get_session),
):
    return vector.search(query=query)


@app.delete("/{id}")
async def delete(
    id: int,
    session=Depends(get_session),
    response: Response = None
):
    try:
        repo.delete(id)
        return {"msg": "succeed"}
    except Exception as e:
        print("Error deleting document:", e)
        response.status_code = 500
        return {"msg": "Delete documents failed !"}


@app.put("/{id}")
async def update(
    id: int,
    document: UpdateDocumentRequest,
    session=Depends(get_session),
    response: Response = None
):
    try:
        repo.update(id, document.dict())
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
    session=Depends(get_session),
):
    try:
        offset = (page - 1) * perpage
        documents = repo.get_all(offset=offset, limit=perpage)
        total_docs = repo.count()
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
    session=Depends(get_session),
):
    try:
        return repo.get(id)
    except Exception as e:
        print("Error finding document:", e)
        response.status_code = 500
        return {"msg": "Find document failed !"}