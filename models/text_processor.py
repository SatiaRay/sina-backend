from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict, Any
import re
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
from dotenv import load_dotenv

load_dotenv()

class TextProcessor:
    def __init__(self):
        self.model = SentenceTransformer(os.getenv('EMBEDDING_MODEL'))
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )

    def clean_text(self, text: str) -> str:
        # حذف کاراکترهای خاص و نویز
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s\u0600-\u06FF]', ' ', text)
        return text.strip()

    def split_text(self, text: str) -> List[str]:
        # تقسیم متن به بخش‌های کوچکتر
        return self.text_splitter.split_text(text)

    def create_embeddings(self, texts: List[str]) -> np.ndarray:
        # ایجاد embeddings برای متن‌ها
        return self.model.encode(texts)

    def process_metadata(self, metadata: Dict[str, Any]) -> Dict[str, str]:
        # تبدیل metadata به فرمت قابل قبول برای ChromaDB
        processed_metadata = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                processed_metadata[key] = str(value)
            elif isinstance(value, dict):
                # تبدیل دیکشنری به رشته JSON
                processed_metadata[key] = str(value)
            else:
                processed_metadata[key] = str(value)
        return processed_metadata

    def process_document(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        # پردازش یک سند کامل
        processed_chunks = []
        
        # بررسی نوع سند (فرمت قدیمی یا جدید)
        if 'text' in document and 'metadata' in document:
            # فرمت جدید از خزنده
            content = document['text']
            metadata = document['metadata']
            url = metadata.get('source', '')
            title = metadata.get('title', '')
        elif 'content' in document and 'url' in document:
            # فرمت قدیمی
            content = document['content']
            url = document['url']
            title = document['title']
            metadata = document.get('metadata', {})
        else:
            raise ValueError("فرمت سند نامعتبر است")
        
        # ثبت اطلاعات برای دیباگ
        print(f"پردازش سند با منبع: {url}")
        print(f"عنوان سند: {title}")
        
        # پردازش متن
        cleaned_text = self.clean_text(content)
        chunks = self.split_text(cleaned_text)
        embeddings = self.create_embeddings(chunks)
        
        print(f"سند به {len(chunks)} قطعه تقسیم شد")
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # پردازش metadata - حفظ دقیق URL اصلی
            processed_metadata = self.process_metadata({
                'source': url,  # URL را دقیقاً همانطور که دریافت شده، حفظ می‌کنیم
                'title': title,
                'chunk_index': str(i),
                'timestamp': metadata.get('timestamp', ''),
                'content_type': metadata.get('content_type', ''),
                'date_added': metadata.get('date_added', '')
            })
            
            processed_chunks.append({
                'text': chunk,
                'embedding': embedding.tolist(),
                'metadata': processed_metadata
            })
        
        return processed_chunks

    def process_batch(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # پردازش دسته‌ای اسناد
        all_processed_chunks = []
        for doc in documents:
            processed_chunks = self.process_document(doc)
            all_processed_chunks.extend(processed_chunks)
        return all_processed_chunks
        
    def process_text(self, text: str) -> str:
        """
        پردازش یک متن ساده
        
        Args:
            text: متن ورودی
            
        Returns:
            متن پردازش شده
        """
        # تمیز کردن متن
        cleaned_text = self.clean_text(text)
        return cleaned_text 