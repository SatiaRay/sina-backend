import os
import json
import requests
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from datetime import datetime
import re
from difflib import SequenceMatcher
import hashlib
from database.models import Document, CrawledDomain
from database.repository import DocumentRepository, CrawledDomainRepository
from database.models import SessionLocal

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


def crawl(url, recursive=False):
    """
    Crawl a URL and optionally its sub-URLs recursively.
    
    Args:
        url (str): The URL to crawl
        recursive (bool): Whether to crawl sub-URLs recursively
    
    Returns:
        None
    """
    # Initialize database session
    db = SessionLocal()
    document_repo = DocumentRepository(db)
    domain_repo = CrawledDomainRepository(db)
    
    try:
        # Parse the URL to get domain
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        # Check if domain already exists in database
        domain_obj = domain_repo.get_by_domain(domain)
        if domain_obj:
            print(f"Domain {domain} already exists in the database")
        else:
            # Try to access the URL first
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                print(f"Failed to access {url}: Status code {response.status_code}")
                return
            
            # Create domain record
            domain_obj = domain_repo.create({"domain": domain})
            print(f"Created new domain record: {domain}")
        
        # Keep track of visited URLs to avoid duplicates
        visited_urls = set()
        crawled_data = []
        docs = []
        
        def process_url(current_url):
            """Process a single URL and store its content in the database"""
            current_url = current_url.split('#')[0]
            
            # Skip if already visited or is a media file
            if current_url in visited_urls:
                return
            visited_urls.add(current_url)
            
            if str(current_url).endswith(tuple(['.jpg', '.png', '.gif', '.jpeg', '.webp', '.pdf', '.doc', '.docx', '.xls', '.xlsx'])):
                print(f"Skipping media file: {current_url}")
                return
            
            print(f"Processing URL: {current_url}")
            
            try:
                # Fetch and parse the page
                response = requests.get(current_url, timeout=10)
                if response.status_code != 200:
                    print(f"Failed to fetch {current_url}: Status {response.status_code}")
                    return
                
                soup = BeautifulSoup(response.text, 'html.parser')
                if not soup:
                    print(f"Failed to parse HTML for {current_url}")
                    return
                
                # Find all <a> tags with href attribute
                a_tags = soup.find_all('a', href=True)
                
                # Extract href values into a list
                links = []
                for a_tag in a_tags:
                    href = a_tag.get('href', '')
                    if href:  # Only add non-empty href values
                        links.append(href)
                
                # Clean HTML content
                for tag in soup.find_all(['script', 'style', 'link', 'img', 'nav', 'header', 'footer', 'aside']):
                    tag.decompose()
                
                # Get title and content
                title = str(soup.title.string) if soup.title else "Untitled"
                html_content = str(soup)
                text_content = soup.get_text(separator=' ', strip=True)
                
                if not text_content:
                    print(f"No content found in {current_url}")
                    return
                
                # Prepare document data
                parsed_url = urlparse(current_url)
                document_data = {
                    'title': title,
                    'html': html_content,
                    'markdown': text_content,
                    'uri': parsed_url.path or '/',
                    'domain_id': domain_obj.id,
                    'embedding_id': None
                }

                
                # Store in database
                try:
                    existing_docs = document_repo.get_by_uri(document_data['uri'])
                    if existing_docs:
                        document_repo.update(existing_docs[0].id, document_data)
                        docs.append(existing_docs[0].id)
                        print(f"Updated document: {document_data['uri']}")
                    else:
                        new_doc = document_repo.create(document_data)
                        docs.append(new_doc.id)
                        print(f"Created new document: {document_data['uri']}")
                except Exception as e:
                    print(f"Database error for {current_url}: {str(e)}")
                    db.rollback()
                
                # If recursive mode, find all links and process them
                if recursive:
                    for link in links:
                        try:
                            # Convert relative URLs to absolute
                            absolute_url = urljoin(current_url, link)
                            if not absolute_url:  # Skip if URL is invalid
                                continue
                                
                            # Only process URLs from the same domain
                            parsed_absolute_url = urlparse(absolute_url)
                            if parsed_absolute_url.netloc == domain:
                                process_url(absolute_url)
                        except Exception as e:
                            print(f"Error processing link {link} from {current_url}: {str(e)}")
                            continue
            
            except requests.exceptions.RequestException as e:
                print(f"Network error for {current_url}: {str(e)}")
            except Exception as e:
                print(f"Error processing {current_url}: {str(e)}")
                db.rollback()
        
        # Start crawling from the initial URL
        process_url(url)
        
        # After crawling all URLs, remove duplicate content
        remove_duplicate_content(crawled_data, document_repo)

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




