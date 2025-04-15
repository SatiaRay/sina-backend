import requests
import sys
from pathlib import Path
import time

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

def test_add_knowledge():
    # آدرس API
    base_url = "http://localhost:8001"
    
    # تست افزودن دانش
    print("در حال تست متد add_knowledge...")
    
    # لیست URL‌هایی که می‌خواهیم اضافه کنیم
    urls_to_add = [
        "https://fa.wikipedia.org/wiki/%D9%87%D9%88%D8%B4_%D9%85%D8%B5%D9%86%D9%88%D8%B9%DB%8C",
        "https://fa.wikipedia.org/wiki/%DB%8C%D8%A7%D8%AF%DA%AF%DB%8C%D8%B1%DB%8C_%D8%B9%D9%85%DB%8C%D9%82"
    ]
    
    for url in urls_to_add:
        print(f"\nدر حال استخراج و افزودن دانش از URL: {url}")
        
        try:
            # ارسال درخواست به API
            response = requests.post(
                f"{base_url}/add_knowledge",
                json={"url": url},
                headers={"Content-Type": "application/json"}
            )
            
            # بررسی پاسخ
            if response.status_code == 200:
                result = response.json()
                print(f"✅ عملیات موفقیت‌آمیز: {result['message']}")
            else:
                print(f"❌ خطا: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ خطای ارتباط با API: {str(e)}")
    
    # تست اینکه آیا دانش به درستی اضافه شده است
    print("\nدر حال بررسی اینکه آیا دانش به درستی اضافه شده است...")
    
    # لیست سوالات تستی
    test_questions = [
        "هوش مصنوعی چیست؟",
        "یادگیری عمیق چگونه کار می‌کند؟"
    ]
    
    for question in test_questions:
        print(f"\nدر حال پرسیدن سوال: {question}")
        
        try:
            # ارسال درخواست به API
            response = requests.post(
                f"{base_url}/askme",
                json={"question": question},
                headers={"Content-Type": "application/json"}
            )
            
            # بررسی پاسخ
            if response.status_code == 200:
                result = response.json()
                print(f"پاسخ: {result['answer'][:150]}...")
                
                if len(result['sources']) > 0:
                    print(f"تعداد منابع: {len(result['sources'])}")
                    print("منابع استفاده شده:")
                    for source in result['sources'][:2]:  # نمایش حداکثر 2 منبع
                        print(f"- {source['metadata'].get('source', 'نامشخص')}")
                else:
                    print("❌ هیچ منبعی در پاسخ یافت نشد.")
            else:
                print(f"❌ خطا: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ خطای ارتباط با API: {str(e)}")
        
        # کمی صبر می‌کنیم تا API بیش از حد بارگذاری نشود
        time.sleep(1)
        
    print("\nتست به پایان رسید.")

if __name__ == "__main__":
    test_add_knowledge() 