import sys
import os
from pathlib import Path
import requests
import json
import time

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# لود کردن متغیرهای محیطی از .env
from dotenv import load_dotenv
load_dotenv()

API_URL = os.getenv('APP_URL', 'http://localhost:8001')

def test_add_url_knowledge(url):
    """
    تست افزودن URL به پایگاه دانش
    
    Args:
        url: آدرس URL برای افزودن به پایگاه دانش
    """
    print(f"=== تست افزودن URL به پایگاه دانش ===")
    print(f"URL: {url}")
    
    endpoint = f"{API_URL}/add_knowledge"
    payload = {
        "url": url
    }
    
    try:
        print(f"ارسال درخواست به {endpoint}...")
        response = requests.post(endpoint, json=payload)
        
        print(f"کد وضعیت: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("پاسخ:")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print(f"تعداد اسناد اضافه شده: {result.get('document_count', 0)}")
            return result
        else:
            print(f"خطا: {response.text}")
            return None
    except Exception as e:
        print(f"خطا در ارسال درخواست: {str(e)}")
        return None

def check_data_source(url):
    """
    بررسی وجود URL در لیست منابع داده
    
    Args:
        url: آدرس URL برای جستجو
    """
    print(f"\n=== بررسی وجود URL در لیست منابع داده ===")
    print(f"URL: {url}")
    
    endpoint = f"{API_URL}/data_sources"
    
    try:
        print(f"ارسال درخواست به {endpoint}...")
        response = requests.get(endpoint)
        
        print(f"کد وضعیت: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            # جستجوی URL در لیست منابع
            sources = result.get('sources', [])
            print(f"تعداد کل منابع: {len(sources)}")
            
            found = False
            for source in sources:
                source_url = source.get('url', '')
                if source_url == url:
                    found = True
                    chunks = source.get('chunks', [])
                    print(f"✅ URL یافت شد!")
                    print(f"تعداد قطعات: {len(chunks)}")
                    
                    if chunks:
                        sample = chunks[0]
                        print(f"\nنمونه قطعه:")
                        print(f"متن: {sample.get('text', '')[:150]}...")
                        print(f"متادیتا: {json.dumps(sample.get('metadata', {}), ensure_ascii=False)}")
                    
                    return source
            
            if not found:
                print(f"❌ URL در لیست منابع داده یافت نشد!")
                
                # نمایش لیست URL های موجود
                print("\nلیست URL های موجود:")
                for i, source in enumerate(sources, 1):
                    print(f"{i}. {source.get('url', '')}")
                
                # بررسی URL های مشابه
                similar_urls = []
                target_url_normalized = url.rstrip('/').lower()
                for source in sources:
                    source_url = source.get('url', '')
                    source_normalized = source_url.rstrip('/').lower()
                    if source_url and (target_url_normalized in source_normalized or source_normalized in target_url_normalized):
                        similar_urls.append(source_url)
                
                if similar_urls:
                    print("\nURL های مشابه یافت شده:")
                    for i, similar_url in enumerate(similar_urls, 1):
                        print(f"{i}. {similar_url}")
                    print("\n⚠️ احتمالاً URL با فرمت متفاوتی ذخیره شده است.")
                
            return None
        else:
            print(f"خطا: {response.text}")
            return None
    except Exception as e:
        print(f"خطا در ارسال درخواست: {str(e)}")
        return None

if __name__ == "__main__":
    # آدرس URL برای تست
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("لطفاً URL مورد نظر را وارد کنید: ")
    
    # اضافه کردن URL به پایگاه دانش
    add_result = test_add_url_knowledge(url)
    
    if add_result and add_result.get('document_count', 0) > 0:
        print("\nصبر کنید تا سیستم URL را پردازش کند...")
        time.sleep(2)  # مکث کوتاه
        
        # بررسی وجود URL در لیست منابع داده
        check_data_source(url) 