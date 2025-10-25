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


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def auth_dependency(request: Request):
    # Skip preflight OPTIONS
    if request.method == "OPTIONS":
        return None
    
    auth = await auth_validate(credential=request)
    if not auth:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return auth


def get_session():
    return authorized_http_session_factory()


@app.get("/test")
async def test(auth=Depends(auth_dependency)):
    return {"msg": "The service is up !"}


@app.get("/whoami")
async def whoami(auth=Depends(auth_dependency), request: Request = None):
    return {
        "scopes": getattr(request.state, "scopes", []),
        "user_id": getattr(request.state, "user_id", None),
    }


@app.post("/")
async def store(
    document: StoreDocumentRequest,
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
):
    return vector.search(query=query)


@app.delete("/{id}")
async def delete(
    id: int,
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
async def all_documents(
    response: Response,
    page: int = 1,
    perpage: int = 20,
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
async def single_document(
    id: int,
    response: Response,
):
    try:
        return repo.get(id)
    except Exception as e:
        print("Error finding document:", e)
        response.status_code = 500
        return {"msg": "Find document failed !"}