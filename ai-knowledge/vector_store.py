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
from models import Document
from util.event_bus import event_bus, VectorStoreEvent
from util.vectore import chunk_text

load_dotenv()


class VectorStore:
    def __init__(self):
        try:
            # تنظیمات ChromaDB
            self.persist_directory = os.getenv(
                "CHROMA_PERSIST_DIRECTORY", "./data/chroma"
            )
            self.collection_name = os.getenv("CHROMA_COLLECTION_NAME", "default")

            # ایجاد دایرکتوری اگر وجود نداشت
            os.makedirs(self.persist_directory, exist_ok=True)

            print(f"Initializing ChromaDB with directory: {self.persist_directory}")
            # ایجاد کلاینت ChromaDB
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False, allow_reset=True),
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