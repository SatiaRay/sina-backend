import scrapy
from scrapy.crawler import CrawlerProcess
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
import json
from pathlib import Path
import ssl
from scrapy.crawler import CrawlerRunner
from twisted.internet import reactor
from multiprocessing import Process, Queue
from urllib.parse import urlparse, urljoin, urlunparse
from datetime import datetime

# غیرفعال کردن بررسی گواهی SSL
ssl._create_default_https_context = ssl._create_unverified_context

load_dotenv()

class SatyaSpider(scrapy.Spider):
    name = 'satya'
    allowed_domains = None
    start_urls = None
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,  # غیرفعال کردن ربات‌های txt
        'DOWNLOAD_DELAY': 2,  # تاخیر بین درخواست‌ها
        'CONCURRENT_REQUESTS': 5,  # محدود کردن درخواست‌های همزمان
        'COOKIES_ENABLED': False,  # غیرفعال کردن کوکی‌ها
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'DOWNLOADER_CLIENT_TLS_METHOD': 'TLSv1.2',
        'DOWNLOADER_CLIENT_TLS_VERIFY': False,
    }

    def __init__(self, url=None, *args, **kwargs):
        super(SatyaSpider, self).__init__(*args, **kwargs)
        self.all_data = []
        
        # اگر URL ارائه شده باشد از آن استفاده کن، در غیر این صورت از URL پیش‌فرض استفاده کن
        if url:
            self.start_urls = [url]
            # استخراج دامنه از URL
            parsed_url = urlparse(url)
            self.allowed_domains = [parsed_url.netloc]


    def parse(self, response):

        print(f"Processing URL: {response.url}")

        # استخراج محتوای اصلی
        content = {
            'url': response.url,
            'title': response.css('title::text').get() or 'بدون عنوان',
            'content': self.clean_content(response.text),
            'images': self.extract_images(response),
            'pdfs': self.extract_pdfs(response),
            'urls': self.content_urls(response),
            'metadata': {
                'timestamp': response.headers.get('Date', b'').decode(),
                'content_type': response.headers.get('Content-Type', b'').decode()
            }
        }
        
        # اضافه کردن به لیست داده‌ها
        self.all_data.append(content)

        # ذخیره تمام داده‌ها در یک فایل
        self.save_all_data()

    def content_urls(self, response):
        """
        استخراج تمام لینک‌های معتبر از صفحه
        
        Args:
            response: پاسخ دریافتی از صفحه
            
        Returns:
            list: لیست URL های معتبر
        """
        # استخراج تمام لینک‌ها
        urls = set()
        for href in response.css('a::attr(href)').getall():
            try:
                # تبدیل URL نسبی به مطلق
                absolute_url = response.urljoin(href)
                
                # بررسی اینکه URL در دامنه‌های مجاز باشد
                parsed_url = urlparse(absolute_url)
                if parsed_url.netloc in self.allowed_domains:
                    # حذف پارامترهای URL و fragment
                    clean_url = urlunparse((
                        parsed_url.scheme,
                        parsed_url.netloc,
                        parsed_url.path,
                        '',
                        '',
                        ''
                    ))
                    urls.add(clean_url)
                    
            except Exception as e:
                print(f"Error processing URL {href}: {str(e)}")
                continue
                
        return list(urls)

    

    def clean_content(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        
        # حذف اسکریپت‌ها و استایل‌ها
        for script in soup(["script", "style"]):
            script.decompose()
            
        # حذف منوهای بالا (معمولاً در تگ‌های header یا nav هستند)
        for header_element in soup.select('header, .header, #header, .top-menu, #top-menu, .main-menu, #main-menu, .navigation, #navigation, nav, .nav, #nav'):
            header_element.decompose()
            
        # حذف منوهای کناری (معمولاً در تگ‌های sidebar یا aside هستند)
        for sidebar_element in soup.select('sidebar, .sidebar, #sidebar, aside, .aside, #aside, .side-menu, #side-menu'):
            sidebar_element.decompose()
            
        # حذف فوتر
        for footer_element in soup.select('footer, .footer, #footer'):
            footer_element.decompose()
            
        # حذف ویجت‌ها و المان‌های جانبی
        for widget in soup.select('.widget, #widget, .widgets, #widgets'):
            widget.decompose()
            
        # حذف باکس‌های لاگین و جستجو
        for login_search in soup.select('.login, #login, .search, #search, .search-box, #search-box'):
            login_search.decompose()
        
        return soup.get_text(separator=' ', strip=True)

    def extract_images(self, response):
        return [img.attrib['src'] for img in response.css('img') if 'src' in img.attrib]

    def extract_pdfs(self, response):
        return [link for link in response.css('a[href$=".pdf"]::attr(href)').getall()]

    def save_all_data(self):
        data_dir = Path('data/crawled_data')
        data_dir.mkdir(exist_ok=True, parents=True)
        
        # ذخیره هر آیتم در یک فایل JSON جداگانه
        for item in self.all_data:
            # ایجاد نام فایل بر اساس URL
            url_parsed = urlparse(item['url'])
            file_name = url_parsed.netloc + url_parsed.path.replace('/', '_').replace('.', '_')
            
            # حذف کاراکترهای نامعتبر و محدود کردن طول نام فایل
            file_name = ''.join(c for c in file_name if c.isalnum() or c == '_')
            file_name = file_name[:100]  # محدود کردن طول نام فایل
            
            # اضافه کردن پسوند json و ذخیره در مسیر مناسب
            file_path = data_dir / f"{file_name}.json"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(item, f, ensure_ascii=False, indent=2)
                
        # علاوه بر فایل‌های جداگانه، یک فایل شامل همه داده‌ها نیز ذخیره می‌کنیم
        with open('data/crawled_data.json', 'w', encoding='utf-8') as f:
            json.dump(self.all_data, f, ensure_ascii=False, indent=2)

def run_spider_in_process(url, queue):
    """
    اجرای خزنده در یک فرآیند جداگانه
    """

    try:
        process = CrawlerProcess(settings={
            'LOG_LEVEL': 'INFO',
            'LOG_FILE': 'scrapy_output.log',
            'ROBOTSTXT_OBEY': False,
            'DOWNLOAD_DELAY': 2,
            'CONCURRENT_REQUESTS': 5,
            'COOKIES_ENABLED': False,
            'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'DOWNLOADER_CLIENT_TLS_METHOD': 'TLSv1.2',
            'DOWNLOADER_CLIENT_TLS_VERIFY': False,
        })
        
        # روش درست استفاده از کلاس اسپایدر
        process.crawl(SatyaSpider, url=url)
        process.start()
        
        # ایجاد یک نمونه موقت از اسپایدر فقط برای دسترسی به داده‌ها
        spider = SatyaSpider(url=url)
        
        # خواندن داده‌ها از فایل ذخیره شده
        data_file = Path('data/crawled_data.json')
        if data_file.exists():
            with open(data_file, 'r', encoding='utf-8') as f:
                spider.all_data = json.load(f)
                
        # اگر فقط یک لینک خاص خزش شده، ممکن است فایل جداگانه آن را نیز بررسی کنیم
        if url:
            # ایجاد نام فایل بر اساس URL
            url_parsed = urlparse(url)
            file_name = url_parsed.netloc + url_parsed.path.replace('/', '_').replace('.', '_')
            file_name = ''.join(c for c in file_name if c.isalnum() or c == '_')
            file_name = file_name[:100]
            
            specific_file = Path(f'data/crawled_data/{file_name}.json')
            if specific_file.exists():
                with open(specific_file, 'r', encoding='utf-8') as f:
                    try:
                        item_data = json.load(f)
                        # اگر آیتم قبلاً در all_data وجود ندارد، اضافه کنیم
                        if not any(d['url'] == item_data['url'] for d in spider.all_data):
                            spider.all_data.append(item_data)
                    except json.JSONDecodeError:
                        pass
        
        # تبدیل داده‌های استخراج شده به فرمت مناسب برای پایگاه دانش
        knowledge_items = []
        current_time = datetime.now().isoformat()
        for item in spider.all_data:
            knowledge_items.append({
                'text': item['content'],
                'metadata': {
                    'source': item['url'],
                    'url': item['url'],
                    'sub_urls': item['urls'],
                    'title': item['title'],
                    'curation_status': 'pending',
                    'date_added': current_time,
                    'last_modified': current_time
                }
            })
        
        queue.put(knowledge_items)
    except Exception as e:
        print(f"خطا در اجرای خزنده: {str(e)}")
        queue.put([])
    
def run_spider(url=None):
    """
    اجرای خزنده برای یک URL خاص
    
    Parameters:
        url (str): آدرس URL برای خزش. اگر خالی باشد، از URL پیش‌فرض استفاده می‌شود.
        
    Returns:
        list: لیست داده‌های استخراج شده
    """

    urls = set()
    if url:
        urls.add(url)
        
    crawled_urls = set()
    all_knowledge = []

    try:
        while urls:
            current_url = urls.pop()
            
            if current_url in crawled_urls:
                continue
                
            print(f"Crawling URL: {current_url}")
            
            queue = Queue()
            p = Process(target=run_spider_in_process, args=(current_url, queue))
            p.start()
            p.join()
            
            # دریافت نتایج از صف
            knowledge_items = queue.get()
            
            if knowledge_items:
                crawled_urls.add(current_url)
                all_knowledge.extend(knowledge_items)
                
                # Add new URLs from metadata
                for item in knowledge_items:
                    if 'metadata' in item and 'sub_urls' in item['metadata']:
                        new_urls = set(item['metadata']['sub_urls']) - crawled_urls
                        urls.update(new_urls)
            
        if not all_knowledge:
            print("هیچ داده‌ای از خزنده دریافت نشد")
            return []
            
        return all_knowledge
        
    except Exception as e:
        print(f"خطا در اجرای خزنده: {str(e)}")
        return []
