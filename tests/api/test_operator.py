import pytest
from fastapi.testclient import TestClient
from api.main import app
from database.models import SessionLocal, User
from api.auth import get_password_hash
from uuid import uuid4

client = TestClient(app)

def create_operator_user(db, email=None):
    if email is None:
        email = f"operator_{uuid4()}@example.com"
    user = User(
        email=email,
        password_hash=get_password_hash("password123"),
        user_type="operator",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_auth_headers(user):
    # This assumes you have a way to get a JWT for the user
    # For now, just return an empty dict or mock as needed
    return {"Authorization": f"Bearer testtoken-for-{user.email}"}

@pytest.fixture(scope="function")
def db():
    db = SessionLocal()
    yield db
    db.close()

@pytest.fixture(scope="function")
def operator_user(db):
    user = create_operator_user(db)
    print(f"DEBUG: Created operator_user with id={user.id}, email={user.email}, user_type={user.user_type}")
    return user

@pytest.fixture(autouse=True)
def override_get_current_user(operator_user):
    from api.operator import get_current_user
    app.dependency_overrides[get_current_user] = lambda: operator_user
    yield
    app.dependency_overrides.clear()

def test_create_operator(db, operator_user):
    data = {
        "email": f"newoperator_{uuid4()}@example.com",
        "password": "password123",
        "first_name": "Op",
        "last_name": "Erator"
    }
    response = client.post("/operators/", json=data, headers=get_auth_headers(operator_user))
    assert response.status_code == 200
    result = response.json()
    assert result["email"] == data["email"]
    assert result["first_name"] == data["first_name"]
    assert result["last_name"] == data["last_name"]
    assert result["is_active"] is True

def test_list_operators(db, operator_user):
    response = client.get("/operators/?page=1&per_page=2", headers=get_auth_headers(operator_user))
    assert response.status_code == 200
    data = response.json()
    assert "operators" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["per_page"] == 2

def test_get_operator_detail(db, operator_user):
    response = client.get(f"/operators/{operator_user.id}", headers=get_auth_headers(operator_user))
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == operator_user.id
    assert data["email"] == operator_user.email

def test_update_operator(db, operator_user):
    update_data = {"first_name": "Updated", "is_active": False}
    response = client.put(f"/operators/{operator_user.id}", json=update_data, headers=get_auth_headers(operator_user))
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "Updated"
    assert data["is_active"] is False

def test_delete_operator(db, operator_user):
    response = client.delete(f"/operators/{operator_user.id}", headers=get_auth_headers(operator_user))
    assert response.status_code == 204
    # Should not be found after delete
    response = client.get(f"/operators/{operator_user.id}", headers=get_auth_headers(operator_user))
    assert response.status_code == 404 