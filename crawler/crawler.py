import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from datetime import datetime
import re
from difflib import SequenceMatcher
import hashlib

def crawl(url, recursive=False):
    """
    Crawl a URL and optionally its sub-URLs recursively.
    
    Args:
        url (str): The URL to crawl
        recursive (bool): Whether to crawl sub-URLs recursively
    
    Returns:
        None
    """
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
            
            # Extract data
            title = soup.title.string if soup.title else "Untitled"
            # Clean the title to use as a filename
            clean_title = re.sub(r'[^\w\-_]', '_', title)[:100]
            
            # Extract domain for folder structure
            domain = urlparse(current_url).netloc
            
            # Create data structure
            current_time = datetime.now().isoformat()
            item = {
                'url': current_url,
                'title': title,
                'html': str(soup),
                'text': soup.get_text(),
                'domain': domain,
                'clean_title': clean_title
            }
            
            crawled_data.append(item)
            
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
    
    # Start crawling from the initial URL
    process_url(url)
    
    # After crawling all URLs, remove duplicate content
    remove_duplicate_content(crawled_data)

def remove_duplicate_content(crawled_data):
    """
    Remove duplicate sections from the crawled data.
    
    Args:
        crawled_data (list): List of dictionaries containing crawled data
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
    
    # Identify common chunks (appearing in more than 50% of pages)
    threshold = len(crawled_data) * 0.5
    common_html_chunks = {k: v['content'] for k, v in html_sections.items() if v['count'] > threshold}
    common_text_chunks = {k: v['content'] for k, v in text_sections.items() if v['count'] > threshold}
    
    print(f"Found {len(common_html_chunks)} common HTML chunks and {len(common_text_chunks)} common text chunks")
    
    # Remove common chunks from each page and save
    for item in crawled_data:
        # Process HTML
        processed_html = item['html']
        for chunk in common_html_chunks.values():
            processed_html = processed_html.replace(chunk, '')
        
        # Process text
        processed_text = item['text']
        for chunk in common_text_chunks.values():
            processed_text = processed_text.replace(chunk, '')
        
        # Create data structure for saving
        current_time = datetime.now().isoformat()
        data = {
            'html': processed_html,
            'text': processed_text,
            'metadata': {
                'source': item['url'],
                'title': item['title'],
                'date_added': current_time,
                'last_modified': current_time
            }
        }
        
        # Save to file
        save_path = os.path.join(os.getcwd(), 'data', 'crawl', item['domain'])
        os.makedirs(save_path, exist_ok=True)
        
        file_path = os.path.join(save_path, f"{item['clean_title']}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        print(f"Saved: {file_path}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Web crawler script')
    parser.add_argument('url', type=str, help='URL to crawl')
    parser.add_argument('--recursive', '-r', action='store_true', help='Crawl recursively')
    
    args = parser.parse_args()
    crawl(args.url, args.recursive)




