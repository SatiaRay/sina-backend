import sys
import os
from pathlib import Path
import requests
import json
import time
import argparse

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# لود کردن متغیرهای محیطی از .env
from dotenv import load_dotenv
load_dotenv()

API_URL = os.getenv('APP_URL', 'http://localhost:8001')
MAX_RETRIES = 5
RETRY_DELAY = 3  # ثانیه

def test_add_url_knowledge(url, verbose=True):
    """
    تست افزودن URL به پایگاه دانش
    
    Args:
        url: آدرس URL برای افزودن به پایگاه دانش
        verbose: نمایش جزئیات بیشتر
        
    Returns:
        dict: نتیجه درخواست یا None در صورت خطا
    """
    if verbose:
        print(f"=== تست افزودن URL به پایگاه دانش ===")
        print(f"URL: {url}")
    
    # حذف اطلاعات قبلی مربوط به این URL از ChromaDB
    if verbose:
        print(f"\n1. حذف داده‌های قبلی مربوط به این URL (اگر وجود داشته باشد)...")
    
    try:
        delete_endpoint = f"{API_URL}/update_knowledge"
        delete_payload = {"url": url}
        delete_response = requests.post(delete_endpoint, json=delete_payload)
        
        if verbose:
            if delete_response.status_code == 200:
                delete_result = delete_response.json()
                deleted_count = delete_result.get('deleted_count', 0)
                print(f"   ✓ {deleted_count} سند قبلی حذف شد")
            else:
                print(f"   ! خطا در حذف داده‌های قبلی: {delete_response.status_code}")
    except Exception as e:
        if verbose:
            print(f"   ! استثنا در حذف داده‌های قبلی: {str(e)}")
    
    # افزودن URL به پایگاه دانش
    if verbose:
        print(f"\n2. افزودن URL به پایگاه دانش...")
    
    endpoint = f"{API_URL}/add_knowledge"
    payload = {"url": url}
    
    try:
        if verbose:
            print(f"   ارسال درخواست به {endpoint}...")
        
        response = requests.post(endpoint, json=payload)
        
        if verbose:
            print(f"   کد وضعیت: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            if verbose:
                print("   پاسخ:")
                print(f"   {json.dumps(result, ensure_ascii=False, indent=2)}")
                print(f"   ✓ تعداد {result.get('document_count', 0)} سند اضافه شد")
            
            return result
        else:
            if verbose:
                print(f"   ✗ خطا: {response.text}")
            return None
    except Exception as e:
        if verbose:
            print(f"   ✗ خطا در ارسال درخواست: {str(e)}")
        return None

def check_data_source(url, verbose=True, retry=True):
    """
    بررسی وجود URL در لیست منابع داده
    
    Args:
        url: آدرس URL برای جستجو
        verbose: نمایش جزئیات بیشتر
        retry: تلاش مجدد در صورت عدم یافتن URL
        
    Returns:
        dict: اطلاعات منبع داده یا None در صورت عدم وجود
    """
    if verbose:
        print(f"\n=== بررسی وجود URL در لیست منابع داده ===")
        print(f"URL: {url}")
    
    endpoint = f"{API_URL}/data_sources"
    
    retries = 0
    while retries <= MAX_RETRIES:
        try:
            if verbose and retries > 0:
                print(f"تلاش {retries} از {MAX_RETRIES}...")
            
            if verbose and retries == 0:
                print(f"ارسال درخواست به {endpoint}...")
            
            response = requests.get(endpoint)
            
            if verbose and retries == 0:
                print(f"کد وضعیت: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                # جستجوی URL در لیست منابع
                sources = result.get('sources', [])
                
                if verbose and retries == 0:
                    print(f"تعداد کل منابع: {len(sources)}")
                
                found = False
                for source in sources:
                    source_url = source.get('url', '')
                    if source_url == url:
                        found = True
                        chunks = source.get('chunks', [])
                        
                        if verbose:
                            print(f"✅ URL یافت شد!")
                            print(f"تعداد قطعات: {len(chunks)}")
                            
                            if chunks:
                                sample = chunks[0]
                                print(f"\nنمونه قطعه:")
                                print(f"متن: {sample.get('text', '')[:150]}...")
                                print(f"متادیتا: {json.dumps(sample.get('metadata', {}), ensure_ascii=False)}")
                        
                        return source
                
                if not found:
                    if verbose and retries == 0:
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
                            source_normalized = source_url.rstrip('/').lower() if source_url else ""
                            if source_url and (target_url_normalized in source_normalized or source_normalized in target_url_normalized):
                                similar_urls.append(source_url)
                        
                        if similar_urls:
                            print("\nURL های مشابه یافت شده:")
                            for i, similar_url in enumerate(similar_urls, 1):
                                print(f"{i}. {similar_url}")
                            print("\n⚠️ احتمالاً URL با فرمت متفاوتی ذخیره شده است.")
                    
                    # اگر نیاز به تلاش مجدد نیست یا به حداکثر تعداد تلاش رسیده‌ایم
                    if not retry or retries >= MAX_RETRIES:
                        return None
                    
                    # انتظار کوتاه قبل از تلاش مجدد
                    if verbose:
                        print(f"\nانتظار {RETRY_DELAY} ثانیه قبل از تلاش مجدد...")
                    time.sleep(RETRY_DELAY)
                    retries += 1
                else:
                    # URL پیدا شد
                    break
            else:
                if verbose:
                    print(f"خطا: {response.text}")
                return None
        except Exception as e:
            if verbose:
                print(f"خطا در ارسال درخواست: {str(e)}")
            return None
    
    return None

def check_direct_in_vector_store(url, verbose=True):
    """
    بررسی مستقیم وجود URL در VectorStore
    
    Args:
        url: آدرس URL برای جستجو
        verbose: نمایش جزئیات بیشتر
    
    Returns:
        list: لیست اسناد یافت شده یا لیست خالی
    """
    if verbose:
        print(f"\n=== بررسی مستقیم وجود URL در پایگاه داده وکتور ===")
        print(f"URL: {url}")
    
    endpoint = f"{API_URL}/api/all_knowledge"
    payload = {"url": url}
    
    try:
        if verbose:
            print(f"ارسال درخواست به {endpoint}...")
        
        response = requests.post(endpoint, json=payload)
        
        if verbose:
            print(f"کد وضعیت: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            documents = result.get('documents', [])
            count = result.get('count', 0)
            
            if verbose:
                print(f"تعداد اسناد یافت شده: {count}")
                
                if count > 0:
                    print(f"✅ URL در پایگاه داده وکتور یافت شد!")
                    
                    # نمایش نمونه‌ای از اسناد
                    if documents:
                        sample = documents[0]
                        print(f"\nنمونه سند:")
                        print(f"متن: {sample.get('text', '')[:150]}...")
                        print(f"متادیتا: {json.dumps(sample.get('metadata', {}), ensure_ascii=False)}")
                else:
                    print(f"❌ URL در پایگاه داده وکتور یافت نشد!")
            
            return documents
        else:
            if verbose:
                print(f"خطا: {response.text}")
            return []
    except Exception as e:
        if verbose:
            print(f"خطا در ارسال درخواست: {str(e)}")
        return []

def test_and_verify(url, bypass_add=False):
    """
    تست کامل افزودن URL و بررسی آن
    
    Args:
        url: آدرس URL برای تست
        bypass_add: در صورت True، مرحله افزودن URL را رد می‌کند
        
    Returns:
        bool: آیا URL با موفقیت اضافه و بررسی شد
    """
    print(f"===== شروع تست کامل برای URL: {url} =====")
    
    # افزودن URL به پایگاه دانش
    if not bypass_add:
        add_result = test_add_url_knowledge(url)
        if not add_result or add_result.get('document_count', 0) == 0:
            print("❌ افزودن URL به پایگاه دانش ناموفق بود!")
            return False
    
    # صبر برای پردازش
    print("\nدر حال صبر برای پردازش داده (5 ثانیه)...")
    time.sleep(5)
    
    # بررسی در لیست منابع داده
    data_source = check_data_source(url)
    
    # بررسی مستقیم در پایگاه داده وکتور
    vector_docs = check_direct_in_vector_store(url)
    
    # نتیجه نهایی
    if data_source:
        print("\n✅ تست موفق: URL در لیست منابع داده یافت شد!")
        return True
    elif vector_docs:
        print("\n⚠️ تست نیمه‌موفق: URL در پایگاه داده وکتور یافت شد اما در لیست منابع داده نیست!")
        print("   این مشکل احتمالاً مربوط به نحوه نمایش منابع داده است، نه ذخیره‌سازی داده‌ها.")
        return True
    else:
        print("\n❌ تست ناموفق: URL در هیچ جایی یافت نشد!")
        
        # پیشنهاد استفاده از روش جایگزین
        print("\nپیشنهاد: استفاده از API add_plaintext برای افزودن مستقیم متن:")
        print(f"""
curl -X 'POST' \\
  '{API_URL}/api/add_plaintext' \\
  -H 'accept: application/json' \\
  -H 'Content-Type: application/json' \\
  -d '{{
  "text": "این یک متن تست برای URL {url} است.",
  "title": "تست URL",
  "source": "{url}"
}}'
        """)
        return False

def main():
    parser = argparse.ArgumentParser(description='تست افزودن URL به پایگاه دانش و بررسی آن')
    parser.add_argument('url', nargs='?', help='آدرس URL برای تست')
    parser.add_argument('--check-only', action='store_true', help='فقط بررسی، بدون افزودن URL')
    parser.add_argument('--max-retries', type=int, default=5, help='حداکثر تعداد تلاش برای بررسی')
    
    args = parser.parse_args()
    
    global MAX_RETRIES
    MAX_RETRIES = args.max_retries
    
    # اگر URL از خط فرمان داده نشده، از کاربر بخواه
    if not args.url:
        args.url = input("لطفاً URL مورد نظر را وارد کنید: ")
    
    # اجرای تست
    test_and_verify(args.url, bypass_add=args.check_only)

if __name__ == "__main__":
    main() 