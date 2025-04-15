import sys
import os
from pathlib import Path
import requests
import json

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

def test_add_plaintext():
    """
    تست افزودن متن ساده به پایگاه دانش
    
    این اسکریپت یک درخواست به API ارسال می‌کند تا متن ساده را به پایگاه دانش اضافه کند
    """
    url = "http://localhost:8001/api/add_plaintext"
    
    data = {
        "text": "ساتیا یک پلتفرم مدیریت منابع است که به کسب و کارها کمک می‌کند تا منابع خود را به صورت بهینه مدیریت کنند. این پلتفرم امکان مدیریت مالی، منابع انسانی و فرآیندهای کسب و کار را فراهم می‌کند.",
        "title": "درباره ساتیا - تست",
        "source": "تست API"
    }
    
    try:
        print(f"ارسال درخواست به {url}...")
        print(f"داده ارسالی: {json.dumps(data, ensure_ascii=False)}")
        
        response = requests.post(url, json=data)
        
        print(f"کد وضعیت: {response.status_code}")
        
        if response.status_code == 200:
            print("پاسخ:")
            print(json.dumps(response.json(), ensure_ascii=False, indent=2))
            return True
        else:
            print(f"خطا: {response.text}")
            return False
    except Exception as e:
        print(f"خطا در ارسال درخواست: {str(e)}")
        return False

def test_all_knowledge():
    """
    تست خواندن تمام داده‌های یک منبع خاص
    """
    url = "http://localhost:8001/api/all_knowledge"
    
    data = {
        "url": "تست API"  # همان منبعی که در تست قبلی استفاده شد
    }
    
    try:
        print(f"\nارسال درخواست به {url}...")
        print(f"داده ارسالی: {json.dumps(data, ensure_ascii=False)}")
        
        response = requests.post(url, json=data)
        
        print(f"کد وضعیت: {response.status_code}")
        
        if response.status_code == 200:
            print("پاسخ:")
            print(json.dumps(response.json(), ensure_ascii=False, indent=2))
            
            # بررسی تعداد اسناد بازیابی شده
            result = response.json()
            if result.get('documents') and len(result['documents']) > 0:
                print(f"تعداد {len(result['documents'])} سند بازیابی شد.")
                return True
            else:
                print("هیچ سندی بازیابی نشد!")
                return False
        else:
            print(f"خطا: {response.text}")
            return False
    except Exception as e:
        print(f"خطا در ارسال درخواست: {str(e)}")
        return False

if __name__ == "__main__":
    print("=== تست افزودن متن ساده به پایگاه دانش ===")
    add_success = test_add_plaintext()
    
    if add_success:
        print("\n=== تست خواندن داده‌های اضافه شده ===")
        test_all_knowledge() 