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

class TestUserManagementEndpoints:
    """Test cases for user management endpoints"""
    
    def setup_method(self):
        """Setup method that runs before each test"""
        # Clear the database before each test
        db = TestingSessionLocal()
        db.query(User).delete()
        db.commit()
        db.close()
    
    def create_test_user(self, email="test@example.com", user_type="customer", is_admin=False):
        """Helper method to create a test user"""
        from api.auth import get_password_hash
        
        db = TestingSessionLocal()
        user = User(
            email=email,
            password_hash=get_password_hash("password123"),
            first_name="Test",
            last_name="User",
            user_type="admin" if is_admin else user_type,
            is_active=True,
            is_verified=False
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.close()
        return user
    
    def get_auth_token(self, email="test@example.com", password="password123"):
        """Helper method to get authentication token"""
        login_data = {"email": email, "password": password}
        response = client.post("/auth/login", json=login_data)
        if response.status_code == 200:
            return response.json()["access_token"]
        return None
    
    def test_update_user_status_activate(self):
        """Test activating a user account"""
        # Create admin user
        admin_user = self.create_test_user("admin@example.com", is_admin=True)
        admin_token = self.get_auth_token("admin@example.com")
        
        # Create regular user
        regular_user = self.create_test_user("user@example.com")
        
        # Deactivate user first
        db = TestingSessionLocal()
        user = db.query(User).filter(User.email == "user@example.com").first()
        user.is_active = False
        db.commit()
        db.close()
        
        # Activate user
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.put(
            f"/users/{regular_user.id}/status",
            json={"is_active": True},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True
        assert data["id"] == regular_user.id
    
    def test_update_user_status_deactivate(self):
        """Test deactivating a user account"""
        # Create admin user
        admin_user = self.create_test_user("admin@example.com", is_admin=True)
        admin_token = self.get_auth_token("admin@example.com")
        
        # Create regular user
        regular_user = self.create_test_user("user@example.com")
        
        # Deactivate user
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.put(
            f"/users/{regular_user.id}/status",
            json={"is_active": False},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False
        assert data["id"] == regular_user.id
    
    def test_update_user_status_admin_cannot_deactivate_self(self):
        """Test that admin cannot deactivate their own account"""
        # Create admin user
        admin_user = self.create_test_user("admin@example.com", is_admin=True)
        admin_token = self.get_auth_token("admin@example.com")
        
        # Try to deactivate own account
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.put(
            f"/users/{admin_user.id}/status",
            json={"is_active": False},
            headers=headers
        )
        
        assert response.status_code == 400
        assert "Cannot deactivate your own account" in response.json()["detail"]
    
    def test_update_user_status_admin_cannot_deactivate_other_admin(self):
        """Test that admin cannot deactivate other admin accounts"""
        # Create two admin users
        admin1 = self.create_test_user("admin1@example.com", is_admin=True)
        admin2 = self.create_test_user("admin2@example.com", is_admin=True)
        admin1_token = self.get_auth_token("admin1@example.com")
        
        # Try to deactivate other admin
        headers = {"Authorization": f"Bearer {admin1_token}"}
        response = client.put(
            f"/users/{admin2.id}/status",
            json={"is_active": False},
            headers=headers
        )
        
        assert response.status_code == 400
        assert "Cannot deactivate admin accounts" in response.json()["detail"]
    
    def test_update_user_status_requires_admin(self):
        """Test that non-admin users cannot update user status"""
        # Create regular user
        regular_user = self.create_test_user("user@example.com")
        user_token = self.get_auth_token("user@example.com")
        
        # Try to update status
        headers = {"Authorization": f"Bearer {user_token}"}
        response = client.put(
            f"/users/{regular_user.id}/status",
            json={"is_active": False},
            headers=headers
        )
        
        assert response.status_code == 403
        assert "Admin access required" in response.json()["detail"]
    
    def test_update_user_information(self):
        """Test updating user information"""
        # Create admin user
        admin_user = self.create_test_user("admin@example.com", is_admin=True)
        admin_token = self.get_auth_token("admin@example.com")
        
        # Create regular user
        regular_user = self.create_test_user("user@example.com")
        
        # Update user information
        headers = {"Authorization": f"Bearer {admin_token}"}
        update_data = {
            "first_name": "Updated",
            "last_name": "Name",
            "user_type": "supporter",
            "is_verified": True
        }
        response = client.put(
            f"/users/{regular_user.id}",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
        assert data["last_name"] == "Name"
        assert data["user_type"] == "supporter"
        assert data["is_verified"] is True
    
    def test_update_user_email_duplicate(self):
        """Test updating user email to already existing email"""
        # Create admin user
        admin_user = self.create_test_user("admin@example.com", is_admin=True)
        admin_token = self.get_auth_token("admin@example.com")
        
        # Create two regular users
        user1 = self.create_test_user("user1@example.com")
        user2 = self.create_test_user("user2@example.com")
        
        # Try to update user1's email to user2's email
        headers = {"Authorization": f"Bearer {admin_token}"}
        update_data = {"email": "user2@example.com"}
        response = client.put(
            f"/users/{user1.id}",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]
    
    def test_update_user_invalid_user_type(self):
        """Test updating user with invalid user type"""
        # Create admin user
        admin_user = self.create_test_user("admin@example.com", is_admin=True)
        admin_token = self.get_auth_token("admin@example.com")
        
        # Create regular user
        regular_user = self.create_test_user("user@example.com")
        
        # Try to update with invalid user type
        headers = {"Authorization": f"Bearer {admin_token}"}
        update_data = {"user_type": "invalid_type"}
        response = client.put(
            f"/users/{regular_user.id}",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 400
        assert "Invalid user type" in response.json()["detail"]
    
    def test_update_user_password_success(self):
        """Test updating user password successfully"""
        # Create user
        user = self.create_test_user("user@example.com")
        user_token = self.get_auth_token("user@example.com")
        
        # Update password
        headers = {"Authorization": f"Bearer {user_token}"}
        password_data = {
            "current_password": "password123",
            "new_password": "newpassword123"
        }
        response = client.put(
            f"/users/{user.id}/password",
            json=password_data,
            headers=headers
        )
        
        assert response.status_code == 200
        assert "Password updated successfully" in response.json()["message"]
    
    def test_update_user_password_wrong_current_password(self):
        """Test updating password with wrong current password"""
        # Create user
        user = self.create_test_user("user@example.com")
        user_token = self.get_auth_token("user@example.com")
        
        # Try to update with wrong current password
        headers = {"Authorization": f"Bearer {user_token}"}
        password_data = {
            "current_password": "wrongpassword",
            "new_password": "newpassword123"
        }
        response = client.put(
            f"/users/{user.id}/password",
            json=password_data,
            headers=headers
        )
        
        assert response.status_code == 400
        assert "Current password is incorrect" in response.json()["detail"]
    
    def test_delete_user_success(self):
        """Test deleting a user successfully"""
        # Create admin user
        admin_user = self.create_test_user("admin@example.com", is_admin=True)
        admin_token = self.get_auth_token("admin@example.com")
        
        # Create regular user
        regular_user = self.create_test_user("user@example.com")
        
        # Delete user
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.delete(f"/users/{regular_user.id}", headers=headers)
        
        assert response.status_code == 200
        assert "User deleted successfully" in response.json()["message"]
    
    def test_delete_user_admin_cannot_delete_self(self):
        """Test that admin cannot delete their own account"""
        # Create admin user
        admin_user = self.create_test_user("admin@example.com", is_admin=True)
        admin_token = self.get_auth_token("admin@example.com")
        
        # Try to delete own account
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.delete(f"/users/{admin_user.id}", headers=headers)
        
        assert response.status_code == 400
        assert "Cannot delete your own account" in response.json()["detail"]
    
    def test_delete_user_cannot_delete_admin(self):
        """Test that admin accounts cannot be deleted"""
        # Create two admin users
        admin1 = self.create_test_user("admin1@example.com", is_admin=True)
        admin2 = self.create_test_user("admin2@example.com", is_admin=True)
        admin1_token = self.get_auth_token("admin1@example.com")
        
        # Try to delete other admin
        headers = {"Authorization": f"Bearer {admin1_token}"}
        response = client.delete(f"/users/{admin2.id}", headers=headers)
        
        assert response.status_code == 400
        assert "Cannot delete admin accounts" in response.json()["detail"]
    
    def test_get_all_users_pagination(self):
        """Test getting all users with pagination"""
        # Create admin user
        admin_user = self.create_test_user("admin@example.com", is_admin=True)
        admin_token = self.get_auth_token("admin@example.com")
        
        # Create multiple users
        for i in range(15):
            self.create_test_user(f"user{i}@example.com")
        
        # Get first page
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/users/?page=1&per_page=10", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["users"]) == 10
        assert data["total"] == 16  # 15 users + 1 admin
        assert data["page"] == 1
        assert data["per_page"] == 10
        assert data["has_next"] is True
        assert data["has_prev"] is False
    
    def test_get_all_users_search(self):
        """Test searching users"""
        # Create admin user
        admin_user = self.create_test_user("admin@example.com", is_admin=True)
        admin_token = self.get_auth_token("admin@example.com")
        
        # Create users with specific names
        self.create_test_user("john@example.com")
        self.create_test_user("jane@example.com")
        self.create_test_user("bob@example.com")
        
        # Search for "john"
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/users/?search=john", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["users"]) == 1
        assert data["users"][0]["email"] == "john@example.com"
    
    def test_get_all_users_filter_by_type(self):
        """Test filtering users by type"""
        # Create admin user
        admin_user = self.create_test_user("admin@example.com", is_admin=True)
        admin_token = self.get_auth_token("admin@example.com")
        
        # Create users with different types
        self.create_test_user("customer1@example.com", "customer")
        self.create_test_user("supporter1@example.com", "supporter")
        self.create_test_user("customer2@example.com", "customer")
        
        # Filter by customer type
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/users/?user_type=customer", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["users"]) == 2
        for user in data["users"]:
            assert user["user_type"] == "customer"
    
    def test_get_user_detail_success(self):
        """Test getting user detail successfully"""
        # Create user
        user = self.create_test_user("user@example.com")
        user_token = self.get_auth_token("user@example.com")
        
        # Get user detail
        headers = {"Authorization": f"Bearer {user_token}"}
        response = client.get(f"/users/{user.id}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user.id
        assert data["email"] == "user@example.com"
        assert "chat_count" in data
    
    def test_get_user_detail_unauthorized(self):
        """Test getting user detail without authorization"""
        # Create user
        user = self.create_test_user("user@example.com")
        
        # Try to get user detail without token
        response = client.get(f"/users/{user.id}")
        
        assert response.status_code == 403
        assert "Not authenticated" in response.json()["detail"]
    
    def test_get_user_detail_wrong_user(self):
        """Test that users can only view their own details"""
        # Create two users
        user1 = self.create_test_user("user1@example.com")
        user2 = self.create_test_user("user2@example.com")
        user1_token = self.get_auth_token("user1@example.com")
        
        # User1 tries to get User2's details
        headers = {"Authorization": f"Bearer {user1_token}"}
        response = client.get(f"/users/{user2.id}", headers=headers)
        
        assert response.status_code == 403
        assert "Can only view your own user details" in response.json()["detail"]
    
    def test_find_user_by_email_success(self):
        """Test finding user by email successfully"""
        # Create admin user
        admin_user = self.create_test_user("admin@example.com", is_admin=True)
        admin_token = self.get_auth_token("admin@example.com")
        
        # Create regular user
        regular_user = self.create_test_user("user@example.com")
        
        # Find user by email
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/users/search/user@example.com", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user@example.com"
        assert data["id"] == regular_user.id
    
    def test_find_user_by_email_not_found(self):
        """Test finding user by non-existent email"""
        # Create admin user
        admin_user = self.create_test_user("admin@example.com", is_admin=True)
        admin_token = self.get_auth_token("admin@example.com")
        
        # Try to find non-existent user
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/users/search/nonexistent@example.com", headers=headers)
        
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]
    
    def test_get_my_profile_success(self):
        """Test getting current user's profile"""
        # Create user
        user = self.create_test_user("user@example.com")
        user_token = self.get_auth_token("user@example.com")
        
        # Get profile
        headers = {"Authorization": f"Bearer {user_token}"}
        response = client.get("/users/me/profile", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user@example.com"
        assert data["id"] == user.id
        assert "chat_count" in data
    
    def test_update_my_profile_success(self):
        """Test updating current user's profile"""
        # Create user
        user = self.create_test_user("user@example.com")
        user_token = self.get_auth_token("user@example.com")
        
        # Update profile
        headers = {"Authorization": f"Bearer {user_token}"}
        update_data = {
            "first_name": "Updated",
            "last_name": "Name"
        }
        response = client.put("/users/me/profile", json=update_data, headers=headers)
        
        assert response.status_code == 200
        assert "Profile updated successfully" in response.json()["message"]
    
    def test_update_my_profile_cannot_change_user_type(self):
        """Test that users cannot change their own user type"""
        # Create user
        user = self.create_test_user("user@example.com")
        user_token = self.get_auth_token("user@example.com")
        
        # Try to change user type
        headers = {"Authorization": f"Bearer {user_token}"}
        update_data = {"user_type": "admin"}
        response = client.put("/users/me/profile", json=update_data, headers=headers)
        
        assert response.status_code == 400
        assert "Cannot change user type" in response.json()["detail"]
    
    def test_update_my_profile_cannot_change_verification(self):
        """Test that users cannot change their own verification status"""
        # Create user
        user = self.create_test_user("user@example.com")
        user_token = self.get_auth_token("user@example.com")
        
        # Try to change verification status
        headers = {"Authorization": f"Bearer {user_token}"}
        update_data = {"is_verified": True}
        response = client.put("/users/me/profile", json=update_data, headers=headers)
        
        assert response.status_code == 400
        assert "Cannot change verification status" in response.json()["detail"] 