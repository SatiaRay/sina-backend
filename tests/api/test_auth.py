import pytest
from api.main import app
from database.models import User
import jwt
from api.auth import SECRET_KEY, ALGORITHM
from datetime import datetime, timedelta


class TestAuthEndpoints:
    """Test cases for authentication endpoints"""

    def test_register_user_success(self, client, db):
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",
            "first_name": "John",
            "last_name": "Doe",
            "user_type": "customer",
        }
        response = client.post("/auth/register", json=user_data)
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["first_name"] == user_data["first_name"]
        assert data["last_name"] == user_data["last_name"]
        assert data["user_type"] == user_data["user_type"]
        assert data["is_active"] is True
        assert data["is_verified"] is False
        assert "id" in data
        assert "created_at" in data
        assert "password_hash" not in data

    def test_register_user_duplicate_email(self, client, db):
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",
            "user_type": "customer",
        }
        response1 = client.post("/auth/register", json=user_data)
        assert response1.status_code == 201
        response2 = client.post("/auth/register", json=user_data)
        assert response2.status_code == 400
        assert "Email already registered" in response2.json()["detail"]

    def test_register_user_invalid_user_type(self, client, db):
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",
            "user_type": "invalid_type",
        }
        response = client.post("/auth/register", json=user_data)
        assert response.status_code == 400
        assert "Invalid user type" in response.json()["detail"]

    def test_register_user_minimal_data(self, client, db):
        user_data = {"email": "test@example.com", "password": "securepassword123"}
        response = client.post("/auth/register", json=user_data)
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["user_type"] == "customer"
        assert data["first_name"] is None
        assert data["last_name"] is None

    def test_login_user_success(self, client, db):
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",
            "user_type": "customer",
        }
        register_response = client.post("/auth/register", json=user_data)
        assert register_response.status_code == 201
        login_data = {"email": "test@example.com", "password": "securepassword123"}
        login_response = client.post("/auth/login", json=login_data)
        assert login_response.status_code == 200
        data = login_response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == user_data["email"]
        token = data["access_token"]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == user_data["email"]

    def test_login_user_invalid_credentials(self, client, db):
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",
            "user_type": "customer",
        }
        register_response = client.post("/auth/register", json=user_data)
        assert register_response.status_code == 201
        login_data = {"email": "test@example.com", "password": "wrongpassword"}
        login_response = client.post("/auth/login", json=login_data)
        assert login_response.status_code == 401
        assert "Incorrect email or password" in login_response.json()["detail"]

    def test_login_user_nonexistent_email(self, client, db):
        login_data = {
            "email": "nonexistent@example.com",
            "password": "securepassword123",
        }
        login_response = client.post("/auth/login", json=login_data)
        assert login_response.status_code == 401
        assert "Incorrect email or password" in login_response.json()["detail"]

    def test_get_current_user_success(self, client, db):
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",
            "user_type": "customer",
        }
        register_response = client.post("/auth/register", json=user_data)
        assert register_response.status_code == 201
        login_data = {"email": "test@example.com", "password": "securepassword123"}
        login_response = client.post("/auth/login", json=login_data)
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        me_response = client.get("/auth/me", headers=headers)
        assert me_response.status_code == 200
        data = me_response.json()
        assert data["email"] == user_data["email"]
        assert data["user_type"] == user_data["user_type"]

    def test_get_current_user_invalid_token(self, client, db):
        headers = {"Authorization": "Bearer invalid_token"}
        me_response = client.get("/auth/me", headers=headers)
        assert me_response.status_code == 401
        assert "Could not validate credentials" in me_response.json()["detail"]

    def test_get_current_user_no_token(self, client, db):
        me_response = client.get("/auth/me")
        assert me_response.status_code == 403
        assert "Not authenticated" in me_response.json()["detail"]

    def test_logout_user(self, client, db):
        response = client.post("/auth/logout")
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"

    def test_register_user_with_admin_type(self, client, db):
        user_data = {
            "email": "admin@example.com",
            "password": "securepassword123",
            "first_name": "Admin",
            "last_name": "User",
            "user_type": "admin",
        }
        response = client.post("/auth/register", json=user_data)
        assert response.status_code == 201
        data = response.json()
        assert data["user_type"] == "admin"

    def test_register_user_with_supporter_type(self, client, db):
        user_data = {
            "email": "supporter@example.com",
            "password": "securepassword123",
            "first_name": "Support",
            "last_name": "User",
            "user_type": "supporter",
        }
        response = client.post("/auth/register", json=user_data)
        assert response.status_code == 201
        data = response.json()
        assert data["user_type"] == "supporter"

    def test_register_user_invalid_email_format(self, client, db):
        user_data = {
            "email": "invalid-email",
            "password": "securepassword123",
            "user_type": "customer",
        }
        response = client.post("/auth/register", json=user_data)
        assert response.status_code == 422

    def test_login_user_inactive_account(self, client, db):
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",
            "user_type": "customer",
        }
        register_response = client.post("/auth/register", json=user_data)
        assert register_response.status_code == 201
        # Deactivate the user in the database
        user = db.query(User).filter(User.email == user_data["email"]).first()
        assert user is not None, "User not found in database after registration"
        user.is_active = False
        db.commit()
        # Try to login
        login_data = {"email": "test@example.com", "password": "securepassword123"}
        login_response = client.post("/auth/login", json=login_data)
        assert login_response.status_code == 400
        assert "Inactive user account" in login_response.json()["detail"]

    def test_token_expiration(self, client, db):
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",
            "user_type": "customer",
        }
        register_response = client.post("/auth/register", json=user_data)
        assert register_response.status_code == 201
        login_data = {"email": "test@example.com", "password": "securepassword123"}
        login_response = client.post("/auth/login", json=login_data)
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        expired_payload = {
            "sub": user_data["email"],
            "exp": datetime.utcnow() - timedelta(minutes=1),
        }
        expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
        headers = {"Authorization": f"Bearer {expired_token}"}
        me_response = client.get("/auth/me", headers=headers)
        assert me_response.status_code == 401
        assert "Could not validate credentials" in me_response.json()["detail"]


class TestAuthUtilities:
    def test_password_hashing(self):
        from api.auth import get_password_hash, verify_password

        password = "testpassword123"
        hashed = get_password_hash(password)
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("wrongpassword", hashed) is False

    def test_token_creation_and_verification(self):
        from api.auth import create_access_token, verify_token

        email = "test@example.com"
        token = create_access_token(data={"sub": email})
        assert isinstance(token, str)
        token_data = verify_token(token)
        assert token_data is not None
        assert token_data.email == email
        invalid_token_data = verify_token("invalid_token")
        assert invalid_token_data is None
