from pydantic import BaseModel

class BaseDocument(BaseModel):
    title: str
    text: str
    metadata: dict

class StoreDocumentRequest(BaseDocument):
    pass

class UpdateDocumentRequest(BaseDocument):
    pass