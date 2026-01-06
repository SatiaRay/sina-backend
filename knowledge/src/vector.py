from itertools import tee
import chromadb
from certifi import where
from chromadb.config import Settings
import os
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
import json
from pathlib import Path
import uuid
from datetime import datetime
from openai import OpenAI
from .util import chunk_text

load_dotenv()

class VectorStore:
    def __init__(self):
        try:
            # تنظیمات ChromaDB
            self.persist_directory = os.getenv(
                "CHROMA_PERSIST_DIRECTORY", "./data/chroma"
            )
            self.collection_name = os.getenv(
                "CHROMA_COLLECTION_NAME", "default")

            # ایجاد دایرکتوری اگر وجود نداشت
            os.makedirs(self.persist_directory, exist_ok=True)

            print(
                f"Initializing ChromaDB with directory: {self.persist_directory}")
            # ایجاد کلاینت ChromaDB
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False,
                                  allow_reset=True),
            )

            print("Creating or getting collection...")
            # ایجاد یا دریافت کالکشن
            self.__refresh()

            # print("Initializing embedding model...")
            # # مدل تبدیل متن به بردار
            # self.embedding_model = SentenceTransformer(
            #     os.getenv('EMBEDDING_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')
            # )
            print("VectorStore initialization completed successfully")

        except Exception as e:
            print(f"Error initializing VectorStore: {str(e)}")
            raise

    def _get_or_create_collection(self):
        # ایجاد یا دریافت کالکشن
        return self.client.get_or_create_collection(
            name=self.collection_name, metadata={"hnsw:space": "cosine"}
        )

    def __refresh(self):
        self.collection = None
        self.collection = self._get_or_create_collection()

    def _clean_metadata(self, metadata: dict) -> dict:
        cleaned_metadata = {}

        for key, value in metadata.items():
            if value is None:
                cleaned_metadata[key] = ""
            else:
                cleaned_metadata[key] = value

        return cleaned_metadata

    def add_document(self, document: dict):
        client = OpenAI()

        # chunks = chunk_text(doc['text'])

        id = f"doc_{uuid.uuid4().hex}"

        metadatas = self._clean_metadata(document['metadata'])

        embeddings = []

        response = client.embeddings.create(
            input=document['text'],
            model=os.getenv("OPENAI_EMBEDDING_MODEL",
                            "text-embedding-3-small"),
        )
        embeddings.append(response.data[0].embedding)

        self.save_documents(id, document["text"], metadatas, embeddings)

        return id

    def save_documents(self, ids, documents, metadatas, embeddings):
        self.collection.add(
            embeddings=embeddings, documents=documents, metadatas=metadatas, ids=ids
        )

    def search(self, query: str, n_results: int = 1000) -> List[Dict[str, Any]]:
        """جستجوی اسناد مرتبط"""
        # تبدیل سوال به بردار با استفاده از OpenAI
        client = OpenAI()
        response = client.embeddings.create(
            input=query,
            model=os.getenv("OPENAI_EMBEDDING_MODEL",
                            "text-embedding-3-small"),
        )
        query_embedding = response.data[0].embedding

        # جستجو در کالکشن
        results = self.collection.query(
            query_embeddings=[query_embedding], n_results=n_results
        )

        # تبدیل نتایج به فرمت مورد نظر و فیلتر بر اساس threshold
        documents = []
        for i in range(len(results["documents"][0])):
            # تبدیل فاصله به امتیاز شباهت (1 - distance)
            similarity_score = 1 - results["distances"][0][i]

            # فقط نتایج با امتیاز شباهت بالاتر از 0.3 را اضافه کن
            if similarity_score >= 0.3:
                documents.append(
                    {
                        "text": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "score": similarity_score,
                        "id": results["ids"][0][i],
                    }
                )

        return documents

    def delete_documents(self, vector_ids: list[str]):
        """Delete a vector from the vector store"""
        self.collection.delete(ids=vector_ids)

    def update_document(self, vector_id: str, document: dict):
        """Update a document in the vector store"""
        # تبدیل متن‌ها به بردار با استفاده از OpenAI
        client = OpenAI()

        print("Send modification to ebmedding model ...")

        response = client.embeddings.create(
            input=document['text'], model=os.getenv(
                "GPT_EMBEDDING_MODEL", "text-embedding-3-small")
        )
        embedding = response.data[0].embedding

        print("Embedding done !")

        self.collection.update(
            embeddings=[embedding],
            documents=[document['text']],
            metadatas=[document['metadata']],
            ids=[vector_id],
        )
       

    def get_all_documents(self, ids: list[str] | None = None) -> list[dict[str, any]]:
     
        if ids is not None:
            results = self.collection.get(ids=ids)
        else:
            results = self.collection.get()
        return [
            {"id": doc_id, "text": doc, "metadata": meta}
            for doc, meta, doc_id in zip(
                results["documents"], results["metadatas"], results["ids"]
            )
        ]

    def get_document_by_id(self, vector_id: str) -> Optional[dict]:
        """Retrieve a single document by its vector id"""
        results = self.collection.get(ids=[vector_id])
        if not results["ids"] or not results["ids"][0]:
            return None
        return {
            "id": results["ids"][0],
            "text": results["documents"][0],
            "metadata": results["metadatas"][0],
        }
