import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from datetime import datetime
import re
from difflib import SequenceMatcher
import hashlib
from database.models import Document
from database.repository import DocumentRepository
from database.models import SessionLocal

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
    
    try:
        # Check if URL already exists in database
        existing_docs = document_repo.get_by_source(url)
        if existing_docs:
            print(f"URL {url} already exists in the database. Skipping crawl.")
            return
        
        # Keep track of visited URLs to avoid duplicates
        visited_urls = set()
        crawled_data = []
        
        def process_url(current_url):
            current_url = current_url.split('#')[0]

            if current_url in visited_urls:
                return
            
            visited_urls.add(current_url)
            
            if str(current_url).endswith(tuple(['.jpg', '.png', '.gif', '.jpeg', '.webp'])):
                print(f"Skipping {current_url} because it is a media file")
                return
            
            print(f"Crawling {current_url}")
            
            try:
                # Fetch the page
                response = requests.get(current_url, timeout=10)
                if response.status_code != 200:
                    print(f"Failed to fetch {current_url}: Status code {response.status_code}")
                    return
                
                print(f"Fetched {current_url}")
                
                # Parse the HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove script, style, link and img tags
                for tag in soup.find_all(['script', 'style', 'link', 'img']):
                    tag.decompose()
                
                # Extract data and ensure it's a string
                title = str(soup.title.string) if soup.title else "Untitled"
                # Clean the title to use as a filename
                clean_title = re.sub(r'[^\w\-_]', '_', title)[:100]
                
                # Extract domain for folder structure
                domain = urlparse(current_url).netloc
                
                # Get text content and ensure it's a string
                text_content = str(soup.get_text())
                
                # Clean and validate content
                text_content = text_content.strip()
                if not text_content:
                    print(f"Skipping {current_url} because it has no content")
                    return
                
                # Create data structure
                current_time = datetime.now().isoformat()
                item = {
                    'url': current_url,
                    'title': title,
                    'html': str(soup),
                    'text': text_content,
                    'domain': domain,
                    'clean_title': clean_title
                }
                
                crawled_data.append(item)
                
                try:
                    # Create content JSON with html and markdown (text) fields
                    content_json = json.dumps({
                        'html': str(soup),
                        'markdown': text_content  # markdown is equal to the text content
                    })
                    
                    # Check if document with this source already exists
                    existing_docs = document_repo.get_by_source(current_url)
                    if existing_docs:
                        # Update existing document
                        document_repo.update(existing_docs[0].id, {
                            'title': title,
                            'content': content_json,
                            'source': current_url,
                            'embedding_id': None
                        })
                        print(f"Updated existing document for URL: {current_url}")
                    else:
                        # Create new document
                        document_data = {
                            'title': title,
                            'content': content_json,
                            'source': current_url,
                            'embedding_id': None  # Will be set later when processed by vector store
                        }
                        document_repo.create(document_data)
                        print(f"Created new document for URL: {current_url}")
                except Exception as e:
                    print(f"Error storing document in database: {str(e)}")
                    # Rollback the session to clear any failed transaction
                    db.rollback()
                
                # If recursive, find all links and process them
                if recursive:
                    links = soup.find_all('a', href=True)
                    for link in links:
                        href = link['href']
                        # Convert relative URLs to absolute
                        absolute_url = urljoin(current_url, href)
                        # Only process URLs from the same domain
                        if urlparse(absolute_url).netloc == domain:
                            process_url(absolute_url)
            
            except Exception as e:
                print(f"Error processing {current_url}: {str(e)}")
                # Rollback the session to clear any failed transaction
                db.rollback()
        
        # Start crawling from the initial URL
        process_url(url)
        
        # After crawling all URLs, remove duplicate content
        remove_duplicate_content(crawled_data, document_repo)
        
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
                print(f"Keeping original content for {item['url']} as processed content was too short")
            
            # Create content JSON with processed content
            content_json = json.dumps({
                'html': processed_html,
                'markdown': processed_text  # markdown is equal to the processed text
            })
            
            # Update document in database
            existing_docs = document_repo.get_by_source(item['url'])
            if existing_docs:  # Check if we found any documents
                # Update the first document (should be only one due to unique source)
                document_repo.update(existing_docs[0].id, {
                    'content': content_json,
                    'title': item['title']
                })
                print(f"Updated document in database for URL: {item['url']}")
        except Exception as e:
            print(f"Error updating document for URL {item['url']}: {str(e)}")
            # Rollback the session to clear any failed transaction
            document_repo.db.rollback()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Web crawler script')
    parser.add_argument('url', type=str, help='URL to crawl')
    parser.add_argument('--recursive', '-r', action='store_true', help='Crawl recursively')
    
    args = parser.parse_args()
    crawl(args.url, args.recursive)




