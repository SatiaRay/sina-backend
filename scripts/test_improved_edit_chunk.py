import sys
import os
from pathlib import Path
import requests
import json
import argparse

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# لود کردن متغیرهای محیطی از .env
from dotenv import load_dotenv
load_dotenv()

API_URL = os.getenv('APP_URL', 'http://localhost:8001')

def list_url_chunks(url):
    """
    نمایش تمام چانک‌های مربوط به یک URL
    
    Args:
        url: آدرس منبع داده
    """
    print(f"\n=== چانک‌های مربوط به URL: {url} ===")
    
    try:
        # تبدیل URL به فرمت مناسب برای استفاده در آدرس
        encoded_url = requests.utils.quote(url)
        data_source_endpoint = f"{API_URL}/data_sources/{encoded_url}/chunks"
        
        print(f"درخواست به: {data_source_endpoint}")
        response = requests.get(data_source_endpoint)
        
        if response.status_code == 200:
            chunks = response.json()
            print(f"تعداد چانک‌ها: {len(chunks)}")
            
            for i, chunk in enumerate(chunks):
                print(f"\nچانک {i}:")
                print(f"  متن: {chunk['text'][:150]}...")
                print(f"  منبع: {chunk['metadata']['source']}")
                if 'title' in chunk['metadata']:
                    print(f"  عنوان: {chunk['metadata']['title']}")
            
            return chunks
        else:
            print(f"خطا: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"خطا در دریافت چانک‌ها: {str(e)}")
        return None

def edit_chunk(url, chunk_index, new_text):
    """
    ویرایش یک چانک با استفاده از API
    
    Args:
        url: آدرس منبع داده
        chunk_index: شماره چانک
        new_text: متن جدید
    """
    print(f"\n=== ویرایش چانک شماره {chunk_index} از URL: {url} ===")
    
    try:
        edit_endpoint = f"{API_URL}/edit_chunk"
        payload = {
            "url": url,
            "chunk_index": chunk_index,
            "new_text": new_text
        }
        
        print(f"درخواست به: {edit_endpoint}")
        print(f"داده‌های ارسالی: {json.dumps(payload, ensure_ascii=False)}")
        
        response = requests.post(edit_endpoint, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            print("ویرایش با موفقیت انجام شد.")
            print(f"پاسخ: {json.dumps(result, ensure_ascii=False, indent=2)}")
            return result
        else:
            print(f"خطا: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"خطا در ویرایش چانک: {str(e)}")
        return None

def main():
    parser = argparse.ArgumentParser(description='تست API بهبود یافته ویرایش چانک')
    parser.add_argument('--url', required=True, help='آدرس URL منبع داده')
    parser.add_argument('--index', type=int, help='شماره چانک برای ویرایش')
    parser.add_argument('--text', help='متن جدید برای چانک')
    parser.add_argument('--list-only', action='store_true', help='فقط نمایش چانک‌ها بدون ویرایش')
    
    args = parser.parse_args()
    
    # نمایش چانک‌های موجود
    chunks = list_url_chunks(args.url)
    
    if chunks is None or len(chunks) == 0:
        print(f"هیچ چانکی برای URL {args.url} یافت نشد.")
        return
    
    if args.list_only:
        return
        
    if args.index is None:
        print("لطفاً شماره چانک را با پارامتر --index مشخص کنید.")
        return
        
    if args.text is None:
        print("لطفاً متن جدید را با پارامتر --text مشخص کنید.")
        return
    
    # ویرایش چانک
    result = edit_chunk(args.url, args.index, args.text)
    
    if result:
        # نمایش وضعیت بعد از ویرایش
        print("\n=== وضعیت بعد از ویرایش ===")
        list_url_chunks(args.url)

if __name__ == "__main__":
    main() 