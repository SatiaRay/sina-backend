import os
import json
import requests
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urlunparse
from datetime import datetime
import re
from difflib import SequenceMatcher
import hashlib
import asyncio
import time
from dotenv import load_dotenv

from sqlalchemy.orm import Session
from database.models import Document, CrawledDomain
from database.repository import DocumentRepository, CrawledDomainRepository
from database.models import SessionLocal
from models.html_to_markdown_agent import HTMLToMarkdownAgent
from database.vector_store import VectorStore

# Load environment variables
load_dotenv()

# Rate limit configuration
RATE_LIMIT_MAX_RETRIES = int(os.getenv('RATE_LIMIT_MAX_RETRIES', '3'))
RATE_LIMIT_WAIT_MINUTES = int(os.getenv('RATE_LIMIT_WAIT_MINUTES', '5'))
RATE_LIMIT_STATUS_CODES = [429, 503]  # Common rate limit status codes

# Create logs directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Configure logging
logging.basicConfig(
    filename=os.path.join(log_dir, 'crawler.log'),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# To run the crawler, use the following command:
# python -m crawler.main <url> [--recursive]
# 
# Examples:
# python -m crawler.main https://satya.ir
# python -m crawler.main https://satya.ir --recursive
#
# The crawler will extract text content from the specified URL
# and store it in the database for later retrieval and processing.
# Use the --recursive flag to crawl all linked pages within the same domain.

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
        logging.error(f"Error cleaning domain: {str(e)}")
        return url

def crawl(url, recursive=False, db: Session = None, job=None):
    """
    Crawl a URL and optionally its sub-URLs recursively.
    
    Args:
        url (str): The URL to crawl
        recursive (bool): Whether to crawl sub-URLs recursively
        store_in_vector (bool): Whether to store content in vector store
        db (Session): Database session
        job (Job): RQ job object for progress tracking
    
    Returns:
        List of document IDs
    """
    # Initialize database session
    db = db or SessionLocal()
    document_repo = DocumentRepository(db)
    domain_repo = CrawledDomainRepository(db)
    
    # Initialize progress tracking
    total_urls = 0
    crawled_urls = 0
    exception_urls = 0
    
    try:
        # Clean the input URL
        cleaned_url = clean_domain(url)
        
        # Parse the URL to get domain
        parsed_url = urlparse(cleaned_url)
        domain = parsed_url.netloc
        
        # Check if domain already exists in database
        domain_obj = domain_repo.get_by_domain(domain)
        if domain_obj:
            print(f"Domain {domain} already exists in the database")
        else:
            # Try to access the URL first
            response = requests.get(cleaned_url, timeout=10)
            if response.status_code != 200:
                print(f"Failed to access {cleaned_url}: Status code {response.status_code}")
                return
            
            # Create domain record
            domain_obj = domain_repo.create({"domain": domain})
            print(f"Created new domain record: {domain}")
        
        # Keep track of visited URLs to avoid duplicates
        visited_urls = set()
        crawled_urls_set = set()  # New set to track crawled URLs
        crawled_data = []
        docs = []
        
        def update_progress():
            """Update job progress metadata"""
            if job:
                progress = (crawled_urls / total_urls * 100) if total_urls > 0 else 0
                job.meta['progress'] = {
                    'total_urls': total_urls,
                    'crawled_urls': crawled_urls,
                    'exception_urls': exception_urls,
                    'progress_percent': round(progress, 2)
                }
                job.save_meta()
        
        def is_valid_url(url):
            """Check if URL is valid and not a media file"""
            if url in visited_urls:
                return False
            visited_urls.add(url)
            
            if str(url).endswith(tuple(['.jpg', '.png', '.gif', '.jpeg', '.webp', '.pdf', '.doc', '.docx', '.xls', '.xlsx'])):
                print(f"Skipping media file: {url}")
                return False
            return True

        def update_job_status(job, status, message=None):
            """Update job status and metadata"""
            if job:
                job.meta['status'] = status
                if message:
                    job.meta['message'] = message
                job.save_meta()

        def handle_rate_limit(job, retry_count):
            """Handle rate limit by waiting and updating job status"""
            wait_minutes = RATE_LIMIT_WAIT_MINUTES
            update_job_status(job, "rate_limit", f"Rate limit hit. Waiting {wait_minutes} minutes before retry {retry_count}/{RATE_LIMIT_MAX_RETRIES}")
            time.sleep(wait_minutes * 60)  # Convert minutes to seconds

        def fetch_and_parse_page(url, job=None):
            """Fetch and parse the webpage content with rate limit handling"""
            retry_count = 0
            
            while retry_count < RATE_LIMIT_MAX_RETRIES:
                try:
                    response = requests.get(url, timeout=10)
                    
                    # Check for rate limit status codes
                    if response.status_code in RATE_LIMIT_STATUS_CODES:
                        retry_count += 1
                        if retry_count >= RATE_LIMIT_MAX_RETRIES:
                            print(f"Max retries reached for {url} due to rate limiting")
                            return None, None
                        
                        handle_rate_limit(job, retry_count)
                        continue
                    
                    if response.status_code != 200:
                        print(f"Failed to fetch {url}: Status {response.status_code}")
                        return None, None
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    if not soup:
                        print(f"Failed to parse HTML for {url}")
                        return None, None
                    
                    return response, soup
                    
                except requests.exceptions.RequestException as e:
                    print(f"Network error for {url}: {str(e)}")
                    return None, None
                except Exception as e:
                    print(f"Unexpected error for {url}: {str(e)}")
                    return None, None
            
            return None, None

        def extract_links(soup, current_url):
            """Extract and clean links from the page"""
            links = []
            a_tags = soup.find_all('a', href=True)
            
            for a_tag in a_tags:
                href = a_tag.get('href', '')
                if href:
                    href = clean_domain(href)
                    if href not in crawled_urls_set:
                        links.append(href)
            
            return links

        def clean_page_content(soup):
            """Clean the HTML content by removing unnecessary elements"""
            for tag in soup.find_all(['script', 'style', 'link', 'img', 'nav', 'header', 'footer', 'aside']):
                tag.decompose()
            
            title = str(soup.title.string) if soup.title else "Untitled"
            html_content = str(soup)
            text_content = soup.get_text(separator=' ', strip=True)
            
            return title, html_content, text_content

        def store_document(document_data, current_url):
            """Store or update document in the database"""
            try:
                existing_docs = document_repo.db.query(document_repo.model_class).filter(
                    document_repo.model_class.uri == document_data['uri'],
                    document_repo.model_class.domain_id == domain_obj.id
                ).all()
                
                if existing_docs:
                    document_repo.update(existing_docs[0].id, document_data)
                    docs.append(existing_docs[0].id)
                    crawled_urls_set.add(current_url)
                    print(f"Updated document: {document_data['uri']}")
                else:
                    new_doc = document_repo.create(document_data)
                    docs.append(new_doc.id)
                    crawled_urls_set.add(current_url)
                    db.commit()
                    print(f"Created new document: {document_data['uri']}")
                return True
            except Exception as e:
                print(f"Database error for {current_url}: {str(e)}")
                db.rollback()
                return False

        def is_url_crawled(url: str, document_repo: DocumentRepository, domain_id: int) -> bool:
            """
            Check if a URL has already been crawled and stored in the database.
            
            Args:
                url (str): The URL to check
                document_repo (DocumentRepository): Repository for database operations
                domain_id (int): The domain ID to check against
                
            Returns:
                bool: True if URL has been crawled, False otherwise
            """
            try:
                parsed_url = urlparse(url)
                uri = parsed_url.path or '/'
                
                # Check if document exists with this URI and domain
                existing_docs = document_repo.db.query(document_repo.model_class).filter(
                    document_repo.model_class.uri == uri,
                    document_repo.model_class.domain_id == domain_id
                ).first()
                
                return existing_docs is not None
            except Exception as e:
                logging.error(f"Error checking if URL is crawled: {str(e)}")
                return False

        def process_url(current_url):
            """Process a single URL and store its content in the database"""
            nonlocal total_urls, crawled_urls, exception_urls
            
            # Clean and validate URL
            current_url = clean_domain(current_url.split('#')[0])
            if not is_valid_url(current_url):
                return
            
            # Check if URL has already been crawled
            is_already_crawled = is_url_crawled(current_url, document_repo, domain_obj.id)
            if is_already_crawled:
                print(f"URL already crawled: {current_url}")
                # If recursive mode is enabled, we still need to process the links
                if not recursive:
                    return
            
            print(f"Processing URL: {current_url}")
            
            # Fetch and parse page with rate limit handling
            response, soup = fetch_and_parse_page(current_url, job)
            if not response or not soup:
                exception_urls += 1
                update_progress()
                return
            
            # Extract links
            links = extract_links(soup, current_url)
            
            # Update total URLs count for recursive crawling
            if recursive:
                total_urls += len(links)
            
            # Only process and store content if not already crawled
            if not is_already_crawled:
                # Clean page content
                title, html_content, text_content = clean_page_content(soup)
                
                if not text_content:
                    print(f"No content found in {current_url}")
                    exception_urls += 1
                    update_progress()
                    return
                
                # Prepare and store document
                parsed_url = urlparse(current_url)
                document_data = {
                    'title': title,
                    'html': html_content,
                    'markdown': text_content,
                    'uri': parsed_url.path or '/',
                    'domain_id': domain_obj.id
                }
                
                if not store_document(document_data, current_url):
                    exception_urls += 1
                    update_progress()
                    return
                
                crawled_urls += 1
                update_progress()
            
            # Process links recursively if enabled
            if recursive:
                for link in links:
                    try:
                        absolute_url = urljoin(current_url, link)
                        if not absolute_url:
                            continue
                            
                        parsed_absolute_url = urlparse(absolute_url)
                        if parsed_absolute_url.netloc == domain:
                            process_url(absolute_url)
                    except Exception as e:
                        print(f"Error processing link {link} from {current_url}: {str(e)}")
                        exception_urls += 1
                        update_progress()
                        continue
        
        # Initialize total URLs count
        total_urls = 1  # Start with 1 for the initial URL
        
        # Start crawling from the initial URL
        process_url(cleaned_url)
        
        # After crawling all URLs, remove duplicate content
        remove_duplicate_content(crawled_data, document_repo)

        # Final progress update
        if job:
            job.meta['progress'] = {
                'total_urls': total_urls,
                'crawled_urls': crawled_urls,
                'exception_urls': exception_urls,
                'progress_percent': 100
            }
            job.save_meta()

        return docs
        
    finally:
        # Close database session
        db.close()

def remove_duplicate_content(crawled_data, document_repo):
    """
    Remove duplicate sections from the crawled data and update database records.
    
    Args:
        crawled_data (list): List of dictionaries containing crawled data
        document_repo (DocumentRepository): Repository for database operations
    """
    if not crawled_data:
        return
    
    # Extract common sections by comparing HTML content
    print("Analyzing content to identify common sections...")
    
    # First, let's identify common HTML chunks
    html_sections = {}
    text_sections = {}
    
    # Function to split content into chunks
    def get_chunks(content, chunk_size=100):
        return [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
    
    # Collect all chunks and their frequencies
    for item in crawled_data:
        html_chunks = get_chunks(item['html'])
        for chunk in html_chunks:
            chunk_hash = hashlib.md5(chunk.encode()).hexdigest()
            if chunk_hash in html_sections:
                html_sections[chunk_hash]['count'] += 1
            else:
                html_sections[chunk_hash] = {'content': chunk, 'count': 1}
        
        text_chunks = get_chunks(item['text'])
        for chunk in text_chunks:
            chunk_hash = hashlib.md5(chunk.encode()).hexdigest()
            if chunk_hash in text_sections:
                text_sections[chunk_hash]['count'] += 1
            else:
                text_sections[chunk_hash] = {'content': chunk, 'count': 1}
    
    # Identify common chunks (appearing in more than 80% of pages)
    threshold = len(crawled_data) * 0.8  # Increased threshold to 80%
    common_html_chunks = {k: v['content'] for k, v in html_sections.items() if v['count'] > threshold}
    common_text_chunks = {k: v['content'] for k, v in text_sections.items() if v['count'] > threshold}
    
    print(f"Found {len(common_html_chunks)} common HTML chunks and {len(common_text_chunks)} common text chunks")
    
    # Remove common chunks from each page and update database
    for item in crawled_data:
        try:
            # Process HTML
            processed_html = item['html']
            for chunk in common_html_chunks.values():
                processed_html = processed_html.replace(chunk, '')
            
            # Process text
            processed_text = item['text']
            for chunk in common_text_chunks.values():
                processed_text = processed_text.replace(chunk, '')
            
            # Clean and validate processed text
            processed_text = processed_text.strip()
            
            # If processed text is too short, keep the original text
            if len(processed_text) < 100:  # If less than 100 characters, keep original
                processed_text = item['text']
                processed_html = item['html']
                print(f"Keeping original content for {item['uri']} as processed content was too short")
            
            # Create content JSON with processed content
            content_json = json.dumps({
                'html': processed_html,
                'markdown': processed_text  # markdown is equal to the processed text
            })
            
            # Update document in database
            existing_docs = document_repo.get_by_uri(item['uri'])
            if existing_docs:  # Check if we found any documents
                # Update the first document (should be only one due to unique URI)
                document_repo.update(existing_docs[0].id, {
                    'html': processed_html,
                    'markdown': processed_text,
                    'title': item['title']
                })
                print(f"Updated document in database for URI: {item['uri']}")
        except Exception as e:
            print(f"Error updating document for URI {item['uri']}: {str(e)}")
            # Rollback the session to clear any failed transaction
            document_repo.db.rollback()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Web crawler script')
    parser.add_argument('url', type=str, help='URL to crawl')
    parser.add_argument('--recursive', '-r', action='store_true', help='Crawl recursively')
    
    args = parser.parse_args()
    crawl(args.url, args.recursive)




