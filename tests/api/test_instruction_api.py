import pytest
from api.main import app

TEST_INSTRUCTION = {
    "label": "Test Instruction",
    "text": "This is a test instruction",
    "status": True,
    "agent_type": "text_agent",
}


@pytest.fixture(scope="function")
def test_instruction(client):
    response = client.post("/instructions/", json=TEST_INSTRUCTION)
    assert response.status_code == 200
    return response.json()


def test_create_instruction(client):
    response = client.post("/instructions/", json=TEST_INSTRUCTION)
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == TEST_INSTRUCTION["label"]
    assert data["text"] == TEST_INSTRUCTION["text"]
    assert data["status"] == TEST_INSTRUCTION["status"]
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_get_instructions(client):
    # Insert at least one instruction
    response = client.post("/instructions/", json=TEST_INSTRUCTION)
    assert response.status_code == 200
    response = client.get("/instructions/?agent_type=text_agent")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert "pages" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) > 0


def test_get_instructions_active_only(client):
    response = client.post("/instructions/", json=TEST_INSTRUCTION)
    assert response.status_code == 200
    response = client.get("/instructions/?active_only=true&agent_type=text_agent")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert "pages" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) > 0
    for instruction in data["items"]:
        assert instruction["status"] is True
        assert instruction["label"] == TEST_INSTRUCTION["label"]
        assert instruction["text"] == TEST_INSTRUCTION["text"]


def test_get_instructions_pagination(client):
    for i in range(15):
        test_data = TEST_INSTRUCTION.copy()
        test_data["label"] = f"Test Instruction {i}"
        response = client.post("/instructions/", json=test_data)
        assert response.status_code == 200
    response = client.get("/instructions/?page=1&size=10&agent_type=text_agent")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10
    assert data["page"] == 1
    assert data["size"] == 10
    assert data["total"] >= 15
    assert data["pages"] >= 2
    response = client.get("/instructions/?page=2&size=10&agent_type=text_agent")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 0
    assert data["page"] == 2
    assert data["size"] == 10


def test_get_instruction(client, test_instruction):
    response = client.get(f"/instructions/{test_instruction['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_instruction["id"]
    assert data["label"] == test_instruction["label"]
    assert data["text"] == test_instruction["text"]


def test_get_nonexistent_instruction(client):
    response = client.get("/instructions/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"


def test_update_instruction(client, test_instruction):
    update_data = {
        "label": "Updated Label",
        "text": "Updated text",
        "status": False,
        "agent_type": "text_agent",
    }
    response = client.put(f"/instructions/{test_instruction['id']}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == update_data["label"]
    assert data["text"] == update_data["text"]
    assert data["status"] == update_data["status"]


def test_update_nonexistent_instruction(client):
    update_data = {
        "label": "Updated Label",
        "text": "Updated text",
        "status": False,
        "agent_type": "text_agent",
    }
    response = client.put("/instructions/99999", json=update_data)
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"


def test_delete_instruction(client, test_instruction):
    response = client.delete(f"/instructions/{test_instruction['id']}")
    assert response.status_code == 200
    assert response.json()["message"] == "Instruction deleted successfully"
    get_response = client.get(f"/instructions/{test_instruction['id']}")
    assert get_response.status_code == 404


def test_delete_nonexistent_instruction(client):
    response = client.delete("/instructions/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"


def test_enable_instruction(client, test_instruction):
    # First disable the instruction
    response = client.patch(f"/instructions/{test_instruction['id']}/disable")
    assert response.status_code == 200
    # Then enable it
    response = client.patch(f"/instructions/{test_instruction['id']}/enable")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is True


def test_disable_instruction(client, test_instruction):
    response = client.patch(f"/instructions/{test_instruction['id']}/disable")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is False


def test_enable_nonexistent_instruction(client):
    response = client.patch("/instructions/99999/enable")
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"


def test_disable_nonexistent_instruction(client):
    response = client.patch("/instructions/99999/disable")
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"


def test_create_instruction_validation(client):
    invalid_data = {"label": "Test Label"}  # Missing text field
    response = client.post("/instructions/", json=invalid_data)
    assert response.status_code == 422
    invalid_data = {"label": "", "text": "", "status": True, "agent_type": "text_agent"}
    response = client.post("/instructions/", json=invalid_data)
    assert response.status_code == 422
