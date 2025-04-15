import sys
from pathlib import Path
import json

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

def check_crawled_data():
    # خواندن داده‌های استخراج شده
    data_file = Path('data/crawled_data.json')
    if data_file.exists():
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"تعداد اسناد استخراج شده: {len(data)}")
            for i, doc in enumerate(data, 1):
                print(f"\nسند {i}:")
                print(f"عنوان: {doc.get('title', 'بدون عنوان')}")
                print(f"URL: {doc.get('url', 'بدون URL')}")
                print(f"محتوا: {doc.get('content', 'بدون محتوا')[:200]}...")
    else:
        print("فایل داده‌های استخراج شده یافت نشد!")

if __name__ == '__main__':
    check_crawled_data() 