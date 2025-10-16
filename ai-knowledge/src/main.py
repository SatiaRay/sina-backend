from fastapi import FastAPI, Response
from openai import BaseModel
from models import Document
from vector_store import VectorStore

app = FastAPI()
vector = VectorStore()


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



