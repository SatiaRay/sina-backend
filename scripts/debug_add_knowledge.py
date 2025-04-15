import sys
from pathlib import Path
import json
from crawler.main import run_spider
from models.text_processor import TextProcessor
from database.vector_store import VectorStore

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

def debug_add_knowledge(url):
    print("1. شروع استخراج داده‌ها...")
    knowledge_items = run_spider(url)
    print(f"تعداد اسناد استخراج شده: {len(knowledge_items)}")
    
    print("\n2. پردازش متن‌ها...")
    text_processor = TextProcessor()
    processed_docs = text_processor.process_batch(knowledge_items)
    print(f"تعداد اسناد پردازش شده: {len(processed_docs)}")
    
    print("\n3. ذخیره در ChromaDB...")
    vector_store = VectorStore()
    vector_store.add_documents(processed_docs)
    
    print("\n4. بررسی داده‌های ذخیره شده...")
    documents = vector_store.get_all_documents()
    print(f"تعداد اسناد در ChromaDB: {len(documents)}")
    
    # ذخیره لاگ در فایل
    with open('debug_log.json', 'w', encoding='utf-8') as f:
        json.dump({
            'extracted': knowledge_items,
            'processed': processed_docs,
            'stored': documents
        }, f, ensure_ascii=False, indent=2)
    
    print("\nلاگ‌ها در فایل debug_log.json ذخیره شدند.")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        url = sys.argv[1]
        debug_add_knowledge(url)
    else:
        print("لطفا URL را به عنوان آرگومان وارد کنید.") 