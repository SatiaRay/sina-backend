from fastapi import APIRouter, HTTPException, Depends, Query,WebSocket, WebSocketDisconnect
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from fastapi.responses import JSONResponse
from datetime import datetime
import logging
from crawler.crawler import crawl
from database.models import Document, CrawledDomain, get_db
from sqlalchemy.orm import Session
from urllib.parse import urlparse, urlunparse
from rq import Queue
from redis import Redis
import uuid
import asyncio
from rq.job import Job
import traceback
import os
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_domain(url: str) -> str:
    """
    Clean domain name by removing www. and ensuring proper URL structure
    
    Args:
        url: The URL to clean
        
    Returns:
        Cleaned URL with proper domain structure
    """
    try:
        # Parse the URL
        parsed = urlparse(url)
        
        # Remove www. from netloc using regex
        netloc = re.sub(r'^www\.', '', parsed.netloc)
        
        # Reconstruct the URL with cleaned netloc
        cleaned = urlunparse((
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        
        return cleaned
    except Exception as e:
        logger.error(f"Error cleaning domain: {str(e)}")
        # Return original URL if cleaning fails
        return url if isinstance(url, str) else str(url)

router = APIRouter()

# Re-use the existing redis connection if it's defined globally or accessible
redis_con = Redis(host="192.168.171.6") # Ensure this is accessible

class CrawlRequest(BaseModel):
    url: HttpUrl
    recursive: bool = False
    store_in_vector: bool = False

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
    - **store_in_vector**: آیا محتوا در پایگاه داده برداری ذخیره شود (پیش‌فرض: False)
    
    **نمونه درخواست:**
    ```json
    {
      "url": "https://www.satia.co/about",
      "recursive": true,
      "store_in_vector": true
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
        q.enqueue(crawl_task, request.url, request.recursive, request.store_in_vector, job_id = job_id)

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

def crawl_task(url: str, recursive: bool = False, store_in_vector: bool = False):
    try:
        from database.models import SessionLocal
        from rq import get_current_job

        job = get_current_job()
        db = get_db()

        try:
            # Start crawling and get document IDs
            doc_ids = crawl(str(url), recursive=recursive, store_in_vector=store_in_vector, db=db)

            if job is not None:
                # Update progress metadata
                job.meta['progress'] = f"Crawl done. Saving data ..."
                job.save_meta()

                # Get document details
                doc_details = []
                for doc_id in doc_ids:
                    # Get document from database
                    doc = db.query(Document).filter(Document.id == doc_id).first()
                    if doc:
                        try:
                            # Clean the URI
                            cleaned_uri = clean_domain(doc.uri)
                            if not cleaned_uri:
                                cleaned_uri = str(doc.uri)  # Fallback to original URI
                            doc.uri = cleaned_uri

                            # Extract domain from cleaned URI if no domain exists
                            if not doc.domain:
                                parsed_uri = urlparse(cleaned_uri)
                                domain_name = parsed_uri.netloc
                                if not domain_name:  # If URI is relative
                                    domain_name = urlparse(str(url)).netloc
                                    domain_name = re.sub(r'^www\.', '', domain_name)

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
                                url=cleaned_uri,
                                title=doc.title or "Untitled"  # Provide default title if None
                            ))
                        except Exception as e:
                            logger.error(f"Error processing document {doc.id}: {str(e)}")
                            continue

                job.meta['doc_ids'] = doc_ids
                job.meta['progress'] = f"Finished"
                job.save_meta()

        except Exception as e:
            if job is not None:
                job.meta['error'] = {'message': str(e)}
                job.save_meta()
            raise e
        finally:
            db.close()

    except Exception as e:
        if job is not None:
            job.meta['error'] = {'message': str(e)}
            job.save_meta()
        raise e

@router.websocket("/ws/jobs/{job_id}")
async def websocket_job_status(websocket: WebSocket, job_id: str):
    await websocket.accept()

    last_progress = None;

    try:
        # Use the existing redis_con
        redis_conn = Redis(host=os.getenv('REDIS_HOST'))
        while True:
            job = Job.fetch(job_id, connection=redis_conn)

            doc_ids = job.meta.get('doc_ids', None)
            if doc_ids:
                await websocket.send_json({'event': 'docs_created', 'doc_ids' : doc_ids})
                break

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