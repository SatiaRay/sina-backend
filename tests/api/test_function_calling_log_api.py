import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
import json

# Test data
MOCK_LOGS = [
    {
        "id": 1,
        "timestamp": (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z",
        "tool": "mayoral.searchSubject",
        "params": {"q": "باغ ملی"},
        "user_id": "usr_123",
        "session_id": "sess_456",
        "duration_ms": 150,
        "tokens_used": 50
    },
    {
        "id": 2,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "tool": "mayoral.submitRequest",
        "params": {"mobile": "09123456789"},
        "user_id": "usr_123",
        "session_id": "sess_456",
        "error": "Invalid mobile number",
        "duration_ms": 200,
        "tokens_used": 0
    }
]

MOCK_TOOL_STATS = [
    {"tool": "mayoral.searchSubject", "call_count": 100, "avg_duration": 120.5, "total_tokens": 5000, "error_count": 5},
    {"tool": "mayoral.submitRequest", "call_count": 50, "avg_duration": 200.0, "total_tokens": 2500, "error_count": 10}
]

MOCK_USER_ACTIVITY = {
    "total_calls": 150,
    "avg_duration": 160.25,
    "total_tokens": 7500,
    "error_count": 15,
    "most_used_tools": [
        {"tool": "mayoral.searchSubject", "call_count": 100},
        {"tool": "mayoral.submitRequest", "call_count": 50}
    ]
}

@pytest.fixture
def mock_repo():
    with patch('api.function_calling_log.FunctionCallLogRepository') as mock:
        # Create a mock instance that will be returned by __enter__
        mock_instance = MagicMock()
        mock_instance.get_recent_logs.return_value = []
        
        # Configure the mock to return our instance when used as context manager
        mock.return_value.__enter__.return_value = mock_instance
        yield mock_instance  # Yield the instance mock for assertions

def test_get_logs(mock_repo, client):
    # Setup test data
    test_data = [
        {
            "id": 1,
            "timestamp": datetime.utcnow().isoformat(),
            "tool": "test_tool",
            "params": {"key": "value"},
            "user_id": "user1",
            "session_id": "session1",
            "response": None,
            "error": None,
            "duration_ms": 100,
            "tokens_used": 50,
            "additional_metadata": {}
        },
        {
            "id": 2,
            "timestamp": datetime.utcnow().isoformat(),
            "tool": "test_tool2",
            "params": {"key": "value2"},
            "user_id": "user2",
            "session_id": "session2",
            "response": {"result": "success"},
            "error": "Some error",
            "duration_ms": 200,
            "tokens_used": 0,
            "additional_metadata": {}
        }
    ]
    
    # Configure the mock to return our test data
    mock_repo.get_paginated_logs.return_value = test_data
    mock_repo.get_logs_count.return_value = len(test_data)
    
    # Test with no filters (default pagination)
    response = client.get("/function-calling-logs/")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["items"][0]["tool"] == "test_tool"
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["per_page"] == 50
    assert data["total_pages"] == 1
    
    # Verify the mock was called with default parameters
    mock_repo.get_paginated_logs.assert_called_with(
        hours=24, tool_name=None, user_id=None, 
        min_duration=None, max_duration=None, 
        has_errors=False, offset=0, limit=50
    )
    mock_repo.get_logs_count.assert_called_with(
        hours=24, tool_name=None, user_id=None,
        min_duration=None, max_duration=None,
        has_errors=False
    )
    
    # Test with filters and custom pagination
    response = client.get("/function-calling-logs/?hours=48&tool_name=test_tool&min_duration=100&page=2&per_page=10")
    assert response.status_code == 200
    mock_repo.get_paginated_logs.assert_called_with(
        hours=48, tool_name="test_tool", user_id=None,
        min_duration=100, max_duration=None,
        has_errors=False, offset=10, limit=10
    )
    mock_repo.get_logs_count.assert_called_with(
        hours=48, tool_name="test_tool", user_id=None,
        min_duration=100, max_duration=None,
        has_errors=False
    )

def test_get_logs_pagination_edge_cases(mock_repo, client):
    # Setup test data with 105 items
    test_data = [{"id": i, "tool": f"tool_{i}"} for i in range(105)]
    
    # Configure the mock
    mock_repo.get_paginated_logs.return_value = test_data[:50]
    mock_repo.get_logs_count.return_value = 105
    
    # Test first page
    response = client.get("/function-calling-logs/?per_page=50")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["per_page"] == 50
    assert data["total"] == 105
    assert data["total_pages"] == 3
    
    # Test last page
    mock_repo.get_paginated_logs.return_value = test_data[100:105]
    response = client.get("/function-calling-logs/?page=3&per_page=50")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 3
    assert len(data["items"]) == 5
    
    # Test invalid page number
    response = client.get("/function-calling-logs/?page=0")
    assert response.status_code == 422
    
    # Test invalid per_page
    response = client.get("/function-calling-logs/?per_page=201")
    assert response.status_code == 422
    response = client.get("/function-calling-logs/?per_page=0")
    assert response.status_code == 422

def test_get_logs_error(mock_repo, client):
    # Configure the mock to raise an exception when either pagination method is called
    mock_repo.get_logs_count.side_effect = Exception("DB error")
    mock_repo.get_paginated_logs.side_effect = Exception("DB error")
    
    response = client.get("/function-calling-logs/")
    assert response.status_code == 500
    assert "DB error" in response.json()["detail"]
    
    # Reset the side effects and test with error in get_paginated_logs only
    mock_repo.get_logs_count.side_effect = None
    mock_repo.get_logs_count.return_value = 10
    mock_repo.get_paginated_logs.side_effect = Exception("DB pagination error")
    
    response = client.get("/function-calling-logs/")
    assert response.status_code == 500
    assert "DB pagination error" in response.json()["detail"]
    
    # Test with error in get_logs_count only
    mock_repo.get_paginated_logs.side_effect = None
    mock_repo.get_logs_count.side_effect = Exception("DB count error")
    
    response = client.get("/function-calling-logs/")
    assert response.status_code == 500
    assert "DB count error" in response.json()["detail"]

def test_get_tool_usage_stats(mock_repo, client):
    # Setup mock data
    mock_stats = [
        {
            "tool": "mayoral.searchSubject",
            "call_count": 100,
            "avg_duration": 120.5,
            "total_tokens": 5000,
            "error_count": 5
        },
        {
            "tool": "mayoral.submitRequest",
            "call_count": 50,
            "avg_duration": 200.0,
            "total_tokens": 2500,
            "error_count": 10
        }
    ]
    
    # Configure the mock to return our test data
    mock_repo.get_tool_usage_stats.return_value = mock_stats
    
    # Test with default params
    response = client.get("/function-calling-logs/stats/tools")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["tool"] == "mayoral.searchSubject"
    mock_repo.get_tool_usage_stats.assert_called_with(days=7, top_n=10)
    
    # Test with custom params
    response = client.get("/function-calling-logs/stats/tools?days=30&top_n=5")
    assert response.status_code == 200
    mock_repo.get_tool_usage_stats.assert_called_with(days=30, top_n=5)

def test_get_user_activity(mock_repo, client):
    mock_repo.get_user_activity.return_value = MOCK_USER_ACTIVITY
    
    response = client.get("/function-calling-logs/stats/user/usr_123?days=7")
    assert response.status_code == 200
    data = response.json()
    assert data["total_calls"] == 150
    assert len(data["most_used_tools"]) == 2
    mock_repo.get_user_activity.assert_called_with("usr_123", days=7)

def test_search_logs(mock_repo, client):
    # Create test data with proper response structure
    mock_log = {
        "id": 1,
        "timestamp": datetime.utcnow().isoformat(),
        "tool": "mayoral.searchSubject",
        "params": {"q": "باغ ملی"},
        "user_id": "user1",
        "session_id": "session1",
        "response": {"results": ["item1", "item2"]},  # Proper serializable data
        "error": None,
        "duration_ms": 150,
        "tokens_used": 50,
        "additional_metadata": {}
    }

    mock_repo.search_logs.return_value = [mock_log]
    
    response = client.get("/function-calling-logs/search?query=باغ&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["tool"] == "mayoral.searchSubject"
    assert isinstance(data[0]["response"]["results"], list)  # Verify proper serialization

def test_get_log_by_id(mock_repo, client):
    # Create proper test data
    mock_log = {
        "id": 1,
        "timestamp": datetime.utcnow().isoformat(),
        "tool": "test_tool",
        "params": {"key": "value"},
        "user_id": "user1",
        "session_id": "session1",
        "response": None,
        "error": None,
        "duration_ms": 100,
        "tokens_used": 50,
        "additional_metadata": {}
    }
    
    mock_repo.get_by_id.return_value = mock_log
    
    # Test successful case
    response = client.get("/function-calling-logs/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["tool"] == "test_tool"
    
    # Test not found case
    mock_repo.get_by_id.return_value = None
    response = client.get("/function-calling-logs/999")
    assert response.status_code == 404
    assert "Log not found" in response.json()["detail"]

def test_logs_endpoint_validation(client):
    # Test invalid parameters
    response = client.get("/function-calling-logs/?hours=invalid")
    assert response.status_code == 422
    
    response = client.get("/function-calling-logs/stats/tools?days=invalid")
    assert response.status_code == 422
    
    response = client.get("/function-calling-logs/stats/user/usr_123?days=invalid")
    assert response.status_code == 422
    
    response = client.get("/function-calling-logs/search?limit=invalid")
    assert response.status_code == 422

@pytest.mark.parametrize("endpoint,method", [
    ("/function-calling-logs/", "GET"),
    ("/function-calling-logs/stats/tools", "GET"),
    ("/function-calling-logs/stats/user/usr_123", "GET"),
    ("/function-calling-logs/search?query=test", "GET"),
    ("/function-calling-logs/1", "GET")
])
def test_endpoints_exist(client, endpoint, method):
    response = client.request(method, endpoint)
    assert response.status_code != 404, f"{endpoint} returned 404"