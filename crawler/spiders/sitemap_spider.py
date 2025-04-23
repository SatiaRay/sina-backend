import scrapy
from scrapy.spiders import SitemapSpider as ScrapySitemapSpider
import json
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

class SitemapSpider(ScrapySitemapSpider):
    name = 'sitemap_spider'
    
    def __init__(self, sitemap_url=None, *args, **kwargs):
        super(SitemapSpider, self).__init__(*args, **kwargs)
        self.sitemap_urls = [sitemap_url] if sitemap_url else []
        self.all_data = []
        self.processed_urls = set()
        
    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse_sitemap,
                errback=self.handle_error,
                dont_filter=True,
                headers={'Accept': 'application/xml, text/xml, */*'}
            )

    def handle_error(self, failure):
        print(f"Error processing request: {failure.value}")

    def parse_sitemap(self, response):
        try:
            # Try parsing as XML first
            soup = BeautifulSoup(response.text, 'xml')
            
            # Check for sitemap index
            sitemaps = soup.find_all('sitemap')
            if sitemaps:
                print(f"Found sitemap index with {len(sitemaps)} sitemaps")
                for sitemap in sitemaps:
                    loc = sitemap.find('loc')
                    if loc and loc.text not in self.processed_urls:
                        self.processed_urls.add(loc.text)
                        yield scrapy.Request(
                            loc.text,
                            callback=self.parse_sitemap,
                            errback=self.handle_error,
                            dont_filter=True,
                            headers={'Accept': 'application/xml, text/xml, */*'}
                        )
                return
            
            # Check for WordPress-style URL entries
            urls = soup.find_all('url')
            if urls:
                print(f"Found {len(urls)} URLs in sitemap")
                for url_entry in urls:
                    loc = url_entry.find('loc')
                    if loc and loc.text not in self.processed_urls:
                        self.processed_urls.add(loc.text)
                        yield scrapy.Request(
                            loc.text,
                            callback=self.parse_content,
                            errback=self.handle_error,
                            dont_filter=True
                        )
                return
            
            # If no sitemaps or URLs found, try parsing as HTML
            html_soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for XML sitemap links
            sitemap_links = html_soup.find_all('a', href=lambda href: href and href.endswith('.xml'))
            if sitemap_links:
                print(f"Found {len(sitemap_links)} sitemap links in HTML")
                for link in sitemap_links:
                    sitemap_url = urljoin(response.url, link['href'])
                    if sitemap_url not in self.processed_urls:
                        self.processed_urls.add(sitemap_url)
                        yield scrapy.Request(
                            sitemap_url,
                            callback=self.parse_sitemap,
                            errback=self.handle_error,
                            dont_filter=True,
                            headers={'Accept': 'application/xml, text/xml, */*'}
                        )
                return
            
            print(f"No valid sitemap content found in {response.url}")
            
        except Exception as e:
            print(f"Error parsing sitemap {response.url}: {str(e)}")
    
    def parse_content(self, response):
        """
        پردازش محتوای هر صفحه
        """
        try:
            # استخراج محتوا با BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # حذف اسکریپت‌ها و استایل‌ها
            for script in soup(['script', 'style']):
                script.decompose()
                
            # حذف منوها و فوتر
            for nav in soup(['nav', 'header', 'footer']):
                nav.decompose()
                
            # استخراج متن و پاکسازی
            text = soup.get_text()
            text = re.sub(r'\s+', ' ', text).strip()
            
            # استخراج عنوان
            title = soup.title.string if soup.title else ''
            title = re.sub(r'\s+', ' ', title).strip() if title else ''
            
            # ذخیره داده‌ها
            data = {
                'url': response.url,
                'title': title,
                'content': text,
                'date_crawled': datetime.now().isoformat()
            }
            
            self.all_data.append(data)
            
            # ذخیره در فایل
            data_dir = Path('data/crawled_data')
            data_dir.mkdir(parents=True, exist_ok=True)
            
            with open(data_dir / 'crawled_data.json', 'w', encoding='utf-8') as f:
                json.dump(self.all_data, f, ensure_ascii=False, indent=2)
                
            print(f"Successfully processed {response.url}")
                
        except Exception as e:
            print(f"Error processing content from {response.url}: {str(e)}") 