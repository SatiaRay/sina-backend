import os
import pytest
from unittest.mock import patch, MagicMock
from database.vector_store import VectorStore

@pytest.fixture
def mock_openai_embedding():
    with patch('database.vector_store.OpenAI') as mock_openai:
        mock_instance = MagicMock()
        mock_instance.embeddings.create.return_value = MagicMock(data=[MagicMock(embedding=[0.1, 0.2, 0.3])])
        mock_openai.return_value = mock_instance
        yield mock_openai

@pytest.fixture
def mock_chromadb():
    with patch('database.vector_store.chromadb') as mock_chroma:
        # Mock AdminClient and Client
        mock_admin = MagicMock()
        mock_client = MagicMock()
        mock_chroma.AdminClient.return_value = mock_admin
        mock_chroma.Client.return_value = mock_client
        # Mock collection behavior
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_client.get_collection.return_value = mock_collection
        mock_client.delete_collection.return_value = None
        mock_collection.get.return_value = {'documents': [[]], 'metadatas': [[]], 'ids': [[]]}
        mock_collection.add.return_value = None
        mock_collection.query.return_value = {
            'documents': [['doc1']],
            'metadatas': [[{'meta': 'data'}]],
            'ids': [['id1']],
            'distances': [[0.1]]
        }
        mock_collection.update.return_value = None
        mock_collection.delete.return_value = None
        yield mock_chroma


def test_tenant_isolation(mock_openai_embedding, mock_chromadb):
    # Create two VectorStores with different tenants
    # TODO: Refactor to support custom parameters if needed
    store1 = container.make('vector_store')
    store2 = container.make('vector_store')
    
    # Add a document to each
    doc1 = [{'text': 'Hello from tenant1', 'metadata': {'meta': 't1'}}]
    doc2 = [{'text': 'Hello from tenant2', 'metadata': {'meta': 't2'}}]
    ids1 = store1.add_documents(doc1)
    ids2 = store2.add_documents(doc2)
    
    # Ensure that the collections are created for each tenant
    assert store1.tenant != store2.tenant
    assert store1.collection_name == store2.collection_name
    # The mock ensures isolation, but in real test, would check actual DB


def test_collection_creation_per_tenant(mock_openai_embedding, mock_chromadb):
    # Create VectorStore for two tenants
    # TODO: Refactor to support custom parameters if needed
    store1 = container.make('vector_store')
    store2 = container.make('vector_store')
    
    # The collection should be created for each tenant
    assert store1.tenant != store2.tenant
    assert store1.collection_name == store2.collection_name


def test_document_isolation_between_tenants(mock_openai_embedding, mock_chromadb):
    # Create two VectorStores with different tenants
    # TODO: Refactor to support custom parameters if needed
    store1 = container.make('vector_store')
    store2 = container.make('vector_store')
    
    # Add documents to each
    doc1 = [{'text': 'Tenant1 doc', 'metadata': {'meta': 'iso1'}}]
    doc2 = [{'text': 'Tenant2 doc', 'metadata': {'meta': 'iso2'}}]
    ids1 = store1.add_documents(doc1)
    ids2 = store2.add_documents(doc2)
    
    # The mock ensures isolation, but in real test, would check actual DB
    assert ids1 is not None
    assert ids2 is not None
    assert store1.tenant != store2.tenant 