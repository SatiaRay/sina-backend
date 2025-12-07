import pytest
from unittest.mock import MagicMock, patch
from src.repositories import DocumentRepository

class DummyRepo(DocumentRepository):
    def __init__(self):
        pass  # skip DB initialization for isolated method tests

def test_to_vector_data_standard_fields():
    repo = DummyRepo()
    data = {
        'text': 'example text',
        'title': 'example',
        'tag': 'tag1',
        'status': True
    }
    expected = {
        'text': 'example text',
        'metadata': {'title': 'example', 'tag': 'tag1', 'status': True}
    }
    assert repo._to_vector_data(data) == expected

def test_to_vector_data_extra_fields():
    repo = DummyRepo()
    data = {
        'text': 'sample',
        'foo': 123,
        'bar': 'baz',
    }
    expected = {
        'text': 'sample',
        'metadata': {'foo': 123, 'bar': 'baz'}
    }
    assert repo._to_vector_data(data) == expected

def test_to_vector_data_text_only():
    repo = DummyRepo()
    data = {
        'text': 'only text',
    }
    expected = {
        'text': 'only text',
        'metadata': {}
    }
    assert repo._to_vector_data(data) == expected

def test_to_vector_data_missing_text():
    repo = DummyRepo()
    data = {
        'title': 'no text',
        'tag': 'missing',
    }
    expected = {
        'text': None,
        'metadata': {'title': 'no text', 'tag': 'missing'}
    }
    assert repo._to_vector_data(data) == expected

# ---------------------- CRUD tests below ----------------------------
@pytest.fixture
def repo_with_mocks():
    repo = DocumentRepository.__new__(DocumentRepository)  # skip __init__
    repo.model_class = MagicMock()
    repo.db = MagicMock()
    # Patch global vector inside src.repositories
    patcher = patch("src.repositories.vector", autospec=True)
    repo._vector_patcher = patcher
    repo.vector = patcher.start()
    yield repo
    patcher.stop()

def test_create(repo_with_mocks):
    repo = repo_with_mocks
    data = {'text': 'hello', 'title': 'Title'}
    repo.model_class.return_value = MagicMock()
    repo.vector.add_documents.return_value = ['vid123']
    instance = MagicMock()
    repo.model_class.return_value = instance

    result = repo.create(data)

    repo.vector.add_documents.assert_called_once()
    repo.db.add.assert_called_once_with(instance)
    repo.db.commit.assert_called_once()
    repo.db.refresh.assert_called_once_with(instance)
    assert result == instance

def test_get(repo_with_mocks):
    repo = repo_with_mocks
    mock_query = MagicMock()
    repo.db.query.return_value.filter.return_value.first.return_value = MagicMock(vector_id='vidA')
    doc = repo.db.query.return_value.filter.return_value.first.return_value
    repo.vector.get_document_by_id.return_value = {'text': 'abc', 'metadata': {'x': 1}}
    repo._merge_vector_data = MagicMock(return_value='merged_doc')
    # with vector
    result = repo.get(1)
    repo.vector.get_document_by_id.assert_called()
    repo._merge_vector_data.assert_called()
    assert result == 'merged_doc'
    # without vector
    out = repo.get(1, without_vector=True)
    assert out == doc

def test_get_all(repo_with_mocks):
    repo = repo_with_mocks
    mock_doc = MagicMock(vector_id='v1')
    repo.db.query.return_value.offset.return_value.limit.return_value.all.return_value = [mock_doc]
    repo.vector.get_all_documents.return_value = [{'id': 'v1', 'text': 'T', 'metadata': {'a': 1}}]
    repo._merge_vector_data = MagicMock()
    out = repo.get_all()
    repo.vector.get_all_documents.assert_called()
    repo._merge_vector_data.assert_called()
    assert isinstance(out, list)
    # without vector
    raw = repo.get_all(without_vector=True)
    assert isinstance(raw, list)

def test_update(repo_with_mocks):
    repo = repo_with_mocks
    data = {'text': 'up', 'title': 'T'}
    instance = MagicMock(vector_id='v123')
    repo.get = MagicMock(return_value=instance)
    repo.vector.update_document = MagicMock()
    repo.db.commit = MagicMock()
    repo.db.refresh = MagicMock()
    out = repo.update(1, data)
    repo.vector.update_document.assert_called_once_with(instance.vector_id, repo._to_vector_data(data))
    repo.db.commit.assert_called_once()
    repo.db.refresh.assert_called_once_with(instance)
    assert out == instance

def test_delete(repo_with_mocks):
    repo = repo_with_mocks
    instance = MagicMock(vector_id='vx')
    repo.get = MagicMock(return_value=instance)
    repo.vector.delete_documents = MagicMock()
    repo.db.delete = MagicMock()
    repo.db.commit = MagicMock()
    res = repo.delete(2)
    repo.vector.delete_documents.assert_called_once_with([instance.vector_id])
    repo.db.delete.assert_called_once_with(instance)
    repo.db.commit.assert_called_once()
    assert res is True
    # test raises on not found
    repo.get = MagicMock(return_value=None)
    with pytest.raises(Exception):
        repo.delete(404)
