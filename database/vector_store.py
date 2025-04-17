import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import os
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
import json
from pathlib import Path
import uuid
from datetime import datetime

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
        self.collection = self._get_or_create_collection()
        
        # مدل تبدیل متن به بردار
        self.embedding_model = SentenceTransformer(
            os.getenv('EMBEDDING_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')
        )

    def _get_or_create_collection(self):
        # ایجاد یا دریافت کالکشن
        return self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_documents(self, documents: List[Dict[str, Any]]):
        """اضافه کردن اسناد به پایگاه داده برداری"""
        if not documents:
            return
            
        # استخراج متن‌ها و متادیتاها
        texts = [doc['text'] for doc in documents]
        metadatas = [doc['metadata'] for doc in documents]
        
        # تولید ID‌های یکتا با استفاده از UUID
        ids = [f"doc_{uuid.uuid4().hex}" for _ in range(len(documents))]
        
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
            where={"status": "approved"},
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
        self.collection = self._get_or_create_collection()

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

    def get_pending_documents(self, offset: int = 0, limit: int = 50) -> List[Dict]:
        """دریافت اسناد در انتظار بررسی"""
        try:
            # Get all documents
            result = self.collection.get()
            
            # Filter pending documents
            pending_docs = []
            for i, metadata in enumerate(result['metadatas']):
                if metadata.get('status', 'pending') == 'pending':
                    doc = {
                        'document_id': result['ids'][i],
                        'text': result['documents'][i],
                        'metadata': metadata
                    }
                    pending_docs.append(doc)
            
            # Apply pagination
            start = offset
            end = offset + limit
            return pending_docs[start:end]
        except Exception as e:
            print(f"Error getting pending documents: {str(e)}")
            return []

    def update_document_status(self, document_id: str, status: str, edited_text: Optional[str] = None) -> bool:
        """به‌روزرسانی وضعیت یک سند"""
        try:
            # Get the document
            result = self.collection.get(ids=[document_id])
            if not result['ids']:
                raise ValueError(f"Document {document_id} not found")
            
            # Update metadata
            metadata = result['metadatas'][0]
            metadata['status'] = status
            metadata['review_date'] = datetime.now().isoformat()
            
            # If text was edited, update the document
            if edited_text:
                # Create new embedding for edited text
                model = SentenceTransformer(os.getenv('EMBEDDING_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2'))
                new_embedding = model.encode(edited_text).tolist()
                
                # Update document
                self.collection.update(
                    ids=[document_id],
                    documents=[edited_text],
                    metadatas=[metadata],
                    embeddings=[new_embedding]
                )
            else:
                # Only update metadata
                self.collection.update(
                    ids=[document_id],
                    metadatas=[metadata]
                )
            
            return True
        except Exception as e:
            print(f"Error updating document status: {str(e)}")
            return False

    def get_curation_stats(self) -> Dict:
        """دریافت آمار وضعیت بررسی اسناد"""
        try:
            result = self.collection.get()
            
            stats = {
                'total_documents': len(result['ids']),
                'approved': 0,
                'rejected': 0,
                'pending': 0,
                'last_review_date': None
            }
            
            latest_review = None
            for metadata in result['metadatas']:
                status = metadata.get('status', 'pending')
                stats[status] += 1
                
                review_date = metadata.get('review_date')
                if review_date:
                    review_date = datetime.fromisoformat(review_date)
                    if not latest_review or review_date > latest_review:
                        latest_review = review_date
            
            if latest_review:
                stats['last_review_date'] = latest_review.isoformat()
            
            return stats
        except Exception as e:
            print(f"Error getting curation stats: {str(e)}")
            return {
                'total_documents': 0,
                'approved': 0,
                'rejected': 0,
                'pending': 0
            }

    def get_document_by_id(self, document_id: str) -> Optional[Dict]:
        """دریافت جزئیات یک سند با شناسه"""
        try:
            result = self.collection.get(ids=[document_id])
            if not result['ids']:
                return None
                
            return {
                'document_id': result['ids'][0],
                'text': result['documents'][0],
                'metadata': result['metadatas'][0]
            }
        except Exception as e:
            print(f"Error getting document: {str(e)}")
            return None 