import sys
from pathlib import Path
import json

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from database.vector_store import VectorStore

def load_sample_data():
    # خواندن داده‌های نمونه
    with open('data/sample_data.json', 'r', encoding='utf-8') as f:
        documents = json.load(f)
    
    # ایجاد نمونه VectorStore
    vector_store = VectorStore()
    
    # اضافه کردن اسناد به پایگاه دانش
    vector_store.add_documents(documents)
    
    print(f"تعداد {len(documents)} سند به پایگاه دانش اضافه شد.")

if __name__ == '__main__':
    load_sample_data() 