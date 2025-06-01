import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Document, CrawledDomain
from api.crawl import router, CrawlRequest
from fastapi import FastAPI
from database.models import get_db
from unittest.mock import patch, MagicMock
import json
import asyncio
from rq import Queue
from redis import Redis
import uuid

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create test app
app = FastAPI()

# Override the get_db dependency
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
app.include_router(router)
client = TestClient(app)

@pytest.fixture(scope="function")
def db_session():
    # Create the database and tables
    Base.metadata.create_all(bind=engine)
    
    # Create a new session for the test
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after the test
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def mock_redis():
    with patch('api.crawl.Redis') as mock:
        yield mock

@pytest.fixture(scope="function")
def mock_queue(mock_redis):
    with patch('api.crawl.Queue') as mock:
        yield mock

@pytest.fixture(scope="function")
def mock_job():
    job = MagicMock()
    job.id = str(uuid.uuid4())
    job.meta = {}
    job.get_status.return_value = 'queued'
    job.is_finished = False
    job.is_failed = False
    return job

def test_crawl_url_success(mock_redis, mock_queue, mock_job):
    # Setup mock queue
    mock_queue.return_value.enqueue.return_value = mock_job
    
    # Test data
    test_url = "https://example.com"
    request_data = {
        "url": test_url,
        "recursive": True,
        "store_in_vector": True
    }
    
    # Make request
    response = client.post("/crawl", json=request_data)
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "لینک وارد شده برای خزش در صف قرار داده شد."
    assert data["url"] == f"{test_url}/"
    assert "job_id" in data
    
    # Verify queue was called correctly
    mock_queue.return_value.enqueue.assert_called_once()

def test_crawl_url_invalid_url():
    # Test with invalid URL
    request_data = {
        "url": "invalid-url",
        "recursive": False,
        "store_in_vector": False
    }
    
    response = client.post("/crawl", json=request_data)
    assert response.status_code == 422  # Validation error

def test_crawl_url_redis_error(mock_redis):
    # Simulate Redis connection error
    mock_redis.side_effect = Exception("Redis connection failed")
    
    request_data = {
        "url": "https://example.com",
        "recursive": False,
        "store_in_vector": False
    }
    
    response = client.post("/crawl", json=request_data)
    assert response.status_code == 500
    assert "خطا در خزش" in response.json()["detail"]["message"]

@pytest.mark.asyncio
async def test_websocket_job_status(mock_redis, mock_job):
    # Setup mock job
    mock_job.meta = {
        'progress': 'Processing...',
        'doc_ids': ['doc1', 'doc2']
    }
    mock_job.get_status.return_value = 'started'
    mock_job.is_finished = False
    mock_job.is_failed = False

    # Mock Job.fetch to return our mock job
    with patch('api.crawl.Job.fetch', return_value=mock_job) as mock_fetch:
        # Create WebSocket client
        with client.websocket_connect(f"/ws/jobs/{mock_job.id}") as websocket:
            # Receive doc_ids first (as per API implementation)
            data = websocket.receive_json()
            assert data["event"] == "docs_created"
            assert data["doc_ids"] == ['doc1', 'doc2']

@pytest.mark.asyncio
async def test_websocket_job_progress(mock_redis, mock_job):
    # Setup mock job with only progress (no doc_ids)
    mock_job.meta = {
        'progress': 'Processing...'
    }
    mock_job.get_status.return_value = 'started'
    mock_job.is_finished = False
    mock_job.is_failed = False

    # Mock Job.fetch to return our mock job
    with patch('api.crawl.Job.fetch', return_value=mock_job) as mock_fetch:
        # Create WebSocket client
        with client.websocket_connect(f"/ws/jobs/{mock_job.id}") as websocket:
            # Receive progress update
            data = websocket.receive_json()
            assert data["event"] == "change_progress"
            assert data["progress"] == "Processing..."
            assert data["status"] == "started"

@pytest.mark.asyncio
async def test_websocket_job_error(mock_redis, mock_job):
    # Setup mock job with error
    mock_job.meta = {'error': {'message': 'Test error'}}
    mock_job.is_failed = True
    mock_job.get_status.return_value = 'failed'
    mock_job.is_finished = False

    # Mock Job.fetch to return our mock job
    with patch('api.crawl.Job.fetch', return_value=mock_job) as mock_fetch:
        # Create WebSocket client
        with client.websocket_connect(f"/ws/jobs/{mock_job.id}") as websocket:
            # Should receive error status
            data = websocket.receive_json()
            assert data["event"] == "change_progress"
            assert data["status"] == "failed"

@pytest.mark.asyncio
async def test_websocket_job_not_found(mock_redis):
    # Mock Job.fetch to raise an exception
    with patch('api.crawl.Job.fetch', side_effect=Exception("Job not found")):
        # Create WebSocket client
        with client.websocket_connect("/ws/jobs/nonexistent-job") as websocket:
            # Should receive error status
            with pytest.raises(Exception):
                websocket.receive_json()

@pytest.mark.asyncio
async def test_websocket_disconnect(mock_redis, mock_job):
    # Setup mock job
    mock_job.meta = {'progress': 'Processing...'}
    mock_job.get_status.return_value = 'started'
    mock_job.is_finished = False
    mock_job.is_failed = False

    # Mock Job.fetch to return our mock job
    with patch('api.crawl.Job.fetch', return_value=mock_job):
        # Create WebSocket client
        with client.websocket_connect(f"/ws/jobs/{mock_job.id}") as websocket:
            # Close the connection immediately
            websocket.close()
            # The test should complete without errors

def test_crawl_task_success(db_session, mock_job):
    from api.crawl import crawl_task
    
    # Setup test data
    test_url = "https://example.com"
    test_doc = Document(
        id=1,
        title="Test Document",
        uri=test_url,
        html="<html>Test</html>",
        markdown="# Test"
    )
    db_session.add(test_doc)
    db_session.commit()
    
    # Mock both the crawl function and get_current_job
    with patch('api.crawl.crawl') as mock_crawl, \
         patch('rq.get_current_job', return_value=mock_job), \
         patch('api.crawl.get_db', return_value=db_session):
        mock_crawl.return_value = [1]  # Return document ID
        
        # Execute crawl task
        crawl_task(test_url, recursive=True, store_in_vector=True)
        
        # Verify job metadata was updated with the final progress message
        assert mock_job.meta['progress'] == "Finished"
        assert mock_job.meta['doc_ids'] == [1]
        
        # Verify that save_meta was called
        assert mock_job.save_meta.call_count >= 2  # At least two calls for progress updates

def test_crawl_task_error_handling(mock_job, db_session):
    from api.crawl import crawl_task
    
    # Mock both the crawl function and get_current_job
    with patch('api.crawl.crawl') as mock_crawl, \
         patch('rq.get_current_job', return_value=mock_job), \
         patch('api.crawl.get_db', return_value=db_session):
        mock_crawl.side_effect = Exception("Test error")
        
        # Execute crawl task and expect it to raise the exception
        with pytest.raises(Exception) as exc_info:
            crawl_task("https://example.com")
        
        # Verify the exception message
        assert str(exc_info.value) == "Test error"
        
        # Verify error was captured in job metadata
        assert 'error' in mock_job.meta
        assert str(mock_job.meta['error']['message']) == "Test error"
        assert mock_job.save_meta.call_count >= 1  # At least one call for error update

def test_crawl_task_no_job(db_session):
    from api.crawl import crawl_task
    
    # Mock get_current_job to return None and patch crawl to avoid actual crawling
    with patch('rq.get_current_job', return_value=None), \
         patch('api.crawl.crawl') as mock_crawl, \
         patch('api.crawl.get_db', return_value=db_session):
        # Execute crawl task - should not raise an exception
        crawl_task("https://example.com")
        # Verify crawl was called
        mock_crawl.assert_called_once()

def test_clean_domain():
    from api.crawl import clean_domain
    
    # Test cases
    test_cases = [
        ("https://www.example.com", "https://example.com"),
        ("http://example.com", "http://example.com"),
        ("https://sub.example.com", "https://sub.example.com"),
        ("https://www.example.com/path", "https://example.com/path"),
    ]
    
    for input_url, expected_url in test_cases:
        assert clean_domain(input_url) == expected_url 