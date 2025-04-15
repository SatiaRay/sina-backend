import sys
from pathlib import Path

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from database.vector_store import VectorStore

def test_vector_store():
    # ایجاد نمونه VectorStore
    vector_store = VectorStore()
    
    # جستجوی یک سوال نمونه
    query = "ساتیا چیست"
    results = vector_store.search(query)
    
    print(f"نتایج جستجو برای سوال '{query}':")
    for i, doc in enumerate(results, 1):
        print(f"\nنتیجه {i}:")
        print(f"متن: {doc['text']}")
        print(f"منبع: {doc['metadata']['source']}")
        print(f"امتیاز: {doc['score']}")

if __name__ == '__main__':
    test_vector_store() 