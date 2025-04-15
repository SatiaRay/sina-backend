import sys
import os
from pathlib import Path
import traceback

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# لود کردن متغیرهای محیطی از .env
from dotenv import load_dotenv
load_dotenv()

from database.vector_store import VectorStore
from models.text_processor import TextProcessor
from models.rag import RAGSystem

def test_get_all_documents():
    """تست متد دریافت همه اسناد"""
    print("\n=== تست متد get_all_documents ===")
    
    vector_store = VectorStore()
    docs = vector_store.get_all_documents()
    
    print(f"تعداد کل اسناد: {len(docs)}")
    if docs:
        print("نمونه اولین سند:")
        print(f"  ID: {docs[0].get('id', 'نامشخص')}")
        print(f"  متن: {docs[0]['text'][:100]}...")
        print(f"  متادیتا: {docs[0]['metadata']}")
    
    return docs

def test_delete_document(doc_id):
    """تست متد حذف سند"""
    print(f"\n=== تست متد delete_document با شناسه '{doc_id}' ===")
    
    vector_store = VectorStore()
    
    # بررسی وجود سند قبل از حذف
    docs_before = vector_store.get_all_documents()
    target_doc = None
    for doc in docs_before:
        if doc.get('id') == doc_id:
            target_doc = doc
            break
    
    if target_doc:
        print(f"سند با شناسه '{doc_id}' یافت شد:")
        print(f"  متن: {target_doc['text'][:100]}...")
        
        try:
            # تلاش برای حذف سند
            print("در حال حذف سند...")
            vector_store.delete_document(doc_id)
            print("عملیات حذف کامل شد")
            
            # بررسی وجود سند بعد از حذف
            docs_after = vector_store.get_all_documents()
            doc_exists = any(doc.get('id') == doc_id for doc in docs_after)
            
            if doc_exists:
                print(f"خطا: سند با شناسه '{doc_id}' هنوز وجود دارد!")
            else:
                print(f"موفقیت: سند با شناسه '{doc_id}' با موفقیت حذف شد")
                
            print(f"تعداد اسناد قبل از حذف: {len(docs_before)}")
            print(f"تعداد اسناد بعد از حذف: {len(docs_after)}")
            
            return not doc_exists
        except Exception as e:
            print(f"خطا در حذف سند: {str(e)}")
            traceback.print_exc()
            return False
    else:
        print(f"سند با شناسه '{doc_id}' یافت نشد!")
        return False

def test_add_document(text, metadata=None):
    """تست متد افزودن سند جدید"""
    print(f"\n=== تست متد add_documents با متن '{text[:50]}...' ===")
    
    if metadata is None:
        metadata = {
            "source": "test_source",
            "title": "Test Document",
            "created_at": "2023-01-01T00:00:00"
        }
    
    vector_store = VectorStore()
    text_processor = TextProcessor()
    rag_system = RAGSystem()
    
    # بررسی تعداد اسناد قبل از افزودن
    docs_before = vector_store.get_all_documents()
    print(f"تعداد اسناد قبل از افزودن: {len(docs_before)}")
    
    try:
        # ایجاد سند
        doc = {
            "text": text,
            "metadata": metadata
        }
        
        # پردازش سند
        print("در حال پردازش سند...")
        processed_docs = text_processor.process_batch([doc])
        print(f"تعداد اسناد پردازش شده: {len(processed_docs)}")
        if processed_docs:
            print(f"نمونه سند پردازش شده: {processed_docs[0]}")
        
        # افزودن به پایگاه دانش
        print("در حال افزودن سند به پایگاه دانش...")
        success = rag_system.update_knowledge_base(processed_docs)
        print(f"نتیجه افزودن سند: {success}")
        
        # بررسی تعداد اسناد بعد از افزودن
        docs_after = vector_store.get_all_documents()
        print(f"تعداد اسناد بعد از افزودن: {len(docs_after)}")
        
        return success and len(docs_after) > len(docs_before)
    except Exception as e:
        print(f"خطا در افزودن سند: {str(e)}")
        traceback.print_exc()
        return False

def test_update_flow(doc_id, new_text):
    """تست جریان کامل به‌روزرسانی یک سند"""
    print(f"\n=== تست جریان کامل به‌روزرسانی سند با شناسه '{doc_id}' ===")
    
    vector_store = VectorStore()
    
    # بررسی وجود سند قبل از به‌روزرسانی
    docs = vector_store.get_all_documents()
    target_doc = None
    for doc in docs:
        if doc.get('id') == doc_id:
            target_doc = doc
            break
    
    if not target_doc:
        print(f"سند با شناسه '{doc_id}' یافت نشد!")
        return False
    
    print(f"سند قبل از به‌روزرسانی:")
    print(f"  متن: {target_doc['text'][:100]}...")
    print(f"  متادیتا: {target_doc['metadata']}")
    
    # حذف سند قدیمی
    delete_success = test_delete_document(doc_id)
    if not delete_success:
        print("خطا در حذف سند قدیمی. ادامه فرآیند به‌روزرسانی...")
    
    # افزودن سند جدید با همان متادیتا
    add_success = test_add_document(new_text, target_doc['metadata'])
    
    if add_success:
        print("به‌روزرسانی با موفقیت انجام شد")
    else:
        print("خطا در به‌روزرسانی سند")
    
    return add_success

def check_chromadb_directory():
    """بررسی محتوای دایرکتوری ChromaDB"""
    print("\n=== بررسی محتوای دایرکتوری ChromaDB ===")
    
    # آدرس دایرکتوری ChromaDB
    chroma_dir = os.getenv('CHROMA_PERSIST_DIRECTORY', './data/chroma')
    print(f"دایرکتوری ChromaDB: {chroma_dir}")
    
    try:
        # بررسی وجود دایرکتوری
        if not os.path.exists(chroma_dir):
            print(f"خطا: دایرکتوری '{chroma_dir}' وجود ندارد!")
            return False
        
        # بررسی محتوای دایرکتوری
        files = os.listdir(chroma_dir)
        print(f"تعداد فایل‌ها و دایرکتوری‌ها: {len(files)}")
        for file in files:
            file_path = os.path.join(chroma_dir, file)
            file_size = os.path.getsize(file_path) if os.path.isfile(file_path) else 'دایرکتوری'
            print(f"  {file}: {file_size} بایت" if isinstance(file_size, int) else f"  {file}: {file_size}")
            
            # اگر یک دایرکتوری باشد، محتوای آن را نیز نمایش دهیم
            if os.path.isdir(file_path):
                subfiles = os.listdir(file_path)
                print(f"    تعداد محتویات: {len(subfiles)}")
                for subfile in subfiles[:5]:  # نمایش حداکثر 5 مورد
                    subfile_path = os.path.join(file_path, subfile)
                    subfile_size = os.path.getsize(subfile_path) if os.path.isfile(subfile_path) else 'دایرکتوری'
                    print(f"    {subfile}: {subfile_size} بایت" if isinstance(subfile_size, int) else f"    {subfile}: {subfile_size}")
                if len(subfiles) > 5:
                    print(f"    ... و {len(subfiles) - 5} مورد دیگر")
        
        return True
    except Exception as e:
        print(f"خطا در بررسی دایرکتوری ChromaDB: {str(e)}")
        traceback.print_exc()
        return False

def inspect_vector_store_methods():
    """بررسی متدهای کلاس VectorStore"""
    print("\n=== بررسی متدهای کلاس VectorStore ===")
    
    try:
        # دریافت کد منبع کلاس VectorStore
        import inspect
        from database.vector_store import VectorStore
        
        source = inspect.getsource(VectorStore)
        methods = [
            "add_documents",
            "search",
            "get_all_documents",
            "delete_all",
            "delete_document",
            "update_document"
        ]
        
        for method in methods:
            if f"def {method}" in source:
                print(f"متد '{method}' در کلاس VectorStore یافت شد")
            else:
                print(f"هشدار: متد '{method}' در کلاس VectorStore یافت نشد!")
        
        # چک کردن متد delete_document
        if "def delete_document" in source:
            import re
            delete_method = re.search(r"def delete_document.*?:(.*?)def", source, re.DOTALL)
            if delete_method:
                print("\nمتد delete_document:")
                print(delete_method.group(1).strip())
        
        return True
    except Exception as e:
        print(f"خطا در بررسی متدهای کلاس VectorStore: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='دیباگ عملکرد کلاس VectorStore')
    parser.add_argument('--check-all', action='store_true', help='اجرای تمام تست‌ها')
    parser.add_argument('--get-docs', action='store_true', help='دریافت تمام اسناد')
    parser.add_argument('--delete-doc', help='حذف سند با شناسه مشخص شده')
    parser.add_argument('--add-doc', help='افزودن سند جدید با متن مشخص شده')
    parser.add_argument('--update', nargs=2, metavar=('DOC_ID', 'NEW_TEXT'), help='به‌روزرسانی سند')
    parser.add_argument('--check-dir', action='store_true', help='بررسی دایرکتوری ChromaDB')
    parser.add_argument('--check-methods', action='store_true', help='بررسی متدهای کلاس VectorStore')
    
    args = parser.parse_args()
    
    if args.check_all or args.get_docs:
        test_get_all_documents()
    
    if args.check_all or args.delete_doc:
        test_delete_document(args.delete_doc)
    
    if args.check_all or args.add_doc:
        test_add_document(args.add_doc)
    
    if args.check_all or args.update:
        test_update_flow(args.update[0], args.update[1])
    
    if args.check_all or args.check_dir:
        check_chromadb_directory()
    
    if args.check_all or args.check_methods:
        inspect_vector_store_methods() 