from pydantic import BaseModel

class DocumentMetadata(BaseModel):
    title: str
    tag: str
    status: bool = True

class BaseDocument(BaseModel):
    text: str
    metadata: DocumentMetadata

class StoreDocumentRequest(BaseDocument):
    pass

class UpdateDocumentRequest(BaseDocument):
    pass