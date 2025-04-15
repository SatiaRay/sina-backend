import sys
import os
from pathlib import Path
import json

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# لود کردن متغیرهای محیطی از .env
from dotenv import load_dotenv
load_dotenv()

from database.vector_store import VectorStore

def check_url_in_db(url):
    """
    بررسی وجود یک URL در پایگاه دانش
    
    Args:
        url: آدرس URL برای جستجو
    """
    print(f"=== بررسی وجود URL در پایگاه دانش ===")
    print(f"URL مورد جستجو: {url}")
    
    try:
        # ایجاد نمونه از VectorStore
        vector_store = VectorStore()
        
        # دریافت تمام اسناد
        docs = vector_store.get_all_documents()
        print(f"تعداد کل اسناد در پایگاه دانش: {len(docs)}")
        
        # فیلتر کردن براساس URL
        found_docs = []
        unique_sources = set()
        for i, doc in enumerate(docs):
            source = doc['metadata'].get('source', '')
            unique_sources.add(source)
            if source == url:
                found_docs.append(doc)
        
        if found_docs:
            print(f"✅ URL مورد نظر در پایگاه دانش یافت شد!")
            print(f"تعداد اسناد مرتبط با این URL: {len(found_docs)}")
            
            # نمایش نمونه‌ای از داده‌ها
            if len(found_docs) > 0:
                sample = found_docs[0]
                print("\nنمونه سند:")
                print(f"متن: {sample['text'][:150]}...")
                print(f"متادیتا: {json.dumps(sample['metadata'], ensure_ascii=False)}")
        else:
            print(f"❌ URL مورد نظر در پایگاه دانش یافت نشد!")
            
            # نمایش لیست منابع موجود
            print("\nلیست منابع موجود در پایگاه دانش:")
            for i, source in enumerate(sorted(unique_sources), 1):
                if source:  # فقط منابع غیرخالی را نمایش بده
                    print(f"{i}. {source}")
            
            # بررسی URL مشابه
            similar_urls = []
            target_url_normalized = url.rstrip('/').lower()
            for source in unique_sources:
                source_normalized = source.rstrip('/').lower()
                if source and (target_url_normalized in source_normalized or source_normalized in target_url_normalized):
                    similar_urls.append(source)
                    
            if similar_urls:
                print("\nURL‌های مشابه یافت شده:")
                for i, similar_url in enumerate(similar_urls, 1):
                    print(f"{i}. {similar_url}")
                print("\n⚠️ احتمالاً URL با فرمت متفاوتی ذخیره شده است.")
            
        return found_docs
            
    except Exception as e:
        print(f"خطا در بررسی URL: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    # آدرس URL برای جستجو
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("لطفاً URL مورد نظر را وارد کنید: ")
    
    check_url_in_db(url) 