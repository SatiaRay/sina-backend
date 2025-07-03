import chromadb
from chromadb.api import AdminAPI, ClientAPI
from chromadb.config import DEFAULT_DATABASE, DEFAULT_TENANT, Settings
import os
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
import json
from pathlib import Path
import uuid
from datetime import datetime
from openai import OpenAI
from util import database
from util.event_bus import event_bus, VectorStoreEvent

load_dotenv()

class VectorStore:
    def __init__(self, collection_name:str|None = None, tenant: str = DEFAULT_TENANT, database: str = DEFAULT_DATABASE):
        try:
            self.tenant = tenant
            self.database = database
            self.collection_name = collection_name or os.getenv('VECTOR_DEFAULT_COLLECTION')
            
            # ایجاد کلاینت ChromaDB
            self.client = self.get_client(chromadb.AdminClient())
            
            print("Creating or getting collection...")
            # ایجاد یا دریافت کالکشن
            self.__refresh()
            
            print("VectorStore initialization completed successfully")
            
        except Exception as e:
            print(f"Error initializing VectorStore: {str(e)}")
            raise
        
    def get_client(self, admin: AdminAPI):                        
        self.__create_tenant_if_not_exists(admin)
        
        self.__create_database_if_not_exists(admin)
        
        client = chromadb.Client(database=self.database, tenant=self.tenant)
            
        return client
    
    def __create_tenant_if_not_exists(self, adminApi: AdminAPI):
        try:
            return adminApi.create_tenant(name=self.tenant)
        except:
            return adminApi.get_tenant(name=self.tenant)
    
    def __create_database_if_not_exists(self, adminApi: AdminAPI):
        try:
            return adminApi.create_database(name=self.database, tenant=self.tenant)
        except:
            return adminApi.get_database(name=self.database, tenant=self.tenant)

    def _get_or_create_collection(self):
        # ایجاد یا دریافت کالکشن
        return self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def __refresh(self):
        self.collection = None
        self.collection = self._get_or_create_collection()

    def add_documents(self, documents: List[Dict[str, Any]], vector_id: str = None):
        """اضافه کردن اسناد به پایگاه داده برداری"""
        if not documents:
            return
            
        # استخراج متن‌ها و متادیتاها
        texts = [doc['text'] for doc in documents]
        
        # Clean metadata by converting None values to empty strings
        metadatas = []
        for doc in documents:
            cleaned_metadata = {}
            for key, value in doc['metadata'].items():
                if value is None:
                    cleaned_metadata[key] = ""
                else:
                    cleaned_metadata[key] = value
            metadatas.append(cleaned_metadata)
        
        # تولید ID‌های یکتا با استفاده از UUID
        ids = vector_id or [f"doc_{uuid.uuid4().hex}" for _ in range(len(documents))]
        
        # تبدیل متن‌ها به بردار با استفاده از OpenAI
        client = OpenAI()
        
        embeddings = []
        for text in texts:
            response = client.embeddings.create(
                input=text,
                model=os.getenv('GPT_EMBEDDING_MODEL', 'text-embedding-3-small')
            )
            embeddings.append(response.data[0].embedding)

        # اضافه کردن به کالکشن
        self.save_documents(ids, texts, metadatas, embeddings)

        # Publish event for document addition
        event_bus.publish(VectorStoreEvent.DOCUMENT_ADDED, {
            'ids': ids,
            'documents': documents
        })
        event_bus.publish(VectorStoreEvent.COLLECTION_MODIFIED)

        return ids

    def save_documents(self, ids, documents, metadatas, embeddings):
        self.collection.add(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

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
        
        # Publish event for collection modification
        event_bus.publish(VectorStoreEvent.COLLECTION_MODIFIED)

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

        self.collection.update(
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata],
            ids=[document_id]
        )
        
        # Publish event for document update
        event_bus.publish(VectorStoreEvent.DOCUMENT_UPDATED, {
            'id': document_id,
            'text': text,
            'metadata': metadata
        })
        event_bus.publish(VectorStoreEvent.COLLECTION_MODIFIED)

    def delete_vector(self, vector_id: str):
        """Delete a vector from the vector store"""
        self.collection.delete(ids=[vector_id])
        
        # Publish event for document deletion
        event_bus.publish(VectorStoreEvent.DOCUMENT_DELETED, {
            'id': vector_id
        })
        event_bus.publish(VectorStoreEvent.COLLECTION_MODIFIED)

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
            
            # Publish event for document update
            event_bus.publish(VectorStoreEvent.DOCUMENT_UPDATED, {
                'id': document_id,
                'text': edited_text,
                'metadata': metadata
            })
            event_bus.publish(VectorStoreEvent.COLLECTION_MODIFIED)

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
        
    
    
