import sys
from pathlib import Path

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from database.vector_store import VectorStore

def check_chroma_data():
    # ایجاد نمونه VectorStore
    vector_store = VectorStore()
    
    # دریافت تمام اسناد
    documents = vector_store.get_all_documents()
    
    print(f"تعداد اسناد در پایگاه داده: {len(documents)}")
    for i, doc in enumerate(documents, 1):
        print(f"\nسند {i}:")
        print(f"متن: {doc['text'][:200]}...")  # نمایش 200 کاراکتر اول
        print(f"متادیتا: {doc['metadata']}")

if __name__ == '__main__':
    check_chroma_data() 