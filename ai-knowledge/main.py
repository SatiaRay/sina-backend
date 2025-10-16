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
            "msg" : "succeed",
        }
    except Exception as e:
        print("Error in storing document:", e)

        response.status_code = 500
        
        return {"msg" : "Store document failed !"}


