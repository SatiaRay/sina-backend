import os
from pathlib import Path
from dotenv import load_dotenv
from crawler.main import run_spider
from models.text_processor import TextProcessor
from database.vector_store import VectorStore
from util.constants import CHROMA_PERSIST_DIRECTORY, DATA_DIR
import json

load_dotenv()

def setup_system():
    # ایجاد پوشه‌های مورد نیاز
    Path(DATA_DIR).mkdir(exist_ok=True)
    Path(CHROMA_PERSIST_DIRECTORY).mkdir(exist_ok=True)
    
    # استخراج داده‌ها
    print("در حال استخراج داده‌ها از وبسایت...")
    run_spider()
    
    # پردازش داده‌ها
    print("در حال پردازش داده‌ها...")
    text_processor = TextProcessor()
    vector_store = VectorStore()
    
    # خواندن داده‌های استخراج شده
    data_files = list(Path("data").glob("*.json"))
    all_documents = []
    
    for file in data_files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    all_documents.extend(data)
                else:
                    all_documents.append(data)
            print(f"فایل {file} با موفقیت خوانده شد")
        except json.JSONDecodeError as e:
            print(f"خطا در خواندن فایل {file}: {e}")
            continue
        except Exception as e:
            print(f"خطای ناشناخته در خواندن فایل {file}: {e}")
            continue
    
    if not all_documents:
        print("هشدار: هیچ داده‌ای برای پردازش یافت نشد!")
        return
    
    print(f"تعداد اسناد یافت شده: {len(all_documents)}")
    
    # پردازش و ذخیره‌سازی
    try:
        processed_docs = text_processor.process_batch(all_documents)
        print(f"تعداد اسناد پردازش شده: {len(processed_docs)}")
        
        if processed_docs:
            vector_store.add_documents(processed_docs)
            print("سیستم با موفقیت راه‌اندازی شد!")
        else:
            print("هشدار: هیچ سند پردازش شده‌ای برای ذخیره وجود ندارد!")
    except Exception as e:
        print(f"خطا در پردازش اسناد: {e}")

if __name__ == "__main__":
    setup_system() 