import sys
from pathlib import Path
import json

# Add the project root directory to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from models.rag import RAGSystem
from database.vector_store import VectorStore

def check_get_all_knowledge(url):
    """
    تست عملکرد get_all_knowledge برای یک URL مشخص
    
    این اسکریپت داده‌های ذخیره شده در ChromaDB برای یک URL خاص را بازیابی می‌کند
    و اطلاعات آن‌ها را نمایش می‌دهد.
    """
    print(f"بررسی داده‌های ذخیره شده برای URL: {url}")
    
    # ایجاد نمونه از RAGSystem
    rag_system = RAGSystem()
    
    # فراخوانی متد get_all_knowledge
    try:
        result = rag_system.get_all_knowledge(url)
        
        print(f"\nتعداد اسناد یافت شده: {result['count']}")
        
        if result['count'] > 0:
            print("\nنمونه‌هایی از اسناد یافت شده:")
            for i, doc in enumerate(result['documents'][:3]):  # نمایش حداکثر 3 سند اول
                print(f"\n--- سند {i+1} ---")
                print(f"متن: {doc['text'][:200]}..." if len(doc['text']) > 200 else f"متن: {doc['text']}")
                print(f"متادیتا: {json.dumps(doc['metadata'], ensure_ascii=False, indent=2)}")
        else:
            print("\nهیچ سندی برای این URL یافت نشد.")
        
        # ذخیره نتایج در یک فایل JSON
        output_dir = Path("data/debug")
        output_dir.mkdir(exist_ok=True, parents=True)
        
        output_file = output_dir / f"all_knowledge_results.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\nنتایج کامل در فایل {output_file} ذخیره شدند.")
            
    except Exception as e:
        print(f"خطا در بازیابی اسناد: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
        check_get_all_knowledge(url)
    else:
        # استفاده از یک URL پیش‌فرض برای تست
        print("هیچ URL‌ای مشخص نشده است. استفاده از URL پیش‌فرض برای تست...")
        check_get_all_knowledge("https://www.satia.co/%D8%A8%DB%8C%D8%A7%D9%86%DB%8C%D9%87-%DB%8C-%D9%85%D8%A7%D9%85%D9%88%D8%B1%DB%8C%D8%AA/") 