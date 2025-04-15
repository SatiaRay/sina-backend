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

def test_update_knowledge():
    """
    تست ساده اندپوینت update_knowledge با فرمت جدید
    """
    url = f"{API_URL}/update_knowledge"
    
    # این دقیقا همان فرمت مثال در مستندات است
    data = {
        "url": "https://www.satia.co/blog"
    }
    
    print(f"ارسال درخواست به {url}...")
    print(f"داده ارسالی: {json.dumps(data, ensure_ascii=False)}")
    
    try:
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

if __name__ == "__main__":
    test_update_knowledge() 