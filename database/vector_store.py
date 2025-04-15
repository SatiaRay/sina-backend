import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import os
from dotenv import load_dotenv
from typing import List, Dict, Any
import json
from pathlib import Path

load_dotenv()

class VectorStore:
    def __init__(self):
        # تنظیمات ChromaDB
        self.persist_directory = os.getenv('CHROMA_PERSIST_DIRECTORY', './data/chroma')
        self.collection_name = os.getenv('CHROMA_COLLECTION_NAME', 'satya_docs')
        
        # ایجاد دایرکتوری اگر وجود نداشت
        os.makedirs(self.persist_directory, exist_ok=True)
        
        # ایجاد کلاینت ChromaDB
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # ایجاد یا دریافت کالکشن
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        # مدل تبدیل متن به بردار
        self.embedding_model = SentenceTransformer(
            os.getenv('EMBEDDING_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')
        )

    def add_documents(self, documents: List[Dict[str, Any]]):
        """اضافه کردن اسناد به پایگاه داده برداری"""
        if not documents:
            return
            
        # استخراج متن‌ها و متادیتاها
        texts = [doc['text'] for doc in documents]
        metadatas = [doc['metadata'] for doc in documents]
        
        # دریافت تعداد اسناد موجود
        current_count = len(self.collection.get()['ids'])
        
        # تولید ID‌های یکتا
        ids = [f"doc_{current_count + i}" for i in range(len(documents))]
        
        # تبدیل متن‌ها به بردار
        embeddings = self.embedding_model.encode(texts).tolist()
        
        # اضافه کردن به کالکشن
        self.collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )

    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """جستجوی اسناد مرتبط"""
        # تبدیل سوال به بردار
        query_embedding = self.embedding_model.encode(query).tolist()
        
        # جستجو در کالکشن
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        # تبدیل نتایج به فرمت مورد نظر
        documents = []
        for i in range(len(results['documents'][0])):
            documents.append({
                'text': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'score': results['distances'][0][i]
            })
            
        return documents

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """
        دریافت تمام اسناد موجود در پایگاه داده به همراه شناسه‌های آنها
        """
        # دریافت تمام اسناد
        results = self.collection.get()
        return [
            {
                'id': doc_id,
                'text': doc,
                'metadata': meta
            }
            for doc, meta, doc_id in zip(results['documents'], results['metadatas'], results['ids'])
        ]

    def delete_all(self):
        # حذف کالکشن
        self.client.delete_collection(self.collection_name)
        
        # ایجاد مجدد کالکشن
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def backup(self, backup_path: str = "data/backup"):
        # پشتیبان‌گیری از داده‌ها
        backup_dir = Path(backup_path)
        backup_dir.mkdir(exist_ok=True)
        
        documents = self.get_all_documents()
        with open(backup_dir / "vector_store_backup.json", "w", encoding="utf-8") as f:
            json.dump(documents, f, ensure_ascii=False, indent=2)

    def restore(self, backup_path: str = "data/backup/vector_store_backup.json"):
        # بازیابی از پشتیبان
        with open(backup_path, "r", encoding="utf-8") as f:
            documents = json.load(f)
        
        self.delete_all()
        self.add_documents(documents)

    def update_document(self, document: Dict):
        """Update a document in the vector store"""
        embedding = self.embedding_model.encode([document["text"]])[0]
        self.collection.update(
            embeddings=[embedding.tolist()],
            documents=[document["text"]],
            metadatas=[document["metadata"]],
            ids=[document["id"]]
        )

    def delete_document(self, document_id: str):
        """Delete a document from the vector store"""
        self.collection.delete(ids=[document_id]) 