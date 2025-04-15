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

def test_update_knowledge(url):
    """
    تست به‌روزرسانی دانش با خزش مجدد یک URL
    
    Args:
        url: آدرس URL که باید مجدداً خزش شود
    """
    endpoint = f"{API_URL}/update_knowledge"
    payload = {
        "url": url
    }
    
    print(f"ارسال درخواست به {endpoint}")
    print(f"داده‌های ارسالی: {json.dumps(payload, ensure_ascii=False)}")
    
    try:
        response = requests.post(endpoint, json=payload)
        
        print(f"کد وضعیت: {response.status_code}")
        
        if response.status_code == 200:
            print("پاسخ:")
            print(json.dumps(response.json(), ensure_ascii=False, indent=2))
            
            result = response.json()
            print(f"تعداد {result.get('document_count', 0)} سند استخراج شد.")
            print(f"تعداد {result.get('deleted_count', 0)} سند قبلی حذف شد.")
            return True
        else:
            print(f"خطا: {response.text}")
            return False
    except Exception as e:
        print(f"خطا در ارسال درخواست: {str(e)}")
        return False

def check_url_chunks(url):
    """
    بررسی چانک‌های مربوط به یک URL در پایگاه داده
    
    Args:
        url: آدرس URL برای بررسی
    """
    print(f"\n=== بررسی چانک‌های URL: {url} در پایگاه داده ===")
    
    try:
        encoded_url = requests.utils.quote(url)
        endpoint = f"{API_URL}/data_sources/{encoded_url}/chunks"
        
        print(f"ارسال درخواست به {endpoint}")
        
        response = requests.get(endpoint)
        
        if response.status_code == 200:
            chunks = response.json()
            print(f"\nتعداد چانک‌ها: {len(chunks)}")
            
            for i, chunk in enumerate(chunks[:5]):  # فقط 5 چانک اول
                print(f"\nچانک {i}:")
                print(f"متن: {chunk.get('text', '')[:150]}...")
                metadata = chunk.get('metadata', {})
                print(f"منبع: {metadata.get('source', '')}")
                print(f"به‌روزرسانی شده: {metadata.get('updated', 'false')}")
                
            if len(chunks) > 5:
                print(f"\n... و {len(chunks) - 5} چانک دیگر")
                
            return chunks
        else:
            print(f"\nخطا در دریافت چانک‌ها: {response.status_code}")
            print(f"پیام خطا: {response.text}")
            return None
    except Exception as e:
        print(f"خطا در ارسال درخواست: {str(e)}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='تست API به‌روزرسانی دانش')
    parser.add_argument('--url', required=True, help='آدرس URL برای به‌روزرسانی')
    parser.add_argument('--check-only', action='store_true', help='فقط بررسی چانک‌های موجود بدون به‌روزرسانی')
    
    args = parser.parse_args()
    
    if args.check_only:
        check_url_chunks(args.url)
    else:
        # ابتدا چانک‌های موجود را بررسی می‌کنیم
        print("بررسی چانک‌های موجود قبل از به‌روزرسانی...")
        check_url_chunks(args.url)
        
        # سپس به‌روزرسانی را انجام می‌دهیم
        test_update_knowledge(args.url)
        
        # و در نهایت چانک‌های به‌روزرسانی شده را بررسی می‌کنیم
        print("\nبررسی چانک‌های به‌روزرسانی شده...")
        check_url_chunks(args.url)

    # اگر می‌خواهید URL دیگری را تست کنید، می‌توانید از ورودی کاربر استفاده کنید
    try_another = input("\nآیا می‌خواهید URL دیگری را تست کنید؟ (بله/خیر): ")
    if try_another.lower() in ['بله', 'y', 'yes']:
        custom_url = input("لطفاً URL مورد نظر را وارد کنید: ")
        if custom_url:
            print(f"\n=== تست به‌روزرسانی دانش برای URL سفارشی ===")
            test_update_knowledge(custom_url) 