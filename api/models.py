from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime

class Chunk(BaseModel):
    text: str
    metadata: Dict[str, Any]

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        },
        schema_extra = {
            "example": {
                "text": "ساتیا یک پلتفرم مدیریت منابع سازمانی است که...",
                "metadata": {
                    "source": "https://www.satia.co/about",
                    "title": "درباره ساتیا"
                }
            }
        }

class DataSource(BaseModel):
    url: str
    imported_by: str
    import_date: datetime
    status: str
    refresh_status: str = "هرگز"
    chunks: List[Chunk]

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class DataSourceListResponse(BaseModel):
    sources: List[DataSource]
    total: int

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class QuestionRequest(BaseModel):
    question: str

class EditChunkRequest(BaseModel):
    url: str
    chunk_index: int
    new_text: str

class AllKnowledgeRequest(BaseModel):
    url: str

class UpdateKnowledgeRequest(BaseModel):
    """
    مدل درخواست برای به‌روزرسانی و خزش مجدد یک URL
    
    - url: آدرس URL که باید مجدداً خزش شود
    """
    url: str
    
    class Config:
        schema_extra = {
            "example": {
                "url": "https://www.satia.co/blog"
            }
        }

class PlainTextRequest(BaseModel):
    """
    مدل درخواست برای اضافه کردن متن ساده به پایگاه دانش
    
    - text: متن اصلی (اجباری)
    - title: عنوان (اختیاری)
    - source: منبع متن (اختیاری)
    """
    text: str
    title: Optional[str] = None
    source: Optional[str] = None 