import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, mock_open, MagicMock
import json
import sys
from pathlib import Path

# Add the project root to the path
root_dir = Path(__file__).parent.parent.parent
sys.path.append(str(root_dir))

from api.main import app
import api.system as system_mod

client = TestClient(app)

MOCK_SETTINGS = {"site_name": "TestBot", "text_agent_model": "mock-model-v1"}

MOCK_SCHEMA = {
    "type": "object",
    "properties": {
        "site_name": {"type": "string"},
        "text_agent_model": {"type": "string"},
    },
    "required": ["site_name", "text_agent_model"],
    "additionalProperties": False,
}


@pytest.fixture(autouse=True)
def patch_settings_schema(monkeypatch):
    # Patch the SYSTEM_SETTINGS_SCHEMA in the system module
    monkeypatch.setattr(system_mod, "SYSTEM_SETTINGS_SCHEMA", MOCK_SCHEMA)
    yield


@patch("api.system.open", new_callable=mock_open, read_data=json.dumps(MOCK_SETTINGS))
@patch("api.system.os.path.exists", return_value=True)
def test_get_system_settings(mock_exists, mock_file):
    response = client.get("/system/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["site_name"] == MOCK_SETTINGS["site_name"]
    assert data["text_agent_model"] == MOCK_SETTINGS["text_agent_model"]
    mock_file.assert_called_with(system_mod.SYSTEM_SETTINGS_PATH, "r", encoding="utf-8")


@patch("api.system.open", new_callable=mock_open)
@patch("api.system.os.path.exists", return_value=True)
def test_post_system_settings_valid(mock_exists, mock_file):
    with patch.object(
        system_mod.config, "get", return_value=["mock-model-v1", "other-model"]
    ):
        response = client.post("/system/settings", json=MOCK_SETTINGS)
        assert response.status_code == 200
        assert response.json()["message"] == "Settings updated successfully"
        mock_file.assert_called_with(
            system_mod.SYSTEM_SETTINGS_PATH, "w", encoding="utf-8"
        )
        handle = mock_file()
        handle.write.assert_called()  # Should write JSON


@patch("api.system.open", new_callable=mock_open)
def test_post_system_settings_invalid(mock_file):
    # Missing required field
    bad_settings = {"site_name": "TestBot"}
    response = client.post("/system/settings", json=bad_settings)
    assert response.status_code == 400
    assert "Invalid settings" in response.json()["detail"]

    # Extra field
    bad_settings2 = {
        "site_name": "TestBot",
        "text_agent_model": "mock-model",
        "extra": 123,
    }
    response2 = client.post("/system/settings", json=bad_settings2)
    assert response2.status_code == 400
    assert "Invalid settings" in response2.json()["detail"]


@patch("api.system.open", new_callable=mock_open)
def test_post_system_settings_invalid_model(mock_file):
    # text_agent_model not in allowed models
    bad_model_settings = {
        "site_name": "TestBot",
        "text_agent_model": "not-allowed-model",
    }
    mock_config = MagicMock()
    mock_config.get.return_value = ["mock-model-v1", "other-model"]
    with patch("api.system.config", mock_config):
        response = client.post("/system/settings", json=bad_model_settings)
        assert response.status_code == 400
        assert "Invalid text_agent_model" in response.json()["detail"]
    # Also test with allowed model (should pass)
    good_model_settings = {"site_name": "TestBot", "text_agent_model": "mock-model-v1"}
    mock_config2 = MagicMock()
    mock_config2.get.return_value = ["mock-model-v1", "other-model"]
    with patch("api.system.config", mock_config2):
        response = client.post("/system/settings", json=good_model_settings)
        assert response.status_code == 200
        assert response.json()["message"] == "Settings updated successfully"


def test_get_config_schema():
    mock_config = MagicMock()
    mock_config.get.return_value = ["model-a", "model-b"]
    with patch("api.system.config", mock_config):
        response = client.get("/system/config-schema")
        assert response.status_code == 200
        data = response.json()
        assert "schema" in data
        assert "allowed_text_models" in data
        assert data["schema"] == system_mod.SYSTEM_SETTINGS_SCHEMA
        assert data["allowed_text_models"] == ["model-a", "model-b"]
