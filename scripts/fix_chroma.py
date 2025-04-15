import sys
import os
from pathlib import Path

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# لود کردن متغیرهای محیطی از .env
from dotenv import load_dotenv
load_dotenv()

import chromadb
from sentence_transformers import SentenceTransformer
from datetime import datetime

def reset_and_fix_chroma():
    """بازسازی مجدد دیتابیس ChromaDB"""
    
    # آدرس دایرکتوری ChromaDB
    chroma_dir = os.getenv('CHROMA_PERSIST_DIRECTORY', './data/chroma')
    collection_name = os.getenv('CHROMA_COLLECTION_NAME', 'satya_docs')
    
    print(f"تنظیم مجدد دیتابیس ChromaDB در مسیر: {chroma_dir}")
    print(f"نام کالکشن: {collection_name}")
    
    try:
        # ایجاد کلاینت ChromaDB
        client = chromadb.PersistentClient(
            path=chroma_dir
        )
        
        # حذف کالکشن موجود در صورت وجود
        try:
            print("در حال حذف کالکشن موجود...")
            client.delete_collection(collection_name)
            print("کالکشن با موفقیت حذف شد")
        except Exception as e:
            print(f"خطا در حذف کالکشن: {str(e)}")
        
        # ایجاد کالکشن جدید
        print("در حال ایجاد کالکشن جدید...")
        collection = client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        print("کالکشن جدید با موفقیت ایجاد شد")
        
        # افزودن یک سند تست برای اطمینان از کارکرد صحیح
        embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        test_text = "این یک متن تست برای اطمینان از کارکرد صحیح ChromaDB است"
        metadata = {
            "source": "https://www.satia.co/",
            "title": "تست",
            "created_at": datetime.now().isoformat()
        }
        
        # ایجاد embedding
        embedding = embedding_model.encode(test_text).tolist()
        
        # افزودن سند تست
        print("در حال افزودن سند تست...")
        collection.add(
            embeddings=[embedding],
            documents=[test_text],
            metadatas=[metadata],
            ids=["test_doc_1"]
        )
        print("سند تست با موفقیت اضافه شد")
        
        # بررسی سند اضافه شده
        print("در حال بررسی سند اضافه شده...")
        results = collection.get()
        
        if results and len(results['ids']) > 0:
            print(f"تعداد اسناد: {len(results['ids'])}")
            print(f"ID سند: {results['ids'][0]}")
            print(f"متن سند: {results['documents'][0]}")
            print("عملیات موفقیت‌آمیز بود")
        else:
            print("خطا: سند تست اضافه نشد")
        
        # تست جستجو
        print("\nدر حال تست جستجو...")
        query_embedding = embedding_model.encode("متن تست").tolist()
        search_results = collection.query(
            query_embeddings=[query_embedding],
            n_results=1
        )
        
        if search_results and len(search_results['ids'][0]) > 0:
            print(f"نتیجه جستجو: {search_results['documents'][0][0]}")
            print("عملیات جستجو موفقیت‌آمیز بود")
        else:
            print("خطا: جستجو نتیجه‌ای نداشت")
            
        print("\nمشکل ChromaDB با موفقیت رفع شد")
        return True
        
    except Exception as e:
        print(f"خطا در تنظیم مجدد ChromaDB: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    reset_and_fix_chroma() 