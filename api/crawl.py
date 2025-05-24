from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from fastapi.responses import JSONResponse
from datetime import datetime
import logging
from crawler.crawler import crawl
from database.models import Document, CrawledDomain, get_db
from sqlalchemy.orm import Session
from urllib.parse import urlparse
from rq import Queue
from redis import Redis

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

@router.post("/crawl", response_model=CrawlResponse, tags=["Crawler"],
          summary="خزش یک URL",
          description="این اندپوینت یک URL را خزش کرده و محتوای آن را استخراج می‌کند")
async def crawl_url(request: CrawlRequest):
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
        # Add crawl task to queue
        redis_con = Redis(host="192.168.171.6")
        q = Queue(connection=redis_con)
        q.enqueue(crawl_task, request.url, request.recursive)

        # Prepare response
        response = CrawlResponse(
            message="لینک وارد شده برای خزش در صف قرار داده شد.",
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

def crawl_task(url: str, recursive: bool = False):
     # Start crawling and get document IDs
        doc_ids = crawl(str(url), recursive=recursive)

        db = get_db()

        print(doc_ids)
        
        # Get document details
        doc_details = []
        for doc_id in doc_ids:
            # Get document from database
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:

                # Extract domain from URI if no domain exists
                if not doc.domain:
                    parsed_uri = urlparse(doc.uri)
                    domain_name = parsed_uri.netloc
                    if not domain_name:  # If URI is relative
                        domain_name = urlparse(str(url)).netloc
                    
                    # Create new domain if it doesn't exist
                    domain = db.query(CrawledDomain).filter(CrawledDomain.domain == domain_name).first()
                    if not domain:
                        domain = CrawledDomain(domain=domain_name)
                        db.add(domain)
                        db.commit()
                        db.refresh(domain)
                    
                    # Update document with new domain
                    doc.domain_id = domain.id
                    db.commit()
                
                # Get domain for URL construction
                domain = doc.domain.domain if doc.domain else ''
                doc_details.append(DocumentInfo(
                    id=str(doc.id),
                    url=domain + doc.uri,
                    title=doc.title
                ))