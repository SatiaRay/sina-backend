from bs4 import BeautifulSoup
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Document, CrawledDomain
from crawler.crawler import crawl
from urllib.parse import urlparse
from types import SimpleNamespace

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
    
    with patch("crawler.crawler.fetch_and_parse_page") as mock_fetch:
        root = f"<html><body><a href='{test_url}/page1'>Link 1</a><a href='{test_url}/page2'>Link 2</a></body></html>"
        page1 = "<html><body><h1>Page 1</h1><p>Content of page 1</p></body></html>"
        page2 = "<html><body><h1>Page 2</h1><p>Content of page 2</p></body></html>"
        
        # Configure side_effect: list of values returned per call
        mock_fetch.side_effect = [
            (SimpleNamespace(text=root), BeautifulSoup(root, 'html.parser')),
            (SimpleNamespace(text=page1), BeautifulSoup(page1, 'html.parser')),
            (SimpleNamespace(text=page2), BeautifulSoup(page2, 'html.parser')),
        ]
        
        # Create domain record
        domain = CrawledDomain(domain=test_domain)
        db_session.add(domain)
        db_session.commit()
        domain_id = domain.id
        
        # Create initial document that's already crawled
        initial_doc = Document(
            title="Initial Page",
            uri="/",
            html=f"<html><body><a href='{test_url}/page1'>Link 1</a><a href='{test_url}/page2'>Link 2</a></body></html>",
            markdown="Initial Page",
            domain_id=domain_id
        )
        db_session.add(initial_doc)
        db_session.commit()
        
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
    
   
    
    