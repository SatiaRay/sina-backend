from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
from database.vector_store import VectorStore
from models.text_processor import TextProcessor
from crawler.main import run_spider
from datetime import datetime
import json
from pathlib import Path

load_dotenv()

class RAGSystem:
    def __init__(self):
        self.vector_store = VectorStore()
        self.text_processor = TextProcessor()
        self.ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        self.ollama_model = os.getenv('OLLAMA_MODEL', 'mistral')
        
        # ایجاد نمونه Ollama
        self.llm = Ollama(
            base_url=self.ollama_host,
            model=self.ollama_model,
            temperature=float(os.getenv('TEMPERATURE', 0.7)),
            num_ctx=int(os.getenv('MAX_TOKENS', 4096))
        )
        
        # تعریف تمپلیت برای تولید پاسخ
        self.prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template="""
            شما یک دستیار هوشمند پشتیبانی ساتیا به زبان فارسی هستید. وظیفه شما پاسخ دادن به سوالات کاربران با استفاده از اطلاعاتی است که در اختیار شما قرار داده شده است.

            دستورالعمل‌های مهم:
            1. همیشه به زبان فارسی پاسخ دهید.
            2. فقط از اطلاعات ارائه شده استفاده کنید و از دانش عمومی خود استفاده نکنید.
            3. اگر پاسخ سوال در اطلاعات ارائه شده موجود نیست، صادقانه بگویید: "متأسفانه اطلاعات کافی برای پاسخ به این سوال ندارم."
            4. از حدس و گمان خودداری کنید و فقط بر اساس اطلاعات موجود پاسخ دهید.
            5. پاسخ‌های خود را مختصر و مفید ارائه دهید.

            اطلاعات مرتبط:
            {context}
            
            سوال کاربر: {question}
            
            پاسخ فارسی:
            """
        )

    def generate_response(self, question: str) -> Dict[str, Any]:
        # جستجوی اسناد مرتبط
        relevant_docs = self.vector_store.search(question)
        
        # ترکیب اسناد مرتبط
        context = "\n\n".join([doc['text'] for doc in relevant_docs])
        
        # تولید پاسخ با استفاده از Ollama
        prompt = self.prompt_template.format(
            context=context,
            question=question
        )
        
        response = self.llm(prompt)
        
        return {
            'answer': response,
            'sources': [
                {
                    'text': doc['text'],
                    'metadata': doc['metadata']
                }
                for doc in relevant_docs
            ]
        }

    def update_knowledge_base(self, url_or_documents):
        """
        به‌روزرسانی پایگاه دانش با اسناد جدید یا داده‌های استخراج شده از URL
        
        Args:
            url_or_documents: می‌تواند یک URL (str) یا لیستی از اسناد (List[Dict]) باشد
            
        Returns:
            Dictionary شامل اطلاعات مربوط به تعداد اسناد اضافه شده
        """
        try:
            # بررسی نوع ورودی (URL یا لیست اسناد)
            if isinstance(url_or_documents, str):
                # استخراج داده‌ها از URL
                url = url_or_documents
                print(f"استخراج داده از URL: {url}")
                documents = run_spider(url)
                
                if not documents or len(documents) == 0:
                    return {
                        "status": "error",
                        "message": "هیچ اطلاعاتی از URL استخراج نشد",
                        "document_count": 0
                    }
                
                # اضافه کردن متادیتا به اسناد
                for doc in documents:
                    if 'metadata' not in doc:
                        doc['metadata'] = {}
                    # ذخیره URL دقیقا همانطور که دریافت شده
                    doc['metadata']['source'] = url
                    doc['metadata']['date_added'] = datetime.now().isoformat()
            else:
                # استفاده از اسناد ارائه شده
                documents = url_or_documents
                
                # اطمینان از وجود متادیتای مناسب برای اسناد دستی
                for doc in documents:
                    if 'metadata' not in doc:
                        doc['metadata'] = {}
                    if 'date_added' not in doc['metadata']:
                        doc['metadata']['date_added'] = datetime.now().isoformat()
            
            # پردازش متن‌ها
            processed_docs = self.text_processor.process_batch(documents)
            print(f"تعداد {len(processed_docs)} سند پردازش شد")
            
            # اضافه کردن به vector store
            self.vector_store.add_documents(processed_docs)
            
            # ذخیره‌سازی اسناد خام برای بررسی‌های آینده
            if isinstance(url_or_documents, str):
                # ذخیره اسناد خام در یک فایل JSON
                try:
                    url_safe = url.replace(':', '_').replace('/', '_')
                    log_dir = Path("data/raw_documents")
                    log_dir.mkdir(exist_ok=True, parents=True)
                    log_file = log_dir / f"raw_{datetime.now().strftime('%Y%m%d%H%M%S')}_{url_safe[:50]}.json"
                    with open(log_file, 'w', encoding='utf-8') as f:
                        json.dump(documents, f, ensure_ascii=False, indent=2)
                    print(f"اسناد خام در {log_file} ذخیره شدند")
                except Exception as e:
                    print(f"خطا در ذخیره‌سازی اسناد خام: {str(e)}")
            
            return {
                "status": "success",
                "message": f"تعداد {len(processed_docs)} سند پردازش شد و به پایگاه دانش اضافه شد",
                "document_count": len(processed_docs)
            }
        except Exception as e:
            print(f"خطا در به‌روزرسانی پایگاه دانش: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "message": f"خطا در به‌روزرسانی پایگاه دانش: {str(e)}",
                "document_count": 0
            }

    def get_relevant_documents(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        # دریافت اسناد مرتبط
        return self.vector_store.search(query, n_results)
        
    def get_all_knowledge(self, url: str) -> Dict[str, Any]:
        """
        دریافت تمام اسناد مرتبط با یک URL خاص
        
        Args:
            url: آدرس منبع داده
            
        Returns:
            Dictionary شامل اطلاعات اسناد و تعداد آنها
        """
        # دریافت همه اسناد از vector store
        all_docs = self.vector_store.get_all_documents()
        
        # فیلتر کردن اسناد براساس URL
        filtered_docs = []
        for doc in all_docs:
            if doc.get('metadata', {}).get('source') == url:
                filtered_docs.append({
                    'text': doc['text'],
                    'metadata': doc['metadata']
                })
        
        return {
            'documents': filtered_docs,
            'count': len(filtered_docs)
        } 