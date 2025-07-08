import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Document, CrawledDomain, User, Workspace, AiBot
from api.document import router, vectorize_task, store_vector_document, get_vector_document
from api.auth import router as auth_router
from fastapi import FastAPI
from database.models import get_db
from unittest.mock import patch, MagicMock
import uuid
from fastapi import WebSocketDisconnect
from fastapi import HTTPException
import os

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create test app
from api.main import app

# Override the get_db dependency
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db


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
    with patch('api.document.Redis') as mock:
        yield mock

@pytest.fixture(scope="function")
def mock_queue(mock_redis):
    with patch('api.document.Queue') as mock:
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

@pytest.fixture(scope="function")
def test_workspace(db_session: sessionmaker, auth_user):
    """Create a workspace for testing (owned by user)"""
    auth_headers, user = auth_user
    
    workspace = Workspace(
        name="Test Workspace",
        description="Test workspace description",
        owner_id=user.id,
        is_active=True
    )
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)
    return workspace

@pytest.fixture(scope="function")
def test_domain(db_session, auth_user):
    auth_headers, user = auth_user
    
    domain = CrawledDomain(domain="example.com", workspace_id=user.current_workspace_id)
    db_session.add(domain)
    db_session.commit()
    return db_session.query(CrawledDomain).filter(CrawledDomain.domain == "example.com").first()

@pytest.fixture(scope="function")
def test_aibot(db_session, auth_user):
    auth_headers, user = auth_user
    
    aibot = AiBot(
        name="Test AiBot",
        workspace_id=user.current_workspace_id,
        owner_id=user.id
    )
    db_session.add(aibot)
    db_session.commit()
    return db_session.query(AiBot).filter(AiBot.name == "Test AiBot").first()

@pytest.fixture(scope="function")
def test_document(db_session, test_domain, test_aibot, auth_user):
    auth_headers, user = auth_user
    doc = Document(
        title="Test Document",
        html="<html>Test</html>",
        markdown="# Test",
        uri="https://example.com/test",
        domain_id=test_domain.id,
        aibot_id=test_aibot.id,
        workspace_id=user.current_workspace_id
    )
    db_session.add(doc)
    db_session.commit()
    return doc

# Add fixture for authenticated customer user and token
@pytest.fixture(scope="function")
def auth_user(db_session, request):
    if hasattr(request, "_cached_auth_user"):
        return request._cached_auth_user

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
    result = (auth_headers, user)
    request._cached_auth_user = result
    return result

def test_create_document(db_session, test_domain, test_aibot, auth_user):
    auth_headers, user = auth_user
    
    # Test data
    document_data = {
        "title": "New Document",
        "html": "<html>New Test</html>",
        "markdown": "# New Test",
        "uri": "https://example.com/new",
        "domain_id": test_domain.id,
        "aibot_id": test_aibot.id
    }
    
    # Make request
    response = client.post("/documents/", json=document_data, headers=auth_headers)
    print(response.text)
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == document_data["title"]
    assert data["html"] == document_data["html"]
    assert data["markdown"] == document_data["markdown"]
    assert data["uri"] == document_data["uri"]
    assert data["domain_id"] == test_domain.id
    assert data["aibot_id"] == test_aibot.id
    assert data["aibot"]["id"] == test_aibot.id
    assert data["aibot"]["name"] == test_aibot.name
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data

def test_create_document_invalid_domain(db_session, auth_user):    
    # Test data with non-existent domain
    
    auth_headers, user = auth_user
    
    
    document_data = {
        "title": "New Document",
        "html": "<html>New Test</html>",
        "markdown": "# New Test",
        "uri": "https://example.com/new",
        "domain_id": 999  # Non-existent domain ID
    }
    
    # Make request1
    response = client.post("/documents/", json=document_data, headers=auth_headers)
    
    # Assertions
    assert response.status_code == 400
    assert "Domain not found" in response.json()["detail"]

def test_create_document_invalid_aibot(db_session, test_domain, auth_user):
    auth_headers, user = auth_user
    
    # Test data with non-existent aibot
    document_data = {
        "title": "New Document",
        "html": "<html>New Test</html>",
        "markdown": "# New Test",
        "uri": "https://example.com/new",
        "domain_id": test_domain.id,
        "aibot_id": 999  # Non-existent aibot ID
    }
    
    # Make request
    response = client.post("/documents/", json=document_data, headers=auth_headers)
    
    # Assertions
    assert response.status_code == 400
    assert "AiBot not found" in response.json()["detail"]

def test_get_document(db_session, test_document, test_aibot):
    # Make request
    response = client.get(f"/documents/{test_document.id}")
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_document.id
    assert data["title"] == test_document.title
    assert data["html"] == test_document.html
    assert data["markdown"] == test_document.markdown
    assert data["uri"] == test_document.uri
    assert data["domain_id"] == test_document.domain_id
    assert data["aibot_id"] == test_aibot.id
    assert data["aibot"]["id"] == test_aibot.id
    assert data["aibot"]["name"] == test_aibot.name

def test_get_document_not_found(db_session):
    # Make request with non-existent ID
    response = client.get("/documents/999")
    
    # Assertions
    assert response.status_code == 404
    assert "Document not found" in response.json()["detail"]

def test_update_document(db_session, test_document, test_aibot):
    # Test data
    update_data = {
        "title": "Updated Title",
        "html": "<html>Updated Test</html>",
        "markdown": "# Updated Test",
        "aibot_id": test_aibot.id
    }
    
    # Make request
    response = client.put(f"/documents/{test_document.id}", json=update_data)
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == update_data["title"]
    assert data["html"] == update_data["html"]
    assert data["markdown"] == update_data["markdown"]
    assert data["aibot_id"] == test_aibot.id
    assert data["aibot"]["id"] == test_aibot.id
    assert data["aibot"]["name"] == test_aibot.name
    assert data["id"] == test_document.id

def test_update_document_invalid_aibot(db_session, test_document):
    # Test data with non-existent aibot
    update_data = {
        "title": "Updated Title",
        "aibot_id": 999  # Non-existent aibot ID
    }
    
    # Make request
    response = client.put(f"/documents/{test_document.id}", json=update_data)
    
    # Assertions
    assert response.status_code == 400
    assert "AiBot not found" in response.json()["detail"]

def test_delete_document(db_session, test_document):
    # Make request
    response = client.delete(f"/documents/{test_document.id}")
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["message"] == "Document deleted successfully"
    
    # Verify document is deleted
    response = client.get(f"/documents/{test_document.id}")
    assert response.status_code == 404

def test_list_documents(db_session, test_document, test_aibot):
    # Make request
    response = client.get("/documents/")
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert "pages" in data
    assert len(data["items"]) > 0
    assert data["items"][0]["id"] == test_document.id
    assert data["items"][0]["aibot_id"] == test_aibot.id
    assert data["items"][0]["aibot"]["id"] == test_aibot.id
    assert data["items"][0]["aibot"]["name"] == test_aibot.name

def test_vectorize_document(db_session, test_document, mock_queue, mock_job):
    # Setup mock queue
    mock_queue.return_value.enqueue.return_value = mock_job
    
    # Test data
    vectorize_data = {
        "html": "<html>Vector Test</html>",
        "metadata": {
            "source": "https://example.com/vector",
            "title": "Vector Test"
        }
    }
    
    # Make request
    response = client.post(f"/documents/{test_document.id}/vectorize", json=vectorize_data)
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "job_id" in data

@pytest.mark.asyncio
async def test_websocket_vectorize_status(mock_redis, mock_job):
    # Setup mock job
    mock_job.meta = {
        'progress': {'type': 'info', 'msg': 'Processing...'}
    }
    mock_job.get_status.return_value = 'started'
    mock_job.is_finished = False
    mock_job.is_failed = False

    # Mock Redis connection
    mock_redis.return_value = MagicMock()

    # Mock Job.fetch to return our mock job
    with patch('api.document.Job.fetch', return_value=mock_job), \
         patch('api.document.Redis', return_value=mock_redis.return_value):
        try:
            # Create WebSocket client
            with client.websocket_connect(f"/ws/documents/vectorize/{mock_job.id}") as websocket:
                # Receive progress update
                data = websocket.receive_json()
                assert data["event"] == "change_progress"
                assert data["progress"]["type"] == "info"
                assert data["progress"]["msg"] == "Processing..."
                assert data["status"] == "started"
        except WebSocketDisconnect:
            # This is expected as the WebSocket will close after sending the message
            pass



def test_search_documents_by_title(db_session, test_document, test_aibot):
    # Make request
    response = client.get("/documents/search/title?query=Test")
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["id"] == test_document.id
    assert data[0]["aibot_id"] == test_aibot.id
    assert data[0]["aibot"]["id"] == test_aibot.id
    assert data[0]["aibot"]["name"] == test_aibot.name

def test_get_documents_by_aibot(db_session, test_document, test_aibot):
    # Make request
    response = client.get(f"/documents/aibot/{test_aibot.id}")
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert "pages" in data
    assert len(data["items"]) > 0
    assert data["items"][0]["id"] == test_document.id
    assert data["items"][0]["aibot_id"] == test_aibot.id
    assert data["items"][0]["aibot"]["id"] == test_aibot.id
    assert data["items"][0]["aibot"]["name"] == test_aibot.name

def test_get_documents_by_aibot_not_found(db_session):
    # Make request with non-existent aibot ID
    response = client.get("/documents/aibot/999")
    
    # Assertions
    assert response.status_code == 404
    assert "AiBot not found" in response.json()["detail"]


def test_get_manual_documents(db_session, test_aibot, auth_user):
    auth_headers, user = auth_user
    
    # Create a manual document
    manual_doc = Document(
        title="Manual Document",
        html="<html>Manual Test</html>",
        markdown="# Manual Test",
        uri="https://example.com/manual",
        type="manual",
        aibot_id=test_aibot.id,
        workspace_id=user.current_workspace_id
    )
    db_session.add(manual_doc)
    db_session.commit()
    
    # Make request
    response = client.get("/documents/manual")
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert "pages" in data
    assert len(data["items"]) > 0
    assert data["items"][0]["id"] == manual_doc.id
    assert data["items"][0]["aibot_id"] == test_aibot.id
    assert data["items"][0]["aibot"]["id"] == test_aibot.id
    assert data["items"][0]["aibot"]["name"] == test_aibot.name

def test_get_documents_by_domain(db_session, test_document, test_domain, test_aibot):
    # Make request
    response = client.get(f"/documents/domain/{test_domain.id}")
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert "pages" in data
    assert len(data["items"]) > 0
    assert data["items"][0]["id"] == test_document.id
    assert data["items"][0]["domain_id"] == test_domain.id
    assert data["items"][0]["aibot_id"] == test_aibot.id
    assert data["items"][0]["aibot"]["id"] == test_aibot.id
    assert data["items"][0]["aibot"]["name"] == test_aibot.name

def test_get_documents_by_domain_not_found(db_session):
    # Make request with non-existent domain ID
    response = client.get("/documents/domain/999")
    
    # Assertions
    assert response.status_code == 404
    assert "Domain not found" in response.json()["detail"] 

@pytest.mark.asyncio
async def test_vectorize_task_success(db_session, test_document, mock_job):
    # Setup test data
    html = "<html>Test Vector Content</html>"
    metadata = {"source": "test", "title": "Test Vector"}
    title = "New Title"  # Add test title
    
    # Mock dependencies
    with patch('rq.get_current_job', return_value=mock_job), \
         patch('api.document.html_to_markdown_agent.convert', return_value="# Test Vector Content"), \
         patch('api.document.store_vector_document', return_value="vec_123"), \
         patch('api.document.get_vector_document', return_value={"vector_id": "vec_123", "text": "# Test Vector Content"}), \
         patch('api.document.DocumentRepository') as mock_repo:
        
        # Setup mock repository
        mock_repo.return_value.get.return_value = test_document
        
        # Define update behavior to actually update the test document
        def update_document(document_id, update_data):
            for key, value in update_data.items():
                setattr(test_document, key, value)
            db_session.commit()
            return test_document
        
        mock_repo.return_value.update.side_effect = update_document
        
        # Execute task
        await vectorize_task(test_document.id, html, metadata, title)
        
        # Verify job progress updates
        assert mock_job.meta['progress']['type'] == 'info'
        assert mock_job.meta['progress']['msg'] == "Finished"
        assert mock_job.save_meta.call_count >= 5  # At least 5 progress updates
        
        # Verify document update was called with correct data including title and vector_id
        mock_repo.return_value.update.assert_called_once_with(
            test_document.id,
            {
                "title": title,  # Verify title is updated
                "html": html,
                "markdown": "# Test Vector Content",
                "vector_id": "vec_123",  # Verify vector_id is set
                "ai_markdown": True,
                "uri": test_document.uri
            }
        )
        
        # Verify document was updated in the database
        db_session.refresh(test_document)
        assert test_document.title == title  # Verify title is updated
        assert test_document.html == html
        assert test_document.markdown == "# Test Vector Content"
        assert test_document.vector_id == "vec_123"  # Verify vector_id has been set

@pytest.mark.asyncio
async def test_vectorize_task_document_not_found(db_session, mock_job):
    # Setup test data
    html = "<html>Test Vector Content</html>"
    metadata = {"source": "test", "title": "Test Vector"}
    
    # Mock dependencies
    with patch('rq.get_current_job', return_value=mock_job), \
         patch('api.document.DocumentRepository') as mock_repo:
        
        # Setup mock repository to return None (document not found)
        mock_repo.return_value.get.return_value = None
        
        # Execute task with non-existent document ID
        with pytest.raises(HTTPException) as exc_info:
            await vectorize_task(999, html, metadata)
        
        # Verify error
        assert exc_info.value.status_code == 500
        assert "404: Document not found" in str(exc_info.value.detail)
        
        # Verify error was captured in job metadata
        assert mock_job.meta['progress']['type'] == 'error'
        assert "404: Document not found" in mock_job.meta['progress']['msg']

@pytest.mark.asyncio
async def test_vectorize_task_vector_store_error(db_session, test_document, mock_job):
    # Setup test data
    html = "<html>Test Vector Content</html>"
    metadata = {"source": "test", "title": "Test Vector"}
    
    # Mock dependencies
    with patch('rq.get_current_job', return_value=mock_job), \
         patch('api.document.html_to_markdown_agent.convert', return_value="# Test Vector Content"), \
         patch('api.document.store_vector_document', side_effect=Exception("Vector store error")), \
         patch('api.document.DocumentRepository') as mock_repo:
        
        # Setup mock repository
        mock_repo.return_value.get.return_value = test_document
        
        # Execute task
        with pytest.raises(HTTPException) as exc_info:
            await vectorize_task(test_document.id, html, metadata)
        
        # Verify error
        assert exc_info.value.status_code == 500
        assert "Vector store error" in str(exc_info.value.detail)
        
        # Verify error was captured in job metadata
        assert mock_job.meta['progress']['type'] == 'error'
        assert "Vector store error" in mock_job.meta['progress']['msg']

@pytest.mark.asyncio
async def test_store_vector_document():
    # Test data
    vector_doc = {
        "text": "Test content",
        "metadata": {"source": "test"}
    }
    
    # Mock httpx client
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = {"document_ids": ["vec_123"]}
        mock_response.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
        
        # Test with default host
        result = await store_vector_document(vector_doc)
        assert result == "vec_123"
        
        # Test with custom host
        os.environ['HOST'] = 'custom-host:8000'
        result = await store_vector_document(vector_doc)
        assert result == "vec_123"
        
        # Test with host that already has protocol
        os.environ['HOST'] = 'https://custom-host:8000'
        result = await store_vector_document(vector_doc)
        assert result == "vec_123"

@pytest.mark.asyncio
async def test_get_vector_document():
    # Mock httpx client
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = {"vector_id": "vec_123", "text": "Test content"}
        mock_response.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
        
        # Test with default host
        result = await get_vector_document("vec_123")
        assert result == {"vector_id": "vec_123", "text": "Test content"}
        
        # Test with custom host
        os.environ['HOST'] = 'custom-host:8000'
        result = await get_vector_document("vec_123")
        assert result == {"vector_id": "vec_123", "text": "Test content"}
        
        # Test with host that already has protocol
        os.environ['HOST'] = 'https://custom-host:8000'
        result = await get_vector_document("vec_123")
        assert result == {"vector_id": "vec_123", "text": "Test content"}

@pytest.mark.asyncio
async def test_vectorize_task_reuse_existing_markdown(db_session, test_document, mock_job):
    """Test that vectorize_task reuses existing markdown when HTML hasn't changed and ai_markdown is True"""
    # Setup test document with ai_markdown=True
    test_document.ai_markdown = True
    test_document.html = "<html>Test Content</html>"
    test_document.markdown = "# Test Content"
    db_session.commit()

    # Mock the HTML to Markdown agent, rq.get_current_job, and vector store functions
    with patch('api.document.html_to_markdown_agent.convert') as mock_convert, \
         patch('rq.get_current_job', return_value=mock_job), \
         patch('api.document.store_vector_document', return_value="vec_123"), \
         patch('api.document.get_vector_document', return_value={"vector_id": "vec_123", "text": "# Test Content"}), \
         patch('api.document.DocumentRepository') as mock_repo:
        
        # Setup mock repository to return our test document
        mock_repo.return_value.get.return_value = test_document
        
        # Call vectorize_task with same HTML
        await vectorize_task(test_document.id, test_document.html)

        # Verify that HTML to Markdown conversion was not called
        mock_convert.assert_not_called()

@pytest.mark.asyncio
async def test_vectorize_task_regenerate_markdown_html_changed(db_session, test_document, mock_job):
    """Test that vectorize_task regenerates markdown when HTML has changed"""
    # Setup test document with ai_markdown=True
    test_document.ai_markdown = True
    test_document.html = "<html>Old Content</html>"
    test_document.markdown = "# Old Content"
    db_session.commit()

    new_html = "<html>New Content</html>"
    expected_markdown = "# New Content"

    # Mock the HTML to Markdown agent, rq.get_current_job, and vector store functions
    with patch('api.document.html_to_markdown_agent.convert', return_value=expected_markdown) as mock_convert, \
         patch('rq.get_current_job', return_value=mock_job), \
         patch('api.document.store_vector_document', return_value="vec_123"), \
         patch('api.document.get_vector_document', return_value={"vector_id": "vec_123", "text": expected_markdown}), \
         patch('api.document.DocumentRepository') as mock_repo:
        
        # Setup mock repository to return our test document
        mock_repo.return_value.get.return_value = test_document
        
        # Call vectorize_task with new HTML
        await vectorize_task(test_document.id, new_html)

        # Verify that HTML to Markdown conversion was called with new HTML
        mock_convert.assert_called_once_with(new_html)

@pytest.mark.asyncio
async def test_vectorize_task_regenerate_markdown_no_ai_markdown(db_session, test_document, mock_job):
    """Test that vectorize_task regenerates markdown when ai_markdown is False"""
    # Setup test document with ai_markdown=False
    test_document.ai_markdown = False
    test_document.html = "<html>Test Content</html>"
    test_document.markdown = "# Test Content"
    db_session.commit()

    expected_markdown = "# New Markdown"

    # Mock the HTML to Markdown agent, rq.get_current_job, and vector store functions
    with patch('api.document.html_to_markdown_agent.convert', return_value=expected_markdown) as mock_convert, \
         patch('rq.get_current_job', return_value=mock_job), \
         patch('api.document.store_vector_document', return_value="vec_123"), \
         patch('api.document.get_vector_document', return_value={"vector_id": "vec_123", "text": expected_markdown}), \
         patch('api.document.DocumentRepository') as mock_repo:
        
        # Setup mock repository to return our test document
        mock_repo.return_value.get.return_value = test_document
        
        # Call vectorize_task with same HTML
        await vectorize_task(test_document.id, test_document.html)

        # Verify that HTML to Markdown conversion was called
        mock_convert.assert_called_once_with(test_document.html)

@pytest.mark.asyncio
async def test_vectorize_task_regenerate_markdown_no_existing_markdown(db_session, test_document, mock_job):
    """Test that vectorize_task regenerates markdown when no existing markdown is present"""
    # Setup test document with ai_markdown=True but no markdown
    test_document.ai_markdown = True
    test_document.html = "<html>Test Content</html>"
    test_document.markdown = None
    db_session.commit()

    expected_markdown = "# New Markdown"

    # Mock the HTML to Markdown agent, rq.get_current_job, and vector store functions
    with patch('api.document.html_to_markdown_agent.convert', return_value=expected_markdown) as mock_convert, \
         patch('rq.get_current_job', return_value=mock_job), \
         patch('api.document.store_vector_document', return_value="vec_123"), \
         patch('api.document.get_vector_document', return_value={"vector_id": "vec_123", "text": expected_markdown}), \
         patch('api.document.DocumentRepository') as mock_repo:
        
        # Setup mock repository to return our test document
        mock_repo.return_value.get.return_value = test_document
        
        # Call vectorize_task with same HTML
        await vectorize_task(test_document.id, test_document.html)

        # Verify that HTML to Markdown conversion was called
        mock_convert.assert_called_once_with(test_document.html)

@pytest.mark.asyncio
async def test_vectorize_task_title_updates(db_session, test_document, mock_job):
    """Test that vectorize_task properly handles title updates in both metadata and document"""
    # Setup test data
    html = "<html>Test Vector Content</html>"
    metadata = {"source": "test"}
    title = "New Custom Title"
    vector_id = "vec_123"  # Define vector_id explicitly
    
    # Mock dependencies
    with patch('rq.get_current_job', return_value=mock_job), \
         patch('api.document.html_to_markdown_agent.convert', return_value="# Test Vector Content"), \
         patch('api.document.store_vector_document', return_value=vector_id) as mock_store, \
         patch('api.document.get_vector_document', return_value={"vector_id": vector_id, "text": "# Test Vector Content"}), \
         patch('api.document.DocumentRepository') as mock_repo:
        
        # Setup mock repository
        mock_repo.return_value.get.return_value = test_document
        
        # Define update behavior to actually update the test document
        def update_document(document_id, update_data):
            # Update the test document with the new values
            for key, value in update_data.items():
                if hasattr(test_document, key):
                    setattr(test_document, key, value)
            db_session.commit()
            return test_document
        
        mock_repo.return_value.update.side_effect = update_document
        
        # Execute task with title parameter
        await vectorize_task(test_document.id, html, metadata, title)
        
        # Verify store_vector_document was called with correct metadata including title
        mock_store.assert_called_once()
        call_args = mock_store.call_args[0][0]
        assert call_args["metadata"]["title"] == title
        
        # Verify document was updated with new title
        db_session.refresh(test_document)
        assert test_document.title == title
        
        # Reset mocks for next test
        mock_store.reset_mock()
        
        title = "Test title"
        await vectorize_task(test_document.id, html, {"source": "test"}, title)
        
        # Verify document was updated with title from metadata
        db_session.refresh(test_document)
        assert test_document.title == title
        
        # Reset mocks for next test
        mock_store.reset_mock()
        
        # Test with no title provided (should keep existing title)
        original_title = test_document.title
        await vectorize_task(test_document.id, html, {})
        
        # Verify document kept its existing title
        db_session.refresh(test_document)
        assert test_document.title == original_title