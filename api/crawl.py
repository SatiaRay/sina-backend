from fastapi import APIRouter, HTTPException, Depends, Query,WebSocket, WebSocketDisconnect
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
import uuid
import asyncio
from rq.job import Job
import traceback
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Re-use the existing redis connection if it's defined globally or accessible
redis_con = Redis(host="192.168.171.6") # Ensure this is accessible

class CrawlRequest(BaseModel):
    url: HttpUrl
    recursive: bool = False

class DocumentInfo(BaseModel):
    id: str
    url: str
    title: str

class CrawlResponse(BaseModel):
    message: str
    url: str
    job_id: str

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
    start_time = datetime.now()

    try:
        # Add crawl task to queue
        redis_con = Redis(host=os.getenv('REDIS_HOST'))
        q = Queue(connection=redis_con)
        job_id = str(uuid.uuid4())
        q.enqueue(crawl_task, request.url, request.recursive, job_id = job_id)

        # Prepare response
        response = CrawlResponse(
            message="لینک وارد شده برای خزش در صف قرار داده شد.",
            url= str(request.url),
            job_id=job_id
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
    try:
        from database.models import SessionLocal
        from rq import get_current_job

        job = get_current_job()

        if job is None:
            # fallback or error handling
            pass

        # Update progress metadata
        job.meta['progress'] = f"Start crawling ..."
        job.save_meta()

        db = SessionLocal()

        # Start crawling and get document IDs
        doc_ids = crawl(str(url), recursive=recursive, db=db)

        # Update progress metadata
        job.meta['progress'] = f"Crawl done. Saving data ..."
        job.save_meta()

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

        job.meta['doc_ids'] = doc_ids
        
        job.meta['progress'] = f"Finished"
        job.save_meta()
    except Exception as e: # Added a general exception handler for debugging
        job.meta['error'] = {'message' : e}
        job.save_meta()

@router.websocket("/ws/jobs/{job_id}")
async def websocket_job_status(websocket: WebSocket, job_id: str):
    await websocket.accept()

    last_progress = None;

    try:
        # Use the existing redis_con
        redis_conn = Redis(host="192.168.171.6")
        while True:
            job = Job.fetch(job_id, connection=redis_conn)

            doc_ids = job.meta.get('doc_ids', None)
            if doc_ids:
                await websocket.send_json({'event': 'docs_created', 'doc_ids' : doc_ids})

            progress = job.meta.get('progress', 'Queued')            
            if progress is not last_progress:
                last_progress = progress
                await websocket.send_json({'event' : 'change_progress', "progress": progress, "status": job.get_status()})

            if job.is_finished or job.is_failed:
                break
            await asyncio.sleep(1)  # Poll every second
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e: # Added a general exception handler for debugging
        logger.error(f"Error in websocket for job {job_id}: {e}")
        traceback.print_exc()
        await websocket.close(code=1011) # Close with an error code