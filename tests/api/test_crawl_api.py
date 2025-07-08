import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Document
from api.crawl import router
from fastapi import FastAPI
from database.models import get_db
from unittest.mock import patch, MagicMock, ANY
import uuid
import time
from unittest.mock import AsyncMock
from sqlalchemy.orm import Session
from redis import Redis

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


from api.main import app

# Override the get_db dependency
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def _override_db():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)

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

# Add fixture for authenticated customer user and token
@pytest.fixture(scope="function")
def auth_user(db_session):
    email = f"customer_{uuid.uuid4()}@example.com"
    password = "securepassword123"
    # Register
    register_resp = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "user_type": "customer"
        }
    )
    assert register_resp.status_code == 201
    # Login
    login_resp = client.post(
        "/auth/login",
        json={"email": email, "password": password}
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    # Fetch user from DB to ensure it's persisted
    from database.models import User

    user = db_session.query(User).filter(User.email == email).first()
    db_session.close()

    auth_headers = {"Authorization": f"Bearer {token}"}
    return auth_headers, user

def test_crawl_url_success(mock_redis, mock_queue, mock_job, db_session, auth_user):
    # Setup mock queue
    
    auth_headers, user = auth_user
    
    mock_queue.return_value.enqueue.return_value = mock_job
    
    # Test data
    test_url = "https://example.com"
    request_data = {
        "url": test_url,
        "recursive": True,
        "store_in_vector": True
    }
    
    # Make request
    response = client.post("/crawl", json=request_data, headers=auth_headers)
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "لینک وارد شده برای خزش در صف قرار داده شد."
    assert data["url"] == f"{test_url}/"
    assert "job_id" in data
    
    # Verify queue was called correctly
    mock_queue.return_value.enqueue.assert_called_once()

def test_crawl_url_invalid_url(auth_user):
    # Test with invalid URL
    auth_headers, user = auth_user
    
    request_data = {
        "url": "invalid-url",
        "recursive": False,
        "store_in_vector": False
    }
    
    response = client.post("/crawl", json=request_data, headers=auth_headers)
    assert response.status_code == 422  # Validation error

def test_crawl_url_redis_error(mock_redis, auth_user):
    # Simulate Redis connection error
    auth_headers, user = auth_user
    
    mock_redis.side_effect = Exception("Redis connection failed")
    
    request_data = {
        "url": "https://example.com",
        "recursive": False,
        "store_in_vector": False
    }
    
    response = client.post("/crawl", json=request_data, headers=auth_headers)
    assert response.status_code == 500
    assert "خطا در خزش" in response.json()["detail"]["message"]


def test_crawl_task_success(db_session, mock_job, auth_user):
    from api.crawl import crawl_task
    
    auth_headers, user = auth_user
    
    # Setup test data
    test_url = "https://example.com"
    test_doc = Document(
        id=1,
        title="Test Document",
        uri=test_url,
        html="<html>Test</html>",
        markdown="# Test",
        workspace_id=user.current_workspace_id
    )
    db_session.add(test_doc)
    db_session.commit()
    
    # Mock both the crawl function and get_current_job
    with patch('api.crawl.crawl') as mock_crawl, \
         patch('rq.get_current_job', return_value=mock_job), \
         patch('api.crawl.get_db', return_value=db_session), \
         patch('api.crawl.create_vectorization_batch') as mock_create_batch, \
         patch('api.crawl.monitor_vectorization_batch') as mock_monitor:
        
        mock_crawl.return_value = [1]  # Return document ID
        mock_create_batch.return_value = {
            'batch_id': 'test_batch',
            'job_ids': ['job1'],
            'progress': {
                'total_docs': 1,
                'done': 0,
                'remaining': 1,
                'exceptions': 0,
                'progress_percent': 0
            }
        }
        
        # Execute crawl task
        crawl_task(test_url, recursive=True, store_in_vector=True, user=user)
        
        # Verify job metadata was updated with the final progress message
        assert mock_job.meta['status']['msg'] == "Finished"
        
        # Verify vectorization was triggered
        mock_create_batch.assert_called_once()

        args, kwargs = mock_create_batch.call_args

        assert args[0] == [1]
        assert isinstance(args[1], Redis)
        assert isinstance(kwargs['db'], Session)
        
        mock_monitor.assert_called_once()
        
        # Verify that save_meta was called
        assert mock_job.save_meta.call_count >= 2  # At least two calls for progress updates

def test_crawl_task_error_handling(mock_job, db_session, auth_user):
    from api.crawl import crawl_task
    
    auth_headers, user = auth_user
    
    # Mock both the crawl function and get_current_job
    with patch('api.crawl.crawl') as mock_crawl, \
         patch('rq.get_current_job', return_value=mock_job), \
         patch('api.crawl.get_db', return_value=db_session):
        mock_crawl.side_effect = Exception("Test error")
        
        # Execute crawl task and expect it to raise the exception
        with pytest.raises(Exception) as exc_info:
            crawl_task("https://example.com", user=user)
        
        # Verify the exception message
        assert str(exc_info.value) == "Test error"
        
        # Verify error was captured in job metadata
        assert 'error' in mock_job.meta
        assert str(mock_job.meta['error']['message']) == "Test error"
        assert mock_job.save_meta.call_count >= 1  # At least one call for error update

def test_crawl_task_no_job(db_session, auth_user):
    from api.crawl import crawl_task
    
    auth_headers, user = auth_user
    
    # Mock get_current_job to return None and patch crawl to avoid actual crawling
    with patch('rq.get_current_job', return_value=None), \
         patch('api.crawl.crawl') as mock_crawl, \
         patch('api.crawl.get_db', return_value=db_session):
        # Execute crawl task - should not raise an exception
        crawl_task("https://example.com", user=user)
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

@pytest.fixture(scope="function")
def test_document(db_session, auth_user):
    """Create a test document for testing"""
    auth_headers, user = auth_user
    
    doc = Document(
        id=1,
        title="Test Document",
        uri="https://example.com",
        html="<html>Test</html>",
        markdown="# Test",
        domain_id=1,
        workspace_id=user.current_workspace_id
    )
    db_session.add(doc)
    db_session.commit()
    return doc

def test_create_vectorization_batch(db_session, test_document, mock_redis, auth_user):
    from api.crawl import create_vectorization_batch
    
    auth_headers, user = auth_user
    
    # Setup test data
    doc_ids = [test_document.id]
    
    # Mock Redis and Queue
    mock_redis.return_value = MagicMock()
    with patch('api.crawl.Queue') as mock_queue:
        mock_job = MagicMock()
        mock_job.id = str(uuid.uuid4())
        mock_queue.return_value.enqueue.return_value = mock_job
        
        # Execute function
        result = create_vectorization_batch(doc_ids, mock_redis.return_value, db=db_session, user=user)
        
        # Verify result
        assert 'batch_id' in result
        assert 'job_ids' in result
        assert 'progress' in result
        assert result['progress']['total_docs'] == len(doc_ids)
        assert result['progress']['remaining'] == len(doc_ids)
        assert result['progress']['done'] == 0
        assert result['progress']['exceptions'] == 0
        assert result['progress']['progress_percent'] == 0
        
        # Verify queue was called correctly
        mock_queue.return_value.enqueue.assert_called_once()

def test_update_batch_progress(mock_redis):
    from api.crawl import update_batch_progress
    
    # Setup test data
    job_ids = ['job1', 'job2', 'job3']
    
    # Mock jobs with different statuses
    mock_job1 = MagicMock()
    mock_job1.is_finished = True
    mock_job1.is_failed = False
    
    mock_job2 = MagicMock()
    mock_job2.is_finished = False
    mock_job2.is_failed = True
    
    mock_job3 = MagicMock()
    mock_job3.is_finished = False
    mock_job3.is_failed = False
    
    # Mock Job.fetch to return different jobs
    with patch('api.crawl.Job.fetch') as mock_fetch:
        mock_fetch.side_effect = [mock_job1, mock_job2, mock_job3]
        
        # Execute function
        result = update_batch_progress(job_ids, mock_redis.return_value)
        
        # Verify result
        assert result['total_docs'] == len(job_ids)
        assert result['done'] == 1
        assert result['exceptions'] == 1
        assert result['remaining'] == 1
        assert result['progress_percent'] == 33.33

def test_monitor_vectorization_batch(mock_redis, mock_job):
    from api.crawl import monitor_vectorization_batch
    
    # Setup test data
    vector_jobs = ['job1', 'job2']
    
    # Initialize job metadata with vectorization batch info
    mock_job.meta = {
        'vectorization_batch': {
            'batch_id': 'test_batch',
            'job_ids': vector_jobs,
            'progress': {
                'total_docs': 2,
                'done': 0,
                'remaining': 2,
                'exceptions': 0,
                'progress_percent': 0
            }
        }
    }
    
    # Mock jobs that will complete after first check
    mock_job1 = MagicMock()
    mock_job1.is_finished = True
    mock_job1.is_failed = False
    
    mock_job2 = MagicMock()
    mock_job2.is_finished = True
    mock_job2.is_failed = False
    
    # Mock Job.fetch to return different jobs
    with patch('api.crawl.Job.fetch') as mock_fetch, \
         patch('api.crawl.update_batch_progress') as mock_update_progress, \
         patch('time.sleep') as mock_sleep:  # Mock sleep to prevent actual waiting
        
        # Setup mock to return completed jobs immediately
        mock_fetch.side_effect = [mock_job1, mock_job2]
        
        # First call returns partial progress
        mock_update_progress.side_effect = [
            {
                'total_docs': 2,
                'done': 1,
                'remaining': 1,
                'exceptions': 0,
                'progress_percent': 50
            },
            {
                'total_docs': 2,
                'done': 2,
                'remaining': 0,
                'exceptions': 0,
                'progress_percent': 100
            }
        ]
        
        # Execute function with a timeout
        try:
            monitor_vectorization_batch(mock_job, vector_jobs, mock_redis.return_value)
        except Exception as e:
            pytest.fail(f"monitor_vectorization_batch raised an exception: {str(e)}")
        
        # Verify job metadata was updated
        assert mock_job.meta['vectorization_batch']['progress']['done'] == 2
        assert mock_job.meta['vectorization_batch']['progress']['remaining'] == 0
        assert mock_job.meta['vectorization_batch']['progress']['progress_percent'] == 100
        assert mock_job.save_meta.call_count > 0
        
        # Verify sleep was called at least once
        assert mock_sleep.call_count >= 1

def test_crawl_task_with_vectorization(db_session, mock_job, auth_user):
    from api.crawl import crawl_task
    
    auth_headers, user = auth_user
    
    # Setup test data
    test_url = "https://example.com"
    test_doc = Document(
        id=1,
        title="Test Document",
        uri=test_url,
        html="<html>Test</html>",
        markdown="# Test",
        workspace_id=user.current_workspace_id
    )
    db_session.add(test_doc)
    db_session.commit()
    
    # Mock dependencies
    with patch('api.crawl.crawl') as mock_crawl, \
         patch('rq.get_current_job', return_value=mock_job), \
         patch('api.crawl.get_db', return_value=db_session), \
         patch('api.crawl.create_vectorization_batch') as mock_create_batch, \
         patch('api.crawl.monitor_vectorization_batch') as mock_monitor, \
         patch('time.sleep') as mock_sleep:  # Mock sleep to prevent actual waiting
        
        # Setup mocks
        mock_crawl.return_value = [1]  # Return document ID
        mock_create_batch.return_value = {
            'batch_id': 'batch_123',
            'job_ids': ['job1', 'job2'],
            'progress': {
                'total_docs': 2,
                'done': 0,
                'remaining': 2,
                'exceptions': 0,
                'progress_percent': 0
            }
        }
        
        # Execute crawl task with vectorization
        try:
            crawl_task(test_url, recursive=True, store_in_vector=True, user=user)
        except Exception as e:
            pytest.fail(f"crawl_task raised an exception: {str(e)}")
        
        # Verify vectorization was triggered
        mock_create_batch.assert_called_once()
        mock_monitor.assert_called_once()
        
        # Verify job metadata was updated
        assert mock_job.meta['vectorization_batch']['batch_id'] == 'batch_123'
        assert len(mock_job.meta['vectorization_batch']['job_ids']) == 2
        assert mock_job.save_meta.call_count >= 2 
