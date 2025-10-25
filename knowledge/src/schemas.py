from pydantic import BaseModel

class BaseDocument(BaseModel):
    text: str
    title: str
    tag: str
    status: bool = True

class StoreDocumentRequest(BaseDocument):
    pass

class UpdateDocumentRequest(BaseDocument):
    pass