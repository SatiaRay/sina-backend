from typing import Generator
import chromadb
from chromadb.config import Settings

def get_db_connection() -> Generator:
    """
    Creates and yields a ChromaDB client connection.
    """
    try:
        client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory="chroma_db"
        ))
        yield client
    finally:
        # ChromaDB handles connection cleanup automatically
        pass 