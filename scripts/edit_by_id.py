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
from models.rag import RAGSystem
from models.text_processor import TextProcessor

def list_chunks_by_url(url):
    """
    نمایش چانک‌های یک URL خاص با شناسه‌های آنها
    
    Args:
        url: آدرس منبع داده
    """
    vector_store = VectorStore()
    
    # دریافت تمام اسناد
    all_docs = vector_store.get_all_documents()
    
    # فیلتر کردن چانک‌های مربوط به URL
    url_chunks = [doc for doc in all_docs if doc['metadata'].get('source', '') == url]
    
    print(f"تعداد چانک‌های مربوط به URL '{url}': {len(url_chunks)}")
    for i, chunk in enumerate(url_chunks):
        print(f"\nچانک شماره {i}:")
        print(f"  شناسه: {chunk.get('id', 'نامشخص')}")
        print(f"  متن: {chunk['text'][:100]}..." if len(chunk['text']) > 100 else f"  متن: {chunk['text']}")
    
    return url_chunks

def edit_chunk_by_id(chunk_id, new_text):
    """
    ویرایش چانک با استفاده از شناسه مستقیم
    
    Args:
        chunk_id: شناسه چانک
        new_text: متن جدید برای جایگزینی
    """
    vector_store = VectorStore()
    text_processor = TextProcessor()
    rag_system = RAGSystem()
    
    # دریافت تمام اسناد
    all_docs = vector_store.get_all_documents()
    
    # پیدا کردن چانک مورد نظر
    target_chunk = None
    for doc in all_docs:
        if doc.get('id') == chunk_id:
            target_chunk = doc
            break
    
    if not target_chunk:
        print(f"خطا: چانک با شناسه '{chunk_id}' یافت نشد.")
        return False
    
    print(f"متن فعلی چانک: {target_chunk['text'][:100]}...")
    
    # ساخت سند جدید با متن جدید
    updated_doc = {
        "text": new_text,
        "metadata": target_chunk['metadata']
    }
    
    try:
        # حذف چانک قدیمی
        vector_store.delete_document(chunk_id)
        print(f"چانک قدیمی با شناسه '{chunk_id}' حذف شد.")
        
        # پردازش و افزودن چانک جدید
        processed_docs = text_processor.process_batch([updated_doc])
        success = rag_system.update_knowledge_base(processed_docs)
        
        if success:
            print("چانک با موفقیت به‌روزرسانی شد.")
        else:
            print("خطا در به‌روزرسانی چانک.")
        
        return success
    except Exception as e:
        print(f"خطا در ویرایش چانک: {str(e)}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='ویرایش چانک با استفاده از شناسه مستقیم')
    parser.add_argument('--url', help='URL برای نمایش چانک‌ها و شناسه‌های آنها')
    parser.add_argument('--id', help='شناسه چانک برای ویرایش')
    parser.add_argument('--text', help='متن جدید برای جایگزینی')
    
    args = parser.parse_args()
    
    if args.url:
        list_chunks_by_url(args.url)
    
    if args.id and args.text:
        edit_chunk_by_id(args.id, args.text) 