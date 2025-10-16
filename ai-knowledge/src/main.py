from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from openai import BaseModel
from models import Document
from util import auth_validate
from vector_store import VectorStore

app = FastAPI()
vector = VectorStore()

# Checking authentication access_token and bind to service container if is valid
# @app.middleware("http")
# async def guard_middleware(request: Request, call_next):    
#     # Skip auth for preflight CORS requests
#     if request.method == "OPTIONS":
#         return await call_next(request)
    
#     auth = await auth_validate(credential=request)

#     if not auth:
#         return JSONResponse(
#             status_code=401,
#             content={
#                 "msg": "Unauthorized",
#             }
#         ) 
    
#     response = await call_next(auth)
        
#     return response


@app.get("/test")
def test():
    return {"msg": "The service is up !"}


@app.post("/store")
def store(document: Document, response: Response):
    try:
        vector.add_documents([document])

        return {
            "msg": "succeed",
        }
    except Exception as e:
        print("Error in storing document:", e)

        response.status_code = 500

        return {"msg": "Store document failed !"}


@app.get('/search')
def search(query: str):
    return vector.search(query=query)


class DeleteDocumentsRequest(BaseModel):
    ids: list[str]


@app.delete("/delete")
def delete(request: DeleteDocumentsRequest, response: Response):
    try:
        vector.delete_documents(request.ids)

        return {
            "msg": "succeed",
        }
    except Exception as e:
        print("Error in deleting document:", e)

        response.status_code = 500

        return {"msg": "Delete documents failed !"}


@app.put('/update/{id}')
def update(id: str, document: Document, response: Response):
    try:
        vector.update_document(id, document=document)

        return {
            "msg": "succeed",
        }
    except Exception as e:
        print("Error in updating document:", e)

        response.status_code = 500

        return {"msg": "Update documents failed !"}


@app.get('/')
def all(response: Response):
    try:
        return vector.get_all_documents()
    except Exception as e:
        print("Error in get all documents:", e)

        response.status_code = 500

        return {"msg": "Get all documents failed !"}
