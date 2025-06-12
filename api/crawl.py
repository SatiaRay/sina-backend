from fastapi import APIRouter, HTTPException, Depends, Query,WebSocket, WebSocketDisconnect
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import logging
from crawler.crawler import crawl
from database.models import CrawlJobs, get_db
from sqlalchemy.orm import Session
from urllib.parse import urlparse, urlunparse
from rq import Queue
from redis import Redis
from rq.exceptions import NoSuchJobError
import uuid
import asyncio
from rq.job import Job
import traceback
import os
import re
import time
import json
from database.repository import DocumentRepository, CrawlJobsRepository
from database.models import SessionLocal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CrawlError(Exception):
    """Base exception class for crawl-related errors"""
    def __init__(self, message: str, error_type: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_type = error_type
        self.details = details or {}
        super().__init__(self.message)

class CrawlInitializationError(CrawlError):
    """Error during crawl initialization"""

class CrawlExecutionError(CrawlError):
    """Error during crawl execution"""

class VectorizationError(CrawlError):
    """Error during vectorization process"""

def handle_crawl_error(job: Job, error: Exception, error_type: str = "unknown"):
    """Handle crawl errors and update job metadata with error information"""
    error_details = {
        'error_type': error_type,
        'message': str(error),
        'traceback': traceback.format_exc(),
        'timestamp': datetime.now().isoformat()
    }
    
    # Update job metadata with error information
    job.meta['error'] = error_details
    job.meta['status'] = {
        'msg': f'Error: {error_type}',
        'progress': job.meta.get('progress', {}),
        'error': error_details
    }
    job.save_meta()
    
    # Log the error
    logger.error(f"Crawl error ({error_type}): {str(error)}")
    logger.error(traceback.format_exc())

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

class CrawlJobResponse(BaseModel):
    id: int
    job_id: str
    init_url: str
    recursive: bool
    save_in_vector: bool
    status: str
    started_at: datetime
    end_at: Optional[datetime] = None

class CrawlJobDetailResponse(CrawlJobResponse):
    logs: List[Dict[str, Any]]
    vectorization_batch: Optional[Dict[str, Any]] = None

class PaginatedCrawlJobsResponse(BaseModel):
    items: List[CrawlJobResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

@router.post("/crawl", response_model=CrawlResponse, tags=["Crawler"],
          summary="خزش یک URL",
          description="این اندپوینت یک URL را خزش کرده و محتوای آن را استخراج می‌کند")
async def crawl_url(request: CrawlRequest, db: Session = Depends(get_db)):
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
    crawl_job_repo = CrawlJobsRepository(db)

    try:
        # Add crawl task to queue
        redis_con = Redis(host=os.getenv('REDIS_HOST'))
        q = Queue('crawl', connection=redis_con, default_timeout=15000)  # 10 minutes timeout
        job_id = str(uuid.uuid4())
        
        # Initial status object
        initial_status = {
            'msg': 'Queued',
            'progress': {
                'total_urls': 0,
                'crawled_urls': 0,
                'exception_urls': 0,
                'progress_percent': 0
            }
        }
        
        # Create CrawlJob record without end_at
        crawl_job = crawl_job_repo.create({
            'job_id': job_id,
            'init_url': str(request.url),
            'recursive': request.recursive,
            'save_in_vector': request.store_in_vector,
            'status': initial_status['msg'],  # Store only the status message
            'logs': json.dumps([initial_status]),  # Store full status history
            'started_at': datetime.now(timezone.utc)
        })
        
        # Create RQ job with initial metadata
        job = q.enqueue(crawl_task, request.url, request.recursive, request.store_in_vector, job_id=job_id)
        job.meta = {
            'type': 'crawl',
            'url': str(request.url),
            'crawl_job_id': crawl_job.id,
            'status': initial_status
        }
        job.save_meta()

        # Prepare response
        response = CrawlResponse(
            message="لینک وارد شده برای خزش در صف قرار داده شد.",
            url=str(request.url),
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
    finally:
        db.close()

def initialize_job_metadata(job):
    """Initialize the job metadata with initial progress information"""
    try:
        status_obj = {
            'msg': 'running crawl',
            'progress': {
                'total_urls': 0,
                'crawled_urls': 0,
                'exception_urls': 0,
                'progress_percent': 0
            }
        }
        job.meta['status'] = status_obj
        job.save_meta()
    except Exception as e:
        raise CrawlInitializationError(
            f"Failed to initialize job metadata: {str(e)}",
            "initialization_error",
            {'original_error': str(e)}
        )
    
def create_vectorization_batch(doc_ids, redis_con, db: Session = Depends(get_db)):
    """Create a batch of vectorization jobs for the given document IDs"""
    try:
        # Create database session and repository
        document_repo = DocumentRepository(db)

        # Create RQ queue
        q = Queue('vectorize', connection=redis_con)
        batch_id = str(uuid.uuid4())

        # Initialize batch progress
        batch_progress = {
            'total_docs': len(doc_ids),
            'done': 0,
            'remaining': len(doc_ids),
            'exceptions': 0,
            'progress_percent': 0
        }

        # Create vectorization jobs for each document
        vector_jobs = []
        for doc_id in doc_ids:
            # Get document from database
            document = document_repo.get(doc_id)
            if not document:
                continue

            # Prepare metadata
            metadata = {
                "document_id": str(doc_id),
                "title": document.title,
                "uri": document.uri or "",
                "domain_id": str(document.domain_id) if document.domain_id else "0",
                "created_at": datetime.now(timezone.utc).isoformat()
            }

            # Enqueue job
            vector_job = q.enqueue(
                'api.document.vectorize_task',
                doc_id,
                document.html,
                metadata,
                job_id=str(uuid.uuid4()),
            )
            vector_jobs.append(vector_job.id)

        return {
            'batch_id': batch_id,
            'job_ids': vector_jobs,
            'progress': batch_progress
        }

    except Exception as e:
        raise VectorizationError(
            f"Failed to create vectorization batch: {str(e)}",
            "batch_creation_error",
            {'doc_ids': doc_ids, 'original_error': str(e)}
        )

def update_batch_progress(vector_jobs, redis_con):
    """Calculate and return the current progress of the vectorization batch"""
    try:
        done = 0
        exceptions = 0
        missing = 0
        
        for job_id in vector_jobs:
            try:
                vector_job = Job.fetch(job_id, connection=redis_con)
                if vector_job.is_finished:
                    done += 1
                elif vector_job.is_failed:
                    exceptions += 1
            except NoSuchJobError:
                logger.warning(f"Vectorization job {job_id} not found in Redis")
                missing += 1
                continue
        
        remaining = len(vector_jobs) - done - exceptions - missing
        progress_percent = ((done + missing) / len(vector_jobs) * 100) if vector_jobs else 0
        
        return {
            'total_docs': len(vector_jobs),
            'done': done,
            'remaining': remaining,
            'exceptions': exceptions,
            'missing': missing,
            'progress_percent': round(progress_percent, 2)
        }
    except Exception as e:
        raise VectorizationError(
            f"Failed to update batch progress: {str(e)}",
            "progress_update_error",
            {'vector_jobs': vector_jobs, 'original_error': str(e)}
        )

def monitor_vectorization_batch(job, vector_jobs, redis_con):
    """Monitor the progress of vectorization jobs and update job metadata"""
    try:
        # Initialize vectorization batch info if not present
        if 'vectorization_batch' not in job.meta:
            job.meta['vectorization_batch'] = {
                'batch_id': str(uuid.uuid4()),
                'job_ids': vector_jobs,
                'progress': {
                    'total_docs': len(vector_jobs),
                    'done': 0,
                    'remaining': len(vector_jobs),
                    'exceptions': 0,
                    'progress_percent': 0
                }
            }
            job.save_meta()

        while True:
            # Update batch progress
            batch_progress = update_batch_progress(vector_jobs, redis_con)
            
            # Update parent job metadata
            job.meta['vectorization_batch']['progress'] = batch_progress
            job.save_meta()
            
            # Check if all jobs are complete (either done or failed)
            if batch_progress['done'] + batch_progress['exceptions'] == len(vector_jobs):
                logger.info(f"All vectorization jobs completed. Done: {batch_progress['done']}, Exceptions: {batch_progress['exceptions']}")
                break
                
            time.sleep(1)  # Wait before next check
            
    except Exception as e:
        logger.error(f"Error monitoring vectorization batch: {str(e)}")
        raise

def update_job_status(job, status_msg, include_batch=False):
    """Update the job status with the given message and optional batch information"""
    try:
        status_obj = {
            'msg': status_msg,
            'progress': job.meta.get('progress', {})
        }
        
        if include_batch:
            status_obj['vectorization_batch'] = job.meta.get('vectorization_batch', {})
        
        job.meta['status'] = status_obj
        job.save_meta()

        # Update status in CrawlJobs table
        crawl_job_id = job.meta.get('crawl_job_id')
        if crawl_job_id:
            db = SessionLocal()
            try:
                update_crawl_job_status(crawl_job_id, status_obj, db)
            finally:
                db.close()

        time.sleep(1)
    except Exception as e:
        raise CrawlError(
            f"Failed to update job status: {str(e)}",
            "status_update_error",
            {'status_msg': status_msg, 'include_batch': include_batch, 'original_error': str(e)}
        )

def update_crawl_job_status(crawl_job_id: int, status_obj: dict, db: Session):
    """Update the CrawlJob record with new status and append to logs"""
    try:
        crawl_job_repo = CrawlJobsRepository(db)
        crawl_job = crawl_job_repo.get(crawl_job_id)
        if crawl_job:
            # Get current logs or initialize empty list
            current_logs = crawl_job.logs or []
            if isinstance(current_logs, str):
                try:
                    current_logs = json.loads(current_logs)
                except:
                    current_logs = []
            
            # Add timestamp to status object
            status_obj['timestamp'] = datetime.now(timezone.utc).isoformat()
            
            # Append new status to logs
            current_logs.append(status_obj)
            
            # Prepare update data
            update_data = {
                'status': status_obj['msg'],  # Store only the status message
                'logs': json.dumps(current_logs)  # Store full status history
            }
            
            # Set end_at only if status is 'Finished'
            if status_obj['msg'] == 'Finished':
                update_data['end_at'] = datetime.now(timezone.utc)
            
            # Update the record
            crawl_job_repo.update(crawl_job.id, update_data)
    except Exception as e:
        logger.error(f"Error updating CrawlJob status: {str(e)}")

def crawl_task(url: str, recursive: bool = False, store_in_vector: bool = False):
    """Main crawl task that orchestrates the crawling and vectorization process"""
    job = None
    db = None
    
    try:
        from database.models import SessionLocal
        from rq import get_current_job

        job = get_current_job()
        db = SessionLocal()
        crawl_job_id = job.meta.get('crawl_job_id') if job else None

        try:
            # Initialize job metadata if job exists
            if job:
                initialize_job_metadata(job)
                if crawl_job_id:
                    update_crawl_job_status(crawl_job_id, job.meta['status'], db)
            
            # Start crawling and get document IDs
            doc_ids = crawl(str(url), recursive=recursive, db=db, job=job)
            
            if store_in_vector and doc_ids:
                # Update status to saving data if job exists
                if job:
                    update_job_status(job, 'saving data')
                    if crawl_job_id:
                        update_crawl_job_status(crawl_job_id, job.meta['status'], db)
                
                # Create batch of vectorization jobs
                redis_con = Redis(host=os.getenv('REDIS_HOST'))
                batch_info = create_vectorization_batch(doc_ids, redis_con, db=db)
                
                # Update parent job with batch information if job exists
                if job:
                    job.meta['vectorization_batch'] = batch_info
                    job.save_meta()
                    if crawl_job_id:
                        update_crawl_job_status(crawl_job_id, job.meta['status'], db)
                
                # Monitor batch progress
                monitor_vectorization_batch(job, batch_info['job_ids'], redis_con)
                
                # Update final status if job exists
                if job:
                    update_job_status(job, 'Finished', include_batch=True)
                    if crawl_job_id:
                        update_crawl_job_status(crawl_job_id, job.meta['status'], db)
            else:
                if job:
                    update_job_status(job, 'Finished', include_batch=False)
                    if crawl_job_id:
                        update_crawl_job_status(crawl_job_id, job.meta['status'], db)

        except CrawlError as e:
            if job:
                handle_crawl_error(job, e, e.error_type)
                if crawl_job_id:
                    update_crawl_job_status(crawl_job_id, job.meta['status'], db)
            raise
        except Exception as e:
            if job:
                handle_crawl_error(job, e, "unexpected_error")
                if crawl_job_id:
                    update_crawl_job_status(crawl_job_id, job.meta['status'], db)
            raise

    except Exception as e:
        if job:
            handle_crawl_error(job, e, "fatal_error")
            if crawl_job_id:
                update_crawl_job_status(crawl_job_id, job.meta['status'], db)
        raise
    finally:
        if db:
            db.close()

@router.websocket("/ws/jobs/{job_id}")
async def websocket_job_status(websocket: WebSocket, job_id: str):
    await websocket.accept()

    last_progress = None

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

@router.get("/crawl/jobs", response_model=PaginatedCrawlJobsResponse, tags=["Crawler"],
          summary="لیست کارهای خزش",
          description="دریافت لیست کارهای خزش با امکان صفحه‌بندی و فیلتر")
async def get_crawl_jobs(
    page: int = Query(1, ge=1, description="شماره صفحه"),
    page_size: int = Query(10, ge=1, le=100, description="تعداد آیتم در هر صفحه"),
    status: Optional[str] = Query(None, description="فیلتر بر اساس وضعیت"),
    domain: Optional[str] = Query(None, description="فیلتر بر اساس دامنه"),
    active: bool = Query(False, description="فقط کارهای ناتمام"),
    recursive: Optional[bool] = Query(None, description="فیلتر بر اساس خزش بازگشتی"),
    save_in_vector: Optional[bool] = Query(None, description="فیلتر بر اساس ذخیره برداری"),
    db: Session = Depends(get_db)
):
    """
    دریافت لیست کارهای خزش با امکان صفحه‌بندی و فیلتر
    
    - **page**: شماره صفحه (شروع از 1)
    - **page_size**: تعداد آیتم در هر صفحه (بین 1 تا 100)
    - **status**: فیلتر بر اساس وضعیت (اختیاری)
    - **domain**: فیلتر بر اساس دامنه (اختیاری)
    - **active**: فقط کارهای ناتمام را نمایش دهد
    - **recursive**: فیلتر بر اساس خزش بازگشتی (اختیاری)
    - **save_in_vector**: فیلتر بر اساس ذخیره برداری (اختیاری)
    """
    try:
        crawl_job_repo = CrawlJobsRepository(db)
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Build query
        query = db.query(CrawlJobs)
        
        # Apply filters
        if status:
            query = query.filter(CrawlJobs.status == status)
        if domain:
            query = query.filter(CrawlJobs.init_url.like(f"%{domain}%"))
        if active:
            query = query.filter(CrawlJobs.end_at.is_(None))
        else:
            query = query.filter(CrawlJobs.end_at.is_not(None))
        if recursive is not None:
            query = query.filter(CrawlJobs.recursive == recursive)
        if save_in_vector is not None:
            query = query.filter(CrawlJobs.save_in_vector == save_in_vector)
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        jobs = query.order_by(CrawlJobs.started_at.desc())\
                   .offset(offset)\
                   .limit(page_size)\
                   .all()
        
        # Calculate total pages
        total_pages = (total + page_size - 1) // page_size
        
        # Prepare response
        response = PaginatedCrawlJobsResponse(
            items=[
                CrawlJobResponse(
                    id=job.id,
                    job_id=job.job_id,
                    init_url=job.init_url,
                    recursive=job.recursive,
                    save_in_vector=job.save_in_vector,
                    status=job.status,
                    started_at=job.started_at,
                    end_at=job.end_at
                ) for job in jobs
            ],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error fetching crawl jobs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": f"خطا در دریافت لیست کارهای خزش: {str(e)}"
            }
        )

@router.get("/crawl/jobs/{job_id}", response_model=CrawlJobDetailResponse, tags=["Crawler"],
          summary="اطلاعات کامل یک کار خزش",
          description="دریافت اطلاعات کامل یک کار خزش شامل لاگ‌ها و وضعیت برداری‌سازی")
async def get_crawl_job_detail(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    دریافت اطلاعات کامل یک کار خزش
    
    - **job_id**: شناسه یکتای کار خزش
    
    **نمونه خروجی:**
    ```json
    {
      "id": 1,
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "init_url": "https://example.com",
      "recursive": true,
      "save_in_vector": true,
      "status": "Finished",
      "started_at": "2024-03-20T10:00:00",
      "end_at": "2024-03-20T10:05:00",
      "logs": [
        {
          "msg": "Queued",
          "progress": {
            "total_urls": 0,
            "crawled_urls": 0,
            "exception_urls": 0,
            "progress_percent": 0
          },
          "timestamp": "2024-03-20T10:00:00"
        }
      ],
      "vectorization_batch": {
        "batch_id": "batch_123",
        "job_ids": ["job_1", "job_2"],
        "progress": {
          "total_docs": 2,
          "done": 1,
          "remaining": 1,
          "exceptions": 0,
          "progress_percent": 50
        }
      }
    }
    ```
    """
    try:
        crawl_job_repo = CrawlJobsRepository(db)
        crawl_job = crawl_job_repo.get_by_job_id(job_id)
        
        if not crawl_job:
            raise HTTPException(
                status_code=404,
                detail={
                    "status": "error",
                    "message": f"کار خزش با شناسه {job_id} یافت نشد"
                }
            )
        
        # Parse logs from JSON string
        logs = []
        if crawl_job.logs:
            try:
                logs = json.loads(crawl_job.logs)
            except json.JSONDecodeError:
                logs = []
        
        # Get vectorization batch info if available
        vectorization_batch = None
        if crawl_job.save_in_vector:
            try:
                redis_conn = Redis(host=os.getenv('REDIS_HOST'))
                job = Job.fetch(job_id, connection=redis_conn)
                if job and job.meta:
                    vectorization_batch = job.meta.get('vectorization_batch')
            except Exception as e:
                logger.error(f"Error fetching vectorization batch: {str(e)}")
        
        return CrawlJobDetailResponse(
            id=crawl_job.id,
            job_id=crawl_job.job_id,
            init_url=crawl_job.init_url,
            recursive=crawl_job.recursive,
            save_in_vector=crawl_job.save_in_vector,
            status=crawl_job.status,
            started_at=crawl_job.started_at,
            end_at=crawl_job.end_at,
            logs=logs,
            vectorization_batch=vectorization_batch
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching crawl job detail: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": f"خطا در دریافت اطلاعات کار خزش: {str(e)}"
            }
        )