from pydantic import BaseModel

class DocumentMetadata(BaseModel):
    title: str
    tag: str

class BaseDocument(BaseModel):
    text: str
    metadata: DocumentMetadata
    status: bool = True

class StoreDocumentRequest(BaseDocument):
    pass

class UpdateDocumentRequest(BaseDocument):
    pass