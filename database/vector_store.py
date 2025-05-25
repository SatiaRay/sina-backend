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
from openai import OpenAI
import threading
import time
import traceback

load_dotenv()

class VectorStore:
    _instance = None
    _lock = threading.Lock()
    _collection = None
    _last_refresh = 0
    _refresh_interval = 1  # Refresh interval in seconds

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(VectorStore, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            try:
                # تنظیمات ChromaDB
                self.persist_directory = os.getenv('CHROMA_PERSIST_DIRECTORY', './data/chroma')
                self.collection_name = os.getenv('CHROMA_COLLECTION_NAME', 'satya_docs')
                
                # ایجاد دایرکتوری اگر وجود نداشت
                os.makedirs(self.persist_directory, exist_ok=True)
                
                print(f"Initializing ChromaDB with directory: {self.persist_directory}")
                # ایجاد کلاینت ChromaDB
                self.client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
                
                print("Creating or getting collection...")
                # ایجاد یا دریافت کالکشن
                self._ensure_collection()
                
                print("VectorStore initialization completed successfully")
                self.initialized = True
                
            except Exception as e:
                print(f"Error initializing VectorStore: {str(e)}")
                raise

    def _ensure_collection(self):
        """Ensure collection is up-to-date with automatic refresh"""
        current_time = time.time()
        if (self._collection is None or 
            current_time - self._last_refresh > self._refresh_interval):
            with self._lock:
                if (self._collection is None or 
                    current_time - self._last_refresh > self._refresh_interval):
                    try:
                        self._collection = self.client.get_or_create_collection(
                            name=self.collection_name,
                            metadata={"hnsw:space": "cosine"}
                        )
                        self._last_refresh = current_time
                    except Exception as e:
                        print(f"Error refreshing collection: {str(e)}")
                        raise

    @property
    def collection(self):
        """Get the current collection instance with automatic refresh"""
        self._ensure_collection()
        return self._collection

    def add_documents(self, documents: List[Dict[str, Any]]):
        """اضافه کردن اسناد به پایگاه داده برداری"""
        if not documents:
            print("No documents provided to add")
            return
            
        try:
            # استخراج متن‌ها و متادیتاها
            texts = [doc['text'] for doc in documents]
            metadatas = [doc['metadata'] for doc in documents]
            
            # تولید ID‌های یکتا با استفاده از UUID
            ids = [f"doc_{uuid.uuid4().hex}" for _ in range(len(documents))]
            
            print(f"Preparing to add {len(documents)} documents to vector store")
            
            # تبدیل متن‌ها به بردار با استفاده از OpenAI
            client = OpenAI()
            
            embeddings = []
            for i, text in enumerate(texts):
                print(f"Generating embedding for document {i+1}/{len(texts)}")
                response = client.embeddings.create(
                    input=text,
                    model=os.getenv('GPT_EMBEDDING_MODEL', 'text-embedding-3-small')
                )
                embeddings.append(response.data[0].embedding)
            
            print("All embeddings generated successfully")
            
            # اضافه کردن به کالکشن
            with self._lock:
                print("Acquiring lock for collection update")
                # Force collection refresh before adding
                self._collection = None
                self._ensure_collection()
                
                print("Adding documents to collection")
                self.collection.add(
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=metadatas,
                    ids=ids
                )
                
                # Verify the documents were added
                added_docs = self.collection.get(ids=ids)
                if len(added_docs['ids']) != len(ids):
                    raise Exception(f"Failed to add all documents. Expected {len(ids)}, got {len(added_docs['ids'])}")
                
                print(f"Successfully added {len(ids)} documents to collection")
                self._last_refresh = time.time()  # Force refresh after modification
            
            return ids
            
        except Exception as e:
            print(f"Error adding documents to vector store: {str(e)}")
            traceback.print_exc()
            raise Exception(f"Failed to add documents: {str(e)}")

    def delete_vector(self, vector_id: str):
        """Delete a vector from the vector store"""
        with self._lock:
            self.collection.delete(ids=[vector_id])
            self._last_refresh = time.time()  # Force refresh after modification

    def update_document(self, document_id: str, text: str, metadata: dict):
        """Update a document in the vector store"""
        # تبدیل متن‌ها به بردار با استفاده از OpenAI
        client = OpenAI()

        print("Send modification to ebmedding model ...")
        
        response = client.embeddings.create(
            input=text,
            model=os.getenv('GPT_EMBEDDING_MODEL', 'text-embedding-3-small')
        )
        embedding = response.data[0].embedding

        print("Embedding done !")

        with self._lock:
            self.collection.update(
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata],
                ids=[document_id]
            )
            self._last_refresh = time.time()  # Force refresh after modification

    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """جستجوی اسناد مرتبط"""
        # تبدیل سوال به بردار با استفاده از OpenAI
        client = OpenAI()
        response = client.embeddings.create(
            input=query,
            model=os.getenv('GPT_EMBEDDING_MODEL', 'text-embedding-3-small')
        )
        query_embedding = response.data[0].embedding
        
        # جستجو در کالکشن
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        # تبدیل نتایج به فرمت مورد نظر و فیلتر بر اساس threshold
        documents = []
        for i in range(len(results['documents'][0])):
            # تبدیل فاصله به امتیاز شباهت (1 - distance)
            similarity_score = 1 - results['distances'][0][i]
            
            # فقط نتایج با امتیاز شباهت بالاتر از 0.3 را اضافه کن
            if similarity_score >= 0.3:
                documents.append({
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'score': similarity_score,
                    'id': results['ids'][0][i]
                })
            
        return documents

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """دریافت تمام اسناد موجود در پایگاه داده به همراه شناسه‌های آنها"""
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
        """Delete all documents and recreate the collection"""
        with self._lock:
            self.client.delete_collection(self.collection_name)
            self._collection = None  # Force collection refresh
            self._ensure_collection()
            self._last_refresh = time.time()

    def get_document(self, document_id: str) -> dict:
        """Get a document from the vector store by its ID"""
        try:
            result = self.collection.get(ids=[document_id])
            if not result['ids']:
                return None
                
            return {
                'id': result['ids'][0],
                'text': result['documents'][0],
                'metadata': result['metadatas'][0]
            }
        except Exception as e:
            print(f"Error getting document: {str(e)}")
            return None

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
        
    
    
