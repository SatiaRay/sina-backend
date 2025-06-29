import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch
import jwt
from datetime import datetime, timedelta

# Import your app and models
import sys
import os
from pathlib import Path

# Add the project root to the path
root_dir = Path(__file__).parent.parent.parent
sys.path.append(str(root_dir))

from api.main import app
from database.models import Base, User, get_db
from api.auth import SECRET_KEY, ALGORITHM

# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

def override_get_db():
    """Override the database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Override the database dependency
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

class TestAuthEndpoints:
    """Test cases for authentication endpoints"""
    
    def setup_method(self):
        """Setup method that runs before each test"""
        # Clear the database before each test
        db = TestingSessionLocal()
        db.query(User).delete()
        db.commit()
        db.close()
    
    def test_register_user_success(self):
        """Test successful user registration"""
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",
            "first_name": "John",
            "last_name": "Doe",
            "user_type": "customer"
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
        assert "password_hash" not in data  # Password should not be returned
    
    def test_register_user_duplicate_email(self):
        """Test registration with duplicate email"""
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",
            "user_type": "customer"
        }
        
        # Register first user
        response1 = client.post("/auth/register", json=user_data)
        assert response1.status_code == 201
        
        # Try to register with same email
        response2 = client.post("/auth/register", json=user_data)
        assert response2.status_code == 400
        assert "Email already registered" in response2.json()["detail"]
    
    def test_register_user_invalid_user_type(self):
        """Test registration with invalid user type"""
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",
            "user_type": "invalid_type"
        }
        
        response = client.post("/auth/register", json=user_data)
        
        assert response.status_code == 400
        assert "Invalid user type" in response.json()["detail"]
    
    def test_register_user_minimal_data(self):
        """Test registration with minimal required data"""
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123"
        }
        
        response = client.post("/auth/register", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["user_type"] == "customer"  # Default value
        assert data["first_name"] is None
        assert data["last_name"] is None
    
    def test_login_user_success(self):
        """Test successful user login"""
        # First register a user
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",
            "user_type": "customer"
        }
        register_response = client.post("/auth/register", json=user_data)
        assert register_response.status_code == 201
        
        # Then login
        login_data = {
            "email": "test@example.com",
            "password": "securepassword123"
        }
        login_response = client.post("/auth/login", json=login_data)
        
        assert login_response.status_code == 200
        data = login_response.json()
        
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == user_data["email"]
        
        # Verify the token is valid
        token = data["access_token"]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == user_data["email"]
    
    def test_login_user_invalid_credentials(self):
        """Test login with invalid credentials"""
        # First register a user
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",
            "user_type": "customer"
        }
        register_response = client.post("/auth/register", json=user_data)
        assert register_response.status_code == 201
        
        # Try to login with wrong password
        login_data = {
            "email": "test@example.com",
            "password": "wrongpassword"
        }
        login_response = client.post("/auth/login", json=login_data)
        
        assert login_response.status_code == 401
        assert "Incorrect email or password" in login_response.json()["detail"]
    
    def test_login_user_nonexistent_email(self):
        """Test login with non-existent email"""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "securepassword123"
        }
        login_response = client.post("/auth/login", json=login_data)
        
        assert login_response.status_code == 401
        assert "Incorrect email or password" in login_response.json()["detail"]
    
    def test_get_current_user_success(self):
        """Test getting current user info with valid token"""
        # First register and login a user
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",
            "user_type": "customer"
        }
        register_response = client.post("/auth/register", json=user_data)
        assert register_response.status_code == 201
        
        login_data = {
            "email": "test@example.com",
            "password": "securepassword123"
        }
        login_response = client.post("/auth/login", json=login_data)
        assert login_response.status_code == 200
        
        token = login_response.json()["access_token"]
        
        # Get current user info
        headers = {"Authorization": f"Bearer {token}"}
        me_response = client.get("/auth/me", headers=headers)
        
        assert me_response.status_code == 200
        data = me_response.json()
        assert data["email"] == user_data["email"]
        assert data["user_type"] == user_data["user_type"]
    
    def test_get_current_user_invalid_token(self):
        """Test getting current user info with invalid token"""
        headers = {"Authorization": "Bearer invalid_token"}
        me_response = client.get("/auth/me", headers=headers)
        
        assert me_response.status_code == 401
        assert "Could not validate credentials" in me_response.json()["detail"]
    
    def test_get_current_user_no_token(self):
        """Test getting current user info without token"""
        me_response = client.get("/auth/me")
        
        assert me_response.status_code == 403
        assert "Not authenticated" in me_response.json()["detail"]
    
    def test_logout_user(self):
        """Test logout endpoint"""
        response = client.post("/auth/logout")
        
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"
    
    def test_register_user_with_admin_type(self):
        """Test registration with admin user type"""
        user_data = {
            "email": "admin@example.com",
            "password": "securepassword123",
            "first_name": "Admin",
            "last_name": "User",
            "user_type": "admin"
        }
        
        response = client.post("/auth/register", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["user_type"] == "admin"
    
    def test_register_user_with_supporter_type(self):
        """Test registration with supporter user type"""
        user_data = {
            "email": "supporter@example.com",
            "password": "securepassword123",
            "first_name": "Support",
            "last_name": "User",
            "user_type": "supporter"
        }
        
        response = client.post("/auth/register", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["user_type"] == "supporter"
    
    def test_register_user_invalid_email_format(self):
        """Test registration with invalid email format"""
        user_data = {
            "email": "invalid-email",
            "password": "securepassword123",
            "user_type": "customer"
        }
        
        response = client.post("/auth/register", json=user_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_login_user_inactive_account(self):
        """Test login with inactive user account"""
        # First register a user
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",
            "user_type": "customer"
        }
        register_response = client.post("/auth/register", json=user_data)
        assert register_response.status_code == 201
        
        # Deactivate the user in the database
        db = TestingSessionLocal()
        user = db.query(User).filter(User.email == user_data["email"]).first()
        user.is_active = False
        db.commit()
        db.close()
        
        # Try to login
        login_data = {
            "email": "test@example.com",
            "password": "securepassword123"
        }
        login_response = client.post("/auth/login", json=login_data)
        
        assert login_response.status_code == 400
        assert "Inactive user account" in login_response.json()["detail"]
    
    def test_token_expiration(self):
        """Test that tokens expire correctly"""
        # First register and login a user
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",
            "user_type": "customer"
        }
        register_response = client.post("/auth/register", json=user_data)
        assert register_response.status_code == 201
        
        login_data = {
            "email": "test@example.com",
            "password": "securepassword123"
        }
        login_response = client.post("/auth/login", json=login_data)
        assert login_response.status_code == 200
        
        token = login_response.json()["access_token"]
        
        # Create an expired token
        expired_payload = {
            "sub": user_data["email"],
            "exp": datetime.utcnow() - timedelta(minutes=1)  # Expired 1 minute ago
        }
        expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
        
        # Try to use expired token
        headers = {"Authorization": f"Bearer {expired_token}"}
        me_response = client.get("/auth/me", headers=headers)
        
        assert me_response.status_code == 401
        assert "Could not validate credentials" in me_response.json()["detail"]

class TestAuthUtilities:
    """Test cases for authentication utility functions"""
    
    def test_password_hashing(self):
        """Test password hashing and verification"""
        from api.auth import get_password_hash, verify_password
        
        password = "testpassword123"
        hashed = get_password_hash(password)
        
        # Hash should be different from original password
        assert hashed != password
        
        # Should verify correctly
        assert verify_password(password, hashed) is True
        
        # Should not verify with wrong password
        assert verify_password("wrongpassword", hashed) is False
    
    def test_token_creation_and_verification(self):
        """Test JWT token creation and verification"""
        from api.auth import create_access_token, verify_token
        
        email = "test@example.com"
        token = create_access_token(data={"sub": email})
        
        # Token should be a string
        assert isinstance(token, str)
        
        # Should verify correctly
        token_data = verify_token(token)
        assert token_data is not None
        assert token_data.email == email
        
        # Should not verify with invalid token
        invalid_token_data = verify_token("invalid_token")
        assert invalid_token_data is None 