from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from fastapi.responses import JSONResponse
from datetime import datetime
import logging
from crawler.crawler import crawl
from database.models import Document, get_db
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class CrawlRequest(BaseModel):
    url: HttpUrl
    recursive: bool = False

class DocumentInfo(BaseModel):
    id: str
    url: str
    title: str

class CrawlResponse(BaseModel):
    message: str
    docs: List[DocumentInfo]

@router.post("/crawl", response_model=CrawlResponse, tags=["Crawler"],
          summary="خزش یک URL",
          description="این اندپوینت یک URL را خزش کرده و محتوای آن را استخراج می‌کند")
async def crawl_url(request: CrawlRequest, db: Session = Depends(get_db)):
    """
    خزش یک URL و استخراج محتوای آن
    
    - **url**: آدرس URL برای خزش
    - **recursive**: آیا خزش به صورت بازگشتی انجام شود (پیش‌فرض: False)
    
    **نمونه درخواست:**
    ```json
    {
      "url": "https://www.satia.co/about",
      "recursive": true
    }
    ```
    
    **نمونه خروجی:**
    ```json
    {
      "message": "خزش با موفقیت انجام شد",
      "docs": [
        {
          "id": "doc_123",
          "uri": "https://www.satia.co/about",
          "title": "درباره ما",
          "domain": "satia.co"
        }
      ]
    }
    ```
    """
    try:
        start_time = datetime.now()
        logger.info(f"Starting crawl for URL: {request.url} (recursive: {request.recursive})")
        
        # Start crawling
        doc_ids = crawl(str(request.url), recursive=request.recursive)
        
        # Get document details from database
        doc_details = []
        
        for doc_id in doc_ids:
            # Get document from database
            doc = db.query(Document).filter(Document.id == doc_id).first()
            domain=doc.domain.domain if doc.domain else ''
            if doc:
                doc_details.append(DocumentInfo(
                    id=str(doc.id),
                    url=domain + doc.uri,
                    title=doc.title
                ))
        
        # Prepare response
        response = CrawlResponse(
            message=f"خزش با موفقیت انجام شد (تعداد صفحات: {len(doc_details)})",
            docs=doc_details
        )
        
        return JSONResponse(
            content=response.dict(),
            media_type="application/json; charset=utf-8"
        )
        
    except Exception as e:
        logger.error(f"Error during crawl: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": f"خطا در خزش: {str(e)}",
                "start_time": start_time.isoformat() if 'start_time' in locals() else None,
                "end_time": datetime.now().isoformat()
            }
        )
