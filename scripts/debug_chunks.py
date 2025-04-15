import sys
import os
from pathlib import Path

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# لود کردن متغیرهای محیطی از .env
from dotenv import load_dotenv
load_dotenv()

from database.vector_store import VectorStore

def debug_chunks():
    """
    بررسی دقیق چانک‌های موجود در پایگاه داده و URL‌های آنها
    """
    print("شروع دیباگ چانک‌های پایگاه داده...")
    
    # ایجاد یک نمونه از VectorStore
    vector_store = VectorStore()
    
    # دریافت تمام اسناد
    all_docs = vector_store.get_all_documents()
    print(f"تعداد کل اسناد: {len(all_docs)}\n")
    
    # استخراج تمام URL‌های یکتا
    sources = {}
    for doc in all_docs:
        source = doc['metadata'].get('source', 'unknown')
        if source not in sources:
            sources[source] = []
        sources[source].append(doc)
    
    print(f"تعداد منابع یکتا: {len(sources)}\n")
    
    # بررسی هر منبع
    for source, docs in sources.items():
        print(f"منبع: {source}")
        print(f"تعداد چانک‌ها: {len(docs)}")
        
        for i, doc in enumerate(docs):
            print(f"  چانک {i}:")
            print(f"    ID: {doc.get('id', 'ندارد')}")
            print(f"    متن: {doc['text'][:100]}..." if len(doc['text']) > 100 else f"    متن: {doc['text']}")
            metadata_str = ", ".join([f"{k}: {v}" for k, v in doc['metadata'].items() if k != 'source'])
            print(f"    متادیتا: {metadata_str}")
            print()
        
        print("=" * 80)
    
    print("\nدیباگ چانک‌ها به پایان رسید.")

def test_url_exact_match(url_to_test):
    """
    بررسی تطابق دقیق URL
    
    Args:
        url_to_test: URL که می‌خواهیم بررسی کنیم
    """
    print(f"\nبررسی تطابق دقیق برای URL: {url_to_test}")
    
    # ایجاد یک نمونه از VectorStore
    vector_store = VectorStore()
    
    # دریافت تمام اسناد
    all_docs = vector_store.get_all_documents()
    
    # بررسی URL‌ها با تطابق دقیق
    exact_matches = [doc for doc in all_docs if doc['metadata'].get('source', '') == url_to_test]
    
    print(f"تعداد چانک‌های با تطابق دقیق: {len(exact_matches)}")
    if exact_matches:
        for i, doc in enumerate(exact_matches):
            print(f"  چانک {i}:")
            print(f"    ID: {doc.get('id', 'ندارد')}")
            print(f"    متن: {doc['text'][:100]}..." if len(doc['text']) > 100 else f"    متن: {doc['text']}")
    
    # بررسی URL‌های مشابه
    similar_matches = [doc for doc in all_docs if url_to_test in doc['metadata'].get('source', '')]
    if len(similar_matches) > len(exact_matches):
        print(f"\nتعداد چانک‌های با URL مشابه: {len(similar_matches)}")
        unique_similar_sources = set([doc['metadata'].get('source', '') for doc in similar_matches])
        print(f"URL‌های مشابه:")
        for source in unique_similar_sources:
            print(f"  {source}")
    
    print("\nبررسی تطابق دقیق به پایان رسید.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='دیباگ چانک‌های پایگاه داده')
    parser.add_argument('--url', help='بررسی یک URL خاص')
    
    args = parser.parse_args()
    
    if args.url:
        test_url_exact_match(args.url)
    else:
        debug_chunks() 