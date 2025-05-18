import pytest
from database.vector_store import VectorStore
import chromadb
from unittest.mock import Mock, patch


@pytest.fixture
def mock_chroma_client():
    """Fixture to create a mock ChromaDB client"""
    with patch('chromadb.Client') as mock_client:
        # Create a mock collection
        mock_collection = Mock()
        mock_client.return_value.get_or_create_collection.return_value = mock_collection
        yield mock_client

@pytest.fixture
def vector_store(mock_chroma_client):
    """Fixture to create a VectorStore instance with mocked ChromaDB client"""
    return VectorStore()

def test_delete_document(vector_store, mock_chroma_client):
    """Test deleting a document from the vector store"""
    # Arrange
    document_id = "test_doc_123"
    mock_collection = mock_chroma_client.return_value.get_or_create_collection.return_value
    
    # Act
    vector_store.delete_document(document_id)
    
    # Assert
    mock_collection.delete.assert_called_once_with(where={'id': document_id})

def test_delete_nonexistent_document(vector_store, mock_chroma_client):
    """Test deleting a document that doesn't exist"""
    # Arrange
    document_id = "nonexistent_doc"
    mock_collection = mock_chroma_client.return_value.get_or_create_collection.return_value
    
    # Act
    vector_store.delete_document(document_id)
    
    # Assert
    mock_collection.delete.assert_called_once_with(where={'id': document_id})
    # Note: ChromaDB doesn't raise an error for deleting non-existent documents

def test_delete_document_with_empty_id(vector_store, mock_chroma_client):
    """Test deleting a document with empty ID"""
    # Arrange
    document_id = ""
    mock_collection = mock_chroma_client.return_value.get_or_create_collection.return_value
    
    # Act
    vector_store.delete_document(document_id)
    
    # Assert
    mock_collection.delete.assert_called_once_with(where={'id': document_id})

def test_delete_document_with_special_characters(vector_store, mock_chroma_client):
    """Test deleting a document with special characters in ID"""
    # Arrange
    document_id = "test@doc#123"
    mock_collection = mock_chroma_client.return_value.get_or_create_collection.return_value
    
    # Act
    vector_store.delete_document(document_id)
    
    # Assert
    mock_collection.delete.assert_called_once_with(where={'id': document_id})
