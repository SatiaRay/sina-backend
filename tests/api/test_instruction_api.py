import pytest
from api.main import app
from database.repository import InstructionRepository

TEST_INSTRUCTION = {
    "label": "Test Instruction",
    "text": "This is a test instruction",
    "status": True,
}


@pytest.fixture(scope="function")
def test_instruction(db):
    repo = InstructionRepository(db)
    instruction = repo.create(TEST_INSTRUCTION)
    return instruction


def test_create_instruction(client, db):
    response = client.post("/instructions/", json=TEST_INSTRUCTION)
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == TEST_INSTRUCTION["label"]
    assert data["text"] == TEST_INSTRUCTION["text"]
    assert data["status"] == TEST_INSTRUCTION["status"]
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_get_instructions(client, db):
    repo = InstructionRepository(db)
    instruction = repo.create(TEST_INSTRUCTION)
    response = client.get("/instructions/")
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
    assert data["items"][0]["label"] == TEST_INSTRUCTION["label"]
    assert data["items"][0]["text"] == TEST_INSTRUCTION["text"]
    assert data["page"] == 1
    assert data["size"] == 10
    assert data["total"] > 0
    assert data["pages"] > 0


def test_get_instructions_active_only(client, db):
    repo = InstructionRepository(db)
    instruction = repo.create(TEST_INSTRUCTION)
    response = client.get("/instructions/?active_only=true")
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
    assert data["page"] == 1
    assert data["size"] == 10
    assert data["total"] > 0
    assert data["pages"] > 0


def test_get_instructions_pagination(client, db):
    repo = InstructionRepository(db)
    for i in range(15):
        test_data = TEST_INSTRUCTION.copy()
        test_data["label"] = f"Test Instruction {i}"
        repo.create(test_data)
    response = client.get("/instructions/?page=1&size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10
    assert data["page"] == 1
    assert data["size"] == 10
    assert data["total"] >= 15
    assert data["pages"] >= 2
    response = client.get("/instructions/?page=2&size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 0
    assert data["page"] == 2
    assert data["size"] == 10


def test_get_instruction(client, db, test_instruction):
    response = client.get(f"/instructions/{test_instruction.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_instruction.id
    assert data["label"] == test_instruction.label
    assert data["text"] == test_instruction.text


def test_get_nonexistent_instruction(client, db):
    response = client.get("/instructions/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"


def test_update_instruction(client, db, test_instruction):
    update_data = {"label": "Updated Label", "text": "Updated text", "status": False}
    response = client.put(f"/instructions/{test_instruction.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == update_data["label"]
    assert data["text"] == update_data["text"]
    assert data["status"] == update_data["status"]


def test_update_nonexistent_instruction(client, db):
    update_data = {"label": "Updated Label", "text": "Updated text", "status": False}
    response = client.put("/instructions/99999", json=update_data)
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"


def test_delete_instruction(client, db, test_instruction):
    response = client.delete(f"/instructions/{test_instruction.id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Instruction deleted successfully"
    get_response = client.get(f"/instructions/{test_instruction.id}")
    assert get_response.status_code == 404


def test_delete_nonexistent_instruction(client, db):
    response = client.delete("/instructions/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"


def test_enable_instruction(client, db, test_instruction):
    from database.repository import InstructionRepository

    repo = InstructionRepository(db)
    repo.disable_instruction(test_instruction.id)
    response = client.patch(f"/instructions/{test_instruction.id}/enable")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is True


def test_disable_instruction(client, db, test_instruction):
    response = client.patch(f"/instructions/{test_instruction.id}/disable")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is False


def test_enable_nonexistent_instruction(client, db):
    response = client.patch("/instructions/99999/enable")
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"


def test_disable_nonexistent_instruction(client, db):
    response = client.patch("/instructions/99999/disable")
    assert response.status_code == 404
    assert response.json()["detail"] == "Instruction not found"


def test_create_instruction_validation(client, db):
    invalid_data = {"label": "Test Label"}
    response = client.post("/instructions/", json=invalid_data)
    assert response.status_code == 422
    invalid_data = {"label": "", "text": "", "status": True}
    response = client.post("/instructions/", json=invalid_data)
    assert response.status_code == 422
