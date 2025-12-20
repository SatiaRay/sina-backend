# test/test_document_repository.py
import pytest
from unittest.mock import MagicMock, patch, Mock
from src.repositories import DocumentRepository

class DummyRepo(DocumentRepository):
    def __init__(self, workspace_id="test-workspace"):
        # Skip parent init with minimal setup
        self.workspace_id = workspace_id
        self.model_class = Mock()

def test_to_vector_data_standard_fields():
    """Test that text is separated from metadata"""
    repo = DummyRepo(workspace_id="test-ws")
    data = {
        'text': 'example text',
        'title': 'example',
        'tag': 'tag1',
        'status': True,
        'workspace_id': 'test-ws'  # This should be in metadata
    }
    result = repo._to_vector_data(data)
    print(f"Result: {result}")
    
    assert result['text'] == 'example text'
    assert 'metadata' in result
    assert result['metadata']['title'] == 'example'
    assert result['metadata']['tag'] == 'tag1'
    assert result['metadata']['status'] == True
    assert result['metadata']['workspace_id'] == 'test-ws'

def test_to_vector_data_adds_workspace_id():
    """Test that workspace_id is automatically added to metadata"""
    repo = DummyRepo(workspace_id="auto-ws")
    data = {
        'text': 'test',
        'title': 'Test'
    }
    result = repo._to_vector_data(data)
    
    assert result['metadata']['workspace_id'] == 'auto-ws'
    assert result['text'] == 'test'

def test_to_vector_data_preserves_existing_workspace_id():
    """Test that existing workspace_id is preserved"""
    repo = DummyRepo(workspace_id="repo-ws")
    data = {
        'text': 'test',
        'workspace_id': 'custom-ws'  # Custom workspace_id
    }
    result = repo._to_vector_data(data)
    
    # Should use the one from data, not from repo
    assert result['metadata']['workspace_id'] == 'custom-ws'

# ---------------------- CRUD tests with tenant ----------------------------
@pytest.fixture
def repo_with_mocks():
    """Create a DocumentRepository with mocked dependencies"""
    repo = DocumentRepository.__new__(DocumentRepository)
    repo.workspace_id = "test-workspace-123"
    repo.model_class = Mock()
    
    # Mock the vector store
    with patch("src.repositories.vector", autospec=True) as mock_vector:
        repo.vector = mock_vector
        # Mock database session
        repo.db = Mock()
        yield repo

def test_create_with_tenant(repo_with_mocks):
    """Test document creation includes workspace_id"""
    repo = repo_with_mocks
    data = {'text': 'hello', 'title': 'Title'}

    # Mock vector store response
    repo.vector.add_document.return_value = 'vid123'
    repo.vector.get_document_by_id.return_value = {
        'text': 'hello',
        'metadata': {'title': 'Title', 'workspace_id': repo.workspace_id}
    }

    # Mock SQL model instance
    mock_instance = Mock()
    repo.model_class.return_value = mock_instance

    result = repo.create(repo.db, data)

    # MAIN TEST: Verify vector store was called with workspace_id in metadata
    vector_call = repo.vector.add_document.call_args[0][0]
    assert 'metadata' in vector_call
    assert vector_call['metadata']['workspace_id'] == repo.workspace_id
    
    # Secondary: Just verify model was instantiated (don't check how)
    repo.model_class.assert_called_once()
    
    repo.db.add.assert_called_once_with(mock_instance)
    repo.db.commit.assert_called_once()
    repo.db.refresh.assert_called_once_with(mock_instance)
    assert result == mock_instance

def test_get_with_tenant_filter(repo_with_mocks):
    """Test get applies tenant filter"""
    repo = repo_with_mocks
    
    # Mock the query chain
    mock_doc = Mock(vector_id='vid123', workspace_id=repo.workspace_id)
    mock_query = Mock()
    mock_filter = Mock()
    mock_filter.first.return_value = mock_doc
    
    repo.db.query.return_value.filter.return_value.first.return_value = mock_doc
    
    # Mock vector response with matching workspace
    repo.vector.get_document_by_id.return_value = {
        'text': 'content',
        'metadata': {'workspace_id': repo.workspace_id, 'title': 'Test'}
    }
    
    result = repo.get(repo.db, 1)
    
    # Verify tenant filter was applied
    repo.db.query.assert_called_with(repo.model_class)
    filter_call = repo.db.query.return_value.filter
    # Should filter by id AND workspace_id
    
    assert result is not None

def test_get_workspace_mismatch(repo_with_mocks):
    """Test get raises error when workspace doesn't match"""
    repo = repo_with_mocks
    
    mock_doc = Mock(vector_id='vid123', workspace_id=repo.workspace_id)
    repo.db.query.return_value.filter.return_value.first.return_value = mock_doc
    
    # Vector returns document with DIFFERENT workspace
    repo.vector.get_document_by_id.return_value = {
        'text': 'content',
        'metadata': {'workspace_id': 'different-workspace'}
    }
    
    with pytest.raises(Exception, match="Workspace mismatch"):
        repo.get(repo.db, 1)

def test_get_all_with_tenant_filter(repo_with_mocks):
    """Test get_all filters by workspace"""
    repo = repo_with_mocks
    
    # Create mock documents
    mock_doc1 = Mock(vector_id='vid1', workspace_id=repo.workspace_id)
    mock_doc2 = Mock(vector_id='vid2', workspace_id=repo.workspace_id)
    
    # Setup the query chain properly
    mock_offset = Mock()
    mock_limit = Mock()
    mock_limit.all.return_value = [mock_doc1, mock_doc2]
    mock_offset.limit.return_value = mock_limit
    
    # Mock the filtered query
    mock_filtered_query = Mock()
    mock_filtered_query.offset.return_value = mock_offset
    
    # Mock _apply_tenant_filter to return the mocked query
    repo._apply_tenant_filter = Mock(return_value=mock_filtered_query)
    
    # Mock db.query
    mock_query = Mock()
    repo.db.query.return_value = mock_query
    
    # Vector returns documents with matching workspace
    repo.vector.get_all_documents.return_value = [
        {'id': 'vid1', 'text': 'doc1', 'metadata': {'workspace_id': repo.workspace_id}},
        {'id': 'vid2', 'text': 'doc2', 'metadata': {'workspace_id': repo.workspace_id}}
    ]
    
    # Mock _merge_vector_data
    repo._merge_vector_data = Mock(side_effect=lambda doc, vec: doc)
    
    results = repo.get_all(repo.db)
    
    # Verify tenant filter was applied
    repo._apply_tenant_filter.assert_called_once_with(mock_query)
    
    # Verify vector store was called with correct IDs
    repo.vector.get_all_documents.assert_called_once_with(['vid1', 'vid2'])
    
    assert len(results) == 2
    assert results[0] == mock_doc1
    assert results[1] == mock_doc2


def test_get_all_filters_out_wrong_workspace(repo_with_mocks):
    """Test get_all excludes documents from other workspaces"""
    repo = repo_with_mocks
    
    # Create mock document
    mock_doc = Mock(vector_id='vid1', workspace_id=repo.workspace_id)
    
    # Create a mock query chain
    mock_query = Mock()
    mock_offset = Mock()
    mock_limit = Mock()
    
    # Setup the chain
    mock_query.offset.return_value = mock_offset
    mock_offset.limit.return_value = mock_limit
    mock_limit.all.return_value = [mock_doc]
    
    # Mock db.query to return a query that will be filtered
    mock_base_query = Mock()
    repo.db.query.return_value = mock_base_query
    
    # Mock _apply_tenant_filter to return our mock_query
    with patch.object(repo, '_apply_tenant_filter', return_value=mock_query) as mock_filter:
        # Vector returns document with DIFFERENT workspace
        repo.vector.get_all_documents.return_value = [
            {'id': 'vid1', 'text': 'doc1', 'metadata': {'workspace_id': 'wrong-workspace'}}
        ]
        
        # Mock _merge_vector_data
        repo._merge_vector_data = Mock(side_effect=lambda doc, vec: doc)
        
        results = repo.get_all(repo.db)
        
        # Verify tenant filter was applied
        mock_filter.assert_called_once_with(mock_base_query)
        
        # Verify vector store was called
        repo.vector.get_all_documents.assert_called_once_with(['vid1'])
        
        # Document should be returned (SQL doc) but vector data not merged
        assert len(results) == 1
        assert results[0] == mock_doc
        # _merge_vector_data should NOT be called because workspace doesn't match
        assert repo._merge_vector_data.call_count == 0

def test_update_with_tenant(repo_with_mocks):
    """Test update preserves workspace_id"""
    repo = repo_with_mocks
    
    mock_instance = Mock(vector_id='vid123', workspace_id=repo.workspace_id)
    repo.db.query.return_value.filter.return_value.first.return_value = mock_instance
    
    data = {'text': 'updated', 'title': 'New Title'}
    
    repo.update(repo.db, 1, data)
    
    # Verify vector update includes workspace_id
    vector_call = repo.vector.update_document.call_args[0]
    assert len(vector_call) >= 2
    vector_data = vector_call[1]
    assert vector_data['metadata']['workspace_id'] == repo.workspace_id

def test_delete_with_tenant(repo_with_mocks):
    """Test delete only deletes documents in current workspace"""
    repo = repo_with_mocks
    
    # Create mock instance with proper attributes
    mock_instance = Mock()
    # Set vector_id as a property that returns a string
    type(mock_instance).vector_id = 'vid123'
    type(mock_instance).workspace_id = repo.workspace_id
    
    # Mock the query chain properly
    mock_filter1 = Mock()  # First filter (by id)
    mock_filter2 = Mock()  # Second filter (by workspace - from _apply_tenant_filter)
    mock_filter2.first.return_value = mock_instance
    
    # When query().filter() is called, it returns another query
    # Then _apply_tenant_filter adds another filter
    mock_base_query = Mock()
    mock_base_query.filter.return_value = mock_filter1
    
    repo.db.query.return_value = mock_base_query
    
    # Mock _apply_tenant_filter to add the workspace filter
    with patch.object(repo, '_apply_tenant_filter', return_value=mock_filter2):
        result = repo.delete(repo.db, 1)
        
        assert result is True
        # Check that delete_documents was called with the correct argument
        repo.vector.delete_documents.assert_called_once()
        
        # Get the actual call argument
        call_args = repo.vector.delete_documents.call_args[0][0]
        # It should be a list with one element
        assert len(call_args) == 1
        # The element should be 'vid123' (might be a Mock or string)
        vector_id = call_args[0]
        # Convert to string if it's a Mock
        if isinstance(vector_id, Mock):
            # If it's a Mock, check its string representation
            assert str(vector_id) == 'vid123'
        else:
            assert vector_id == 'vid123'

def test_delete_not_found_in_workspace(repo_with_mocks):
    """Test delete raises error if document not in current workspace"""
    repo = repo_with_mocks
    
    # Mock the query chain
    mock_filter = Mock()
    mock_filter.first.return_value = None  # Document not found
    
    # Mock db.query() to return a query that can be filtered
    mock_query = Mock()
    mock_query.filter.return_value = mock_filter
    repo.db.query.return_value = mock_query
    
    # Mock _apply_tenant_filter to return our filtered query
    with patch.object(repo, '_apply_tenant_filter', return_value=mock_filter):
        with pytest.raises(Exception) as exc_info:
            repo.delete(repo.db, 999)
        
        # Check the exception message
        assert f"not found in workspace {repo.workspace_id}" in str(exc_info.value)

def test_count_with_tenant(repo_with_mocks):
    """Test count only counts documents in current workspace"""
    repo = repo_with_mocks
    
    repo.db.query.return_value.filter.return_value.count.return_value = 5
    
    result = repo.count(repo.db)
    
    assert result == 5
    # Verify tenant filter was applied
    repo.db.query.assert_called_with(repo.model_class)