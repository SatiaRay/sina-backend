import pytest
from fastapi.testclient import TestClient
import json
from pathlib import Path
from api.main import app

client = TestClient(app)

def test_get_functions_map_success():
    """Test successful retrieval of functions map"""
    response = client.get("/ai-functions/map")
    
    assert response.status_code == 200
    
    # Verify response structure
    data = response.json()
    assert "functions" in data
    assert isinstance(data["functions"], list)
    
    # Verify first function structure if exists
    if data["functions"]:
        first_function = data["functions"][0]
        assert "type" in first_function
        assert "name" in first_function
        assert "description" in first_function
        assert "parameters" in first_function

def test_get_functions_map_file_not_found(monkeypatch):
    """Test error handling when map file is not found"""
    def mock_open(*args, **kwargs):
        raise FileNotFoundError("Map file not found")
    
    # Mock the open function to simulate file not found
    monkeypatch.setattr("builtins.open", mock_open)
    
    response = client.get("/ai-functions/map")
    
    assert response.status_code == 500
    assert "Error loading functions map" in response.json()["detail"]

def test_get_functions_map_invalid_json(monkeypatch):
    """Test error handling when map file contains invalid JSON"""
    def mock_open(*args, **kwargs):
        class MockFile:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                return "invalid json content"
        return MockFile()
    
    # Mock the open function to return invalid JSON
    monkeypatch.setattr("builtins.open", mock_open)
    
    response = client.get("/ai-functions/map")
    
    assert response.status_code == 500
    assert "Error loading functions map" in response.json()["detail"] 