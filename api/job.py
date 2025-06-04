from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis import Redis
from rq.job import Job
from rq import Queue
import asyncio
import logging
import os
import traceback
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])

class QueueJobsResponse(BaseModel):
    queue_name: str
    jobs: List[Dict[str, Any]]

class JobStatusTracker:
    """Class to handle job status tracking and WebSocket communication"""
    
    def __init__(self, websocket: WebSocket, job_id: str):
        self.websocket = websocket
        self.job_id = job_id
        self.redis_conn = Redis(host=os.getenv('REDIS_HOST'))
        self.last_progress = None
        self.last_status = None
        self.last_error = None
    
    async def connect(self):
        """Establish WebSocket connection"""
        await self.websocket.accept()
        logger.info(f"WebSocket connection established for job {self.job_id}")
    
    async def disconnect(self):
        """Close WebSocket connection"""
        await self.websocket.close()
        logger.info(f"WebSocket connection closed for job {self.job_id}")
    
    def get_job(self) -> Optional[Job]:
        """Fetch job from Redis"""
        try:
            return Job.fetch(self.job_id, connection=self.redis_conn)
        except Exception as e:
            logger.error(f"Error fetching job {self.job_id}: {str(e)}")
            return None
    
    def format_progress_message(self, job: Job) -> Dict[str, Any]:
        """Format progress message for WebSocket"""
        message = {
            'event': 'progress_update',
            'job_id': self.job_id,
            'status': job.get_status(),
            'timestamp': datetime.now().isoformat()
        }
        
        # Add progress information if available
        if 'progress' in job.meta:
            message['progress'] = job.meta['progress']
        
        # Add status information if available
        if 'status' in job.meta:
            message['status_info'] = job.meta['status']
        
        # Add error information if available
        if 'error' in job.meta:
            message['error'] = job.meta['error']
        
        # Add vectorization batch information if available
        if 'vectorization_batch' in job.meta:
            message['vectorization_batch'] = job.meta['vectorization_batch']
        
        return message
    
    def should_send_update(self, job: Job) -> bool:
        """Determine if an update should be sent based on changes"""
        current_progress = job.meta.get('progress')
        current_status = job.meta.get('status')
        current_error = job.meta.get('error')
        
        # Check if any relevant data has changed
        if (current_progress != self.last_progress or
            current_status != self.last_status or
            current_error != self.last_error):
            
            self.last_progress = current_progress
            self.last_status = current_status
            self.last_error = current_error
            return True
        
        return False
    
    async def send_update(self, message: Dict[str, Any]):
        """Send update through WebSocket"""
        try:
            await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {str(e)}")
            raise
    
    async def track_job(self):
        """Main method to track job progress"""
        try:
            while True:
                job = self.get_job()
                if not job:
                    await self.send_update({
                        'event': 'error',
                        'message': f'Job {self.job_id} not found'
                    })
                    break
                
                # Check if job is finished or failed
                if job.is_finished:
                    await self.send_update({
                        'event': 'finished',
                        'message': 'Job completed successfully',
                        'data': self.format_progress_message(job)
                    })
                    break
                elif job.is_failed:
                    await self.send_update({
                        'event': 'failed',
                        'message': 'Job failed',
                        'data': self.format_progress_message(job)
                    })
                    break
                
                # Send update if there are changes
                if self.should_send_update(job):
                    await self.send_update(self.format_progress_message(job))
                
                await asyncio.sleep(1)  # Poll every second
                
        except WebSocketDisconnect:
            logger.info(f"Client disconnected for job {self.job_id}")
        except Exception as e:
            logger.error(f"Error tracking job {self.job_id}: {str(e)}")
            traceback.print_exc()
            try:
                await self.send_update({
                    'event': 'error',
                    'message': f'Error tracking job: {str(e)}'
                })
            except:
                pass

@router.websocket("/ws/{job_id}")
async def websocket_job_status(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for tracking job status"""
    tracker = JobStatusTracker(websocket, job_id)
    
    try:
        await tracker.connect()
        await tracker.track_job()
    except Exception as e:
        logger.error(f"Error in websocket_job_status: {str(e)}")
        traceback.print_exc()
    finally:
        await tracker.disconnect()

@router.get("/queues", response_model=List[QueueJobsResponse])
async def get_queue_jobs():
    """Get all in-process jobs separated by queue names"""
    try:
        redis_conn = Redis(host=os.getenv('REDIS_HOST'))
        queues = Queue.all(connection=redis_conn)
        result = []
        
        for queue in queues:
            jobs = []
            # Get started jobs (in-process)
            started_jobs = queue.started_job_registry.get_job_ids()
            
            for job_id in started_jobs:
                job = Job.fetch(job_id, connection=redis_conn)
                if job:
                    job_data = {
                        'id': job.id,
                        'status': job.get_status(),
                        'created_at': job.created_at.isoformat() if job.created_at else None,
                        'started_at': job.started_at.isoformat() if job.started_at else None,
                        'meta': job.meta
                    }
                    jobs.append(job_data)
            
            if jobs:  # Only include queues that have jobs
                result.append(QueueJobsResponse(
                    queue_name=queue.name,
                    jobs=jobs
                ))
        
        return result
    except Exception as e:
        logger.error(f"Error getting queue jobs: {str(e)}")
        traceback.print_exc()
        raise
