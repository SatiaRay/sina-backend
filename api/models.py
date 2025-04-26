from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class Chunk(BaseModel):
    text: str
    metadata: Dict[str, Any]

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
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
        json_schema_extra = {
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

class ChatRequest(BaseModel):
    """
    مدل درخواست برای چت با بات
    
    - message: پیام کاربر
    - conversation_id: شناسه مکالمه (اختیاری)
    """
    message: str
    conversation_id: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "ساتیا چیست؟",
                "conversation_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }

class AddKnowledgeRequest(BaseModel):
    """
    مدل درخواست برای افزودن دانش از یک URL
    
    - url: آدرس URL که باید خزش شود
    """
    url: HttpUrl
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.satia.co/blog"
            }
        }

class CurationStatus(BaseModel):
    """مدل وضعیت بررسی یک سند"""
    document_id: str
    status: str  # 'approved', 'rejected', 'pending'
    edited_text: Optional[str] = None
    reason: Optional[str] = None
    reviewer: Optional[str] = None
    review_date: Optional[datetime] = None

class CurationListRequest(BaseModel):
    """مدل درخواست لیست اسناد در انتظار بررسی"""
    offset: int = 0
    limit: int = 50
    status: Optional[str] = None  # Filter by status

class CurationStats(BaseModel):
    """مدل آمار بررسی اسناد"""
    total_documents: int
    approved: int
    rejected: int
    pending: int
    last_review_date: Optional[datetime] = None

class CrawledDocument(BaseModel):
    """مدل سند خزش شده"""
    document_id: str
    url: str
    title: str
    text: str
    metadata: Dict[str, Any]
    status: str = "pending"
    review_info: Optional[CurationStatus] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

class VectorSearchRequest(BaseModel):
    question: str
    limit: Optional[int] = 5 
    max_score: Optional[float] = 1.0

class StoreVectorRequest(BaseModel):
    """
    مدل درخواست برای ذخیره متن و متادیتا در پایگاه داده برداری
    
    - text: متن اصلی برای ذخیره
    - metadata: متادیتای مربوط به متن
    """
    text: str
    metadata: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "ساتیا یک پلتفرم مدیریت منابع سازمانی است که...",
                "metadata": {
                    "source": "دستی",
                    "title": "درباره ساتیا",
                    "author": "تیم ساتیا",
                    "date": "2024-04-26"
                }
            }
        }