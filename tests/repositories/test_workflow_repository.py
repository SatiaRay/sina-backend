import pytest
from unittest.mock import Mock, patch
from database.repositories.workflow_repository import WorkflowRepository
from database.models import Workflow

@pytest.fixture
def mock_db():
    return Mock()

@pytest.fixture
def workflow_repository(mock_db):
    return WorkflowRepository(mock_db)

def test_get_active_workflows_schemas(workflow_repository, mock_db):
    # Arrange
    mock_schemas = [
        {"id": "node1", "type": "start"},
        {"id": "node2", "type": "end"}
    ]
    
    # Create mock workflow objects with different statuses
    mock_workflows = [
        (mock_schemas[0],),  # Active workflow
        (mock_schemas[1],),  # Active workflow
    ]
    
    # Setup mock query
    mock_query = Mock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = mock_workflows
    
    # Act
    result = workflow_repository.get_active_workflows_schemas()
    
    # Assert
    # Verify that only active workflows were queried
    mock_query.filter.assert_called_once()
    filter_call = mock_query.filter.call_args[0][0]
    assert str(filter_call) == str(Workflow.status == True)
    
    # Verify that only schemas were returned
    assert result == mock_schemas
    assert len(result) == 2
    
    # Verify that the result contains only the schema data
    for schema in result:
        assert isinstance(schema, dict)
        assert "id" in schema
        assert "type" in schema

def test_get_active_workflows_schemas_empty(workflow_repository, mock_db):
    # Arrange
    mock_db.query.return_value.filter.return_value.all.return_value = []
    
    # Act
    result = workflow_repository.get_active_workflows_schemas()
    
    # Assert
    assert result == []
    assert len(result) == 0

def test_get_active_workflows_schemas_error(workflow_repository, mock_db):
    # Arrange
    mock_db.query.side_effect = Exception("Database error")
    
    # Act & Assert
    with pytest.raises(Exception) as exc_info:
        workflow_repository.get_active_workflows_schemas()
    
    assert str(exc_info.value) == "Database error"
    mock_db.rollback.assert_called_once() 