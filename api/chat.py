from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database.models import Chat, ChatHistory, get_db
from datetime import datetime

router = APIRouter()

class ChatHistoryResponse(BaseModel):
    id: int
    chat_id: int
    role: str
    body: str
    created_at: datetime

@router.get("/chat/history/{session_id}", response_model=List[ChatHistoryResponse], tags=["Chat"],
          summary="دریافت تاریخچه چت",
          description="این اندپوینت تاریخچه چت را بر اساس شناسه جلسه برمی‌گرداند")
async def get_chat_history(
    session_id: str,
    limit: Optional[int] = Query(default=20, ge=1, le=100),
    offset: Optional[int] = Query(default=0, ge=0),
    db: Session = Depends(get_db)
):
    """
    دریافت تاریخچه چت بر اساس شناسه جلسه
    
    - **session_id**: شناسه جلسه چت
    - **limit**: تعداد پیام‌های مورد نظر (پیش‌فرض: 20)
    - **offset**: تعداد پیام‌های رد شده (پیش‌فرض: 0)
    
    **نمونه خروجی:**
    ```json
    [
      {
        "id": 1,
        "chat_id": 123,
        "role": "user",
        "body": "سلام",
        "created_at": "2024-03-20T10:30:00"
      },
      {
        "id": 2,
        "chat_id": 123,
        "role": "assistant",
        "body": "سلام! چطور می‌توانم کمک کنم؟",
        "created_at": "2024-03-20T10:30:05"
      }
    ]
    ```
    """
    try:
        # First find the chat by session_id
        chat = db.query(Chat).filter(Chat.session_id == session_id).first()
        
        if not chat:
            return []
        
        # Then get the chat history for this chat with offset
        history = db.query(ChatHistory)\
            .filter(ChatHistory.chat_id == chat.id)\
            .order_by(ChatHistory.created_at.desc())\
            .offset(int(offset))\
            .limit(int(limit))\
            .all()
        
        if not history:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "تاریخچه چت یافت نشد",
                    "session_id": session_id,
                    "chat_id": chat.id,
                    "offset": offset
                }
            )
        
        # Convert to response model
        return [
            ChatHistoryResponse(
                id=msg.id,
                chat_id=msg.chat_id,
                role=msg.role,
                body=msg.body,
                created_at=msg.created_at
            )
            for msg in history
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "خطا در دریافت تاریخچه چت",
                "error": str(e)
            }
        )
