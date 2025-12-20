# src/main.py
import os
from pathlib import Path
import sys

from fastapi import FastAPI, Depends, Request, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.schemas import StoreDocumentRequest, UpdateDocumentRequest
from src.database import get_db
from sqlalchemy.orm import Session
from src.repositories import get_document_repository
from src.vector import VectorStore


root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

app = FastAPI()
vector = VectorStore()

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
    repo = Depends(get_document_repository)  # Use dependency injection
):
    try:
        repo.create(db, document.dict())
        return {"msg": "succeed"}
    except Exception as e:
        print("Error in storing document:", e)
        raise HTTPException(status_code=500, detail="Store document failed!")


@app.get("/search")
async def search(
    query: str,
    db: Session = Depends(get_db),
    repo = Depends(get_document_repository)  # Add repo dependency
):
    try:
        # For now, just return vector search results
        results = vector.search(query=query)
        
        # Filter by current workspace
        if hasattr(repo, 'workspace_id'):
            filtered_results = []
            for result in results:
                metadata = result.get('metadata', {})
                if isinstance(metadata, dict) and metadata.get('workspace_id') == repo.workspace_id:
                    filtered_results.append(result)
            return filtered_results
        
        return results
    except Exception as e:
        print(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail="Search failed!")


@app.delete("/{id}")
async def delete(
    id: int,
    db: Session = Depends(get_db),
    repo = Depends(get_document_repository)  # Use dependency injection
):
    try:
        repo.delete(db, id)
        return {"msg": "succeed"}
    except Exception as e:
        print("Error deleting document:", e)
        raise HTTPException(status_code=500, detail="Delete document failed!")


@app.put("/{id}")
async def update(
    id: int,
    document: UpdateDocumentRequest,
    db: Session = Depends(get_db),
    repo = Depends(get_document_repository)  # Use dependency injection
):
    try:
        repo.update(db, id, document.dict())
        return {"msg": "succeed"}
    except Exception as e:
        print("Error updating document:", e)
        raise HTTPException(status_code=500, detail="Update document failed!")


@app.get("/")
async def all(
    page: int = 1,
    perpage: int = 20,
    db: Session = Depends(get_db),
    repo = Depends(get_document_repository)  # Use dependency injection
):
    try:
        offset = (page - 1) * perpage
        documents = repo.get_all(db, offset=offset, limit=perpage)
        total_docs = repo.count(db)
        total_pages = (total_docs + perpage - 1) // perpage if perpage > 0 else 1
        
        # Convert documents to dicts safely
        documents_list = []
        for doc in documents:
            doc_dict = doc.__dict__.copy()
            # Remove SQLAlchemy internal attribute
            doc_dict.pop('_sa_instance_state', None)
            documents_list.append(doc_dict)
        
        return {
            "documents": documents_list,
            "pages": total_pages,
            "total": total_docs,
        }
    except Exception as e:
        print("Error in get all documents:", e)
        raise HTTPException(status_code=500, detail="Get all documents failed!")


@app.get("/{id}")
async def find(
    id: int,
    db: Session = Depends(get_db),
    repo = Depends(get_document_repository)  # Use dependency injection
):
    try:
        doc = repo.get(db, id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Convert to dict safely
        doc_dict = doc.__dict__.copy()
        doc_dict.pop('_sa_instance_state', None)
        return doc_dict
    except HTTPException:
        raise
    except Exception as e:
        print("Error finding document:", e)
        raise HTTPException(status_code=500, detail="Find document failed!")