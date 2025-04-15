import os
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
from datetime import datetime
import json
import traceback
from sentence_transformers import SentenceTransformer

# لود کردن متغیرهای محیطی
load_dotenv()

def fix_chunk():
    """
    اصلاح مستقیم چانک در ChromaDB
    """
    try:
        # تنظیمات ChromaDB
        chroma_dir = os.getenv('CHROMA_PERSIST_DIRECTORY', './data/chroma')
        collection_name = os.getenv('CHROMA_COLLECTION_NAME', 'satya_docs')
        
        print(f"دایرکتوری ChromaDB: {chroma_dir}")
        print(f"نام کالکشن: {collection_name}")
        
        # ایجاد کلاینت ChromaDB
        client = chromadb.PersistentClient(
            path=chroma_dir,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # دریافت کالکشن موجود
        collection = client.get_collection(name=collection_name)
        
        # دریافت تمام داده‌ها
        all_data = collection.get()
        print(f"تعداد کل اسناد: {len(all_data['ids'])}")
        
        # بررسی داده‌ها
        found_doc = False
        doc_to_update = None
        doc_index = None
        
        # بررسی داده‌ها و یافتن چانک مورد نظر
        for i, (doc_id, doc_text, doc_metadata) in enumerate(zip(all_data['ids'], all_data['documents'], all_data['metadatas'])):
            # جستجو برای یافتن چانک مربوط به URL مورد نظر (چانک شماره 1)
            if doc_metadata.get('source') == 'https://www.satia.co/' and doc_id == 'doc_1':
                found_doc = True
                doc_to_update = {
                    'id': doc_id,
                    'text': doc_text,
                    'metadata': doc_metadata
                }
                doc_index = i
                print(f"سند مورد نظر یافت شد:")
                print(f"  شناسه: {doc_id}")
                print(f"  متن: {doc_text[:100]}")
                print(f"  منبع: {doc_metadata.get('source')}")
                break
        
        if not found_doc:
            print("سند مورد نظر (doc_1 با URL: https://www.satia.co/) یافت نشد")
            
            # جستجوی تمام اسناد مرتبط با URL مورد نظر
            related_docs = []
            for i, (doc_id, doc_text, doc_metadata) in enumerate(zip(all_data['ids'], all_data['documents'], all_data['metadatas'])):
                if doc_metadata.get('source') == 'https://www.satia.co/':
                    related_docs.append({
                        'id': doc_id,
                        'text': doc_text[:100],
                        'metadata': doc_metadata
                    })
            
            if related_docs:
                print(f"اسناد مرتبط با URL https://www.satia.co/:")
                for i, doc in enumerate(related_docs):
                    print(f"  سند {i}:")
                    print(f"    شناسه: {doc['id']}")
                    print(f"    متن: {doc['text']}")
            
            # در صورت عدم وجود doc_1، از اولین سند استفاده کنیم
            if related_docs:
                doc_to_update = related_docs[0]
                print(f"استفاده از اولین سند مرتبط به عنوان هدف به‌روزرسانی:")
                print(f"  شناسه: {doc_to_update['id']}")
        
        if doc_to_update:
            # حذف چانک قدیمی
            try:
                print(f"در حال حذف چانک با شناسه {doc_to_update['id']}...")
                collection.delete(ids=[doc_to_update['id']])
                print("چانک با موفقیت حذف شد")
                
                # بررسی حذف موفقیت‌آمیز
                after_delete = collection.get()
                if doc_to_update['id'] not in after_delete['ids']:
                    print("حذف با موفقیت تأیید شد")
                else:
                    print("خطا: چانک هنوز وجود دارد!")
            except Exception as e:
                print(f"خطا در حذف چانک: {str(e)}")
                traceback.print_exc()
            
            # افزودن چانک جدید
            new_text = "شرکت ساتیاری ارتباط"
            
            try:
                # ایجاد embedding جدید با استفاده از SentenceTransformer
                print("در حال ایجاد embedding جدید...")
                model = SentenceTransformer(os.getenv('EMBEDDING_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2'))
                new_embedding = model.encode(new_text).tolist()
                
                print(f"در حال افزودن چانک جدید با متن '{new_text}'...")
                collection.add(
                    ids=[doc_to_update['id']],
                    documents=[new_text],
                    metadatas=[doc_to_update['metadata']],
                    embeddings=[new_embedding]
                )
                print("چانک جدید با موفقیت اضافه شد")
            except Exception as e:
                print(f"خطا در افزودن چانک جدید: {str(e)}")
                traceback.print_exc()
        
        # بررسی نتیجه
        updated_data = collection.get()
        print(f"\nبررسی نتیجه نهایی:")
        print(f"تعداد کل اسناد بعد از به‌روزرسانی: {len(updated_data['ids'])}")
        
        if doc_to_update:
            updated_doc = None
            for i, (doc_id, doc_text, doc_metadata) in enumerate(zip(updated_data['ids'], updated_data['documents'], updated_data['metadatas'])):
                if doc_id == doc_to_update['id']:
                    updated_doc = {
                        'id': doc_id,
                        'text': doc_text,
                        'metadata': doc_metadata
                    }
                    break
            
            if updated_doc:
                print(f"سند به‌روزرسانی شده:")
                print(f"  شناسه: {updated_doc['id']}")
                print(f"  متن جدید: {updated_doc['text']}")
                print("به‌روزرسانی با موفقیت انجام شد")
            else:
                print(f"خطا: سند با شناسه {doc_to_update['id']} بعد از به‌روزرسانی یافت نشد")
        
        return True
    except Exception as e:
        print(f"خطا در اصلاح چانک: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("شروع فرآیند اصلاح مستقیم چانک...")
    fix_chunk()
    print("پایان فرآیند اصلاح چانک") 