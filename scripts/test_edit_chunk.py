import sys
import os
from pathlib import Path
import requests
import json

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# لود کردن متغیرهای محیطی از .env
from dotenv import load_dotenv
load_dotenv()

API_URL = os.getenv('APP_URL', 'http://localhost:8001')

def test_edit_chunk(url, chunk_index, new_text):
    """
    تست API ویرایش چانک
    
    Args:
        url: آدرس منبع داده
        chunk_index: شماره چانک برای ویرایش
        new_text: متن جدید برای جایگزینی
    """
    endpoint = f"{API_URL}/edit_chunk"
    payload = {
        "url": url,
        "chunk_index": chunk_index,
        "new_text": new_text
    }
    
    print(f"ارسال درخواست به {endpoint} با پارامترهای:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(endpoint, json=payload)
        
        print(f"\nوضعیت پاسخ: {response.status_code}")
        if response.status_code == 200:
            print("ویرایش با موفقیت انجام شد")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        else:
            print(f"خطا: {response.text}")
    except Exception as e:
        print(f"خطا در ارسال درخواست: {str(e)}")

def list_chunks(url):
    """
    دریافت و نمایش چانک‌های یک منبع
    
    Args:
        url: آدرس منبع داده
    """
    print(f"\nدریافت چانک‌های منبع {url}:")
    try:
        encoded_url = requests.utils.quote(url)
        response = requests.get(f"{API_URL}/data_sources/{encoded_url}/chunks")
        
        if response.status_code == 200:
            chunks = response.json()
            print(f"تعداد چانک‌ها: {len(chunks)}")
            for i, chunk in enumerate(chunks):
                print(f"\nچانک شماره {i}:")
                print(f"متن: {chunk['text'][:100]}...")
                print(f"منبع: {chunk['metadata'].get('source', '')}")
                if chunk['metadata'].get('title'):
                    print(f"عنوان: {chunk['metadata'].get('title', '')}")
        else:
            print(f"خطا در دریافت چانک‌ها: {response.text}")
    except Exception as e:
        print(f"خطا در ارسال درخواست: {str(e)}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='تست API ویرایش چانک')
    parser.add_argument('--url', required=True, help='آدرس منبع داده')
    parser.add_argument('--index', type=int, required=True, help='شماره چانک برای ویرایش')
    parser.add_argument('--text', required=True, help='متن جدید برای جایگزینی')
    parser.add_argument('--list', action='store_true', help='نمایش لیست چانک‌ها قبل از ویرایش')
    
    args = parser.parse_args()
    
    if args.list:
        list_chunks(args.url)
    
    test_edit_chunk(args.url, args.index, args.text)
    
    if args.list:
        print("\nوضعیت بعد از ویرایش:")
        list_chunks(args.url) 