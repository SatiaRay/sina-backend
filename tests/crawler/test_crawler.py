import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Document, CrawledDomain
from crawler.crawler import crawl
from urllib.parse import urlparse

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_crawler.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop tables after test
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def mock_requests():
    with patch('requests.get') as mock:
        yield mock

def test_recursive_crawl_with_existing_initial_url(db_session, mock_requests):
    """Test that recursive crawling works even when the initial URL is already crawled"""
    # Setup test data
    test_url = "https://example.com"
    test_domain = "example.com"
    
    # Create domain record
    domain = CrawledDomain(domain=test_domain)
    db_session.add(domain)
    db_session.commit()
    domain_id = domain.id
    
    # Create initial document that's already crawled
    initial_doc = Document(
        title="Initial Page",
        uri="/",
        html="<html><body><a href='/page1'>Link 1</a><a href='/page2'>Link 2</a></body></html>",
        markdown="Initial Page",
        domain_id=domain_id
    )
    db_session.add(initial_doc)
    db_session.commit()
    
    # Mock responses for sub-pages
    def mock_get(url, *args, **kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        # Clean the URL to match our test cases
        parsed_url = urlparse(url)
        path = parsed_url.path or '/'
        
        if path == '/':
            mock_response.text = "<html><body><a href='/page1'>Link 1</a><a href='/page2'>Link 2</a></body></html>"
        elif path == '/page1':
            mock_response.text = "<html><body><h1>Page 1</h1><p>Content of page 1</p></body></html>"
        elif path == '/page2':
            mock_response.text = "<html><body><h1>Page 2</h1><p>Content of page 2</p></body></html>"
        else:
            mock_response.status_code = 404
            
        return mock_response
    
    mock_requests.side_effect = mock_get
    
    # Create mock job for progress tracking
    mock_job = MagicMock()
    mock_job.meta = {}
    
    # Run crawler in recursive mode
    doc_ids = crawl(test_url, recursive=True, db=db_session, job=mock_job)
    
    # Verify results
    assert len(doc_ids) == 2  # Should have crawled two sub-pages (initial page was already crawled)
    
    # Check that all pages were crawled
    crawled_docs = db_session.query(Document).filter_by(domain_id=domain_id).all()
    assert len(crawled_docs) == 3  # Initial page + two sub-pages
    
    # Verify the content of each page
    uris = {doc.uri for doc in crawled_docs}
    assert uris == {'/', '/page1', '/page2'}
    
    # Verify job progress was updated
    assert mock_job.meta['progress']['total_urls'] > 0
    assert mock_job.meta['progress']['crawled_urls'] == 2  # Only the new pages were crawled
    assert mock_job.save_meta.call_count > 0 