import pytest
from database.models import User
from api.auth import SECRET_KEY, ALGORITHM
from datetime import datetime, timedelta


@pytest.fixture(scope="function")
def create_test_user(db):
    def _create_test_user(
        email="test@example.com", user_type="customer", is_admin=False
    ):
        from api.auth import get_password_hash

        user = User(
            email=email,
            password_hash=get_password_hash("password123"),
            first_name="Test",
            last_name="User",
            user_type="admin" if is_admin else user_type,
            is_active=True,
            is_verified=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _create_test_user


@pytest.fixture(scope="function")
def get_auth_token(client):
    def _get_auth_token(email="test@example.com", password="password123"):
        login_data = {"email": email, "password": password}
        response = client.post("/auth/login", json=login_data)
        if response.status_code == 200:
            return response.json()["access_token"]
        return None

    return _get_auth_token


class TestUserManagementEndpoints:
    def test_update_user_status_activate(
        self, client, db, create_test_user, get_auth_token
    ):
        admin_user = create_test_user("admin@example.com", is_admin=True)
        admin_token = get_auth_token("admin@example.com")
        regular_user = create_test_user("user@example.com")
        # Deactivate user first
        user = db.query(User).filter(User.email == "user@example.com").first()
        user.is_active = False
        db.commit()
        # Activate user
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.put(
            f"/users/{regular_user.id}/status",
            json={"is_active": True},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True
        assert data["id"] == regular_user.id

    def test_update_user_status_deactivate(
        self, client, db, create_test_user, get_auth_token
    ):
        admin_user = create_test_user("admin@example.com", is_admin=True)
        admin_token = get_auth_token("admin@example.com")
        regular_user = create_test_user("user@example.com")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.put(
            f"/users/{regular_user.id}/status",
            json={"is_active": False},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False
        assert data["id"] == regular_user.id

    def test_update_user_status_admin_cannot_deactivate_self(
        self, client, db, create_test_user, get_auth_token
    ):
        admin_user = create_test_user("admin@example.com", is_admin=True)
        admin_token = get_auth_token("admin@example.com")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.put(
            f"/users/{admin_user.id}/status", json={"is_active": False}, headers=headers
        )
        assert response.status_code == 400
        assert "Cannot deactivate your own account" in response.json()["detail"]

    def test_update_user_status_admin_cannot_deactivate_other_admin(
        self, client, db, create_test_user, get_auth_token
    ):
        admin1 = create_test_user("admin1@example.com", is_admin=True)
        admin2 = create_test_user("admin2@example.com", is_admin=True)
        admin1_token = get_auth_token("admin1@example.com")
        headers = {"Authorization": f"Bearer {admin1_token}"}
        response = client.put(
            f"/users/{admin2.id}/status", json={"is_active": False}, headers=headers
        )
        assert response.status_code == 400
        assert "Cannot deactivate admin accounts" in response.json()["detail"]

    def test_update_user_status_requires_admin(
        self, client, db, create_test_user, get_auth_token
    ):
        regular_user = create_test_user("user@example.com")
        user_token = get_auth_token("user@example.com")
        headers = {"Authorization": f"Bearer {user_token}"}
        response = client.put(
            f"/users/{regular_user.id}/status",
            json={"is_active": False},
            headers=headers,
        )
        assert response.status_code == 403
        assert "Admin access required" in response.json()["detail"]

    def test_update_user_information(
        self, client, db, create_test_user, get_auth_token
    ):
        admin_user = create_test_user("admin@example.com", is_admin=True)
        admin_token = get_auth_token("admin@example.com")
        regular_user = create_test_user("user@example.com")
        headers = {"Authorization": f"Bearer {admin_token}"}
        update_data = {
            "first_name": "Updated",
            "last_name": "Name",
            "user_type": "supporter",
            "is_verified": True,
        }
        response = client.put(
            f"/users/{regular_user.id}", json=update_data, headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
        assert data["last_name"] == "Name"
        assert data["user_type"] == "supporter"
        assert data["is_verified"] is True

    def test_update_user_email_duplicate(
        self, client, db, create_test_user, get_auth_token
    ):
        admin_user = create_test_user("admin@example.com", is_admin=True)
        admin_token = get_auth_token("admin@example.com")
        user1 = create_test_user("user1@example.com")
        user2 = create_test_user("user2@example.com")
        headers = {"Authorization": f"Bearer {admin_token}"}
        update_data = {"email": "user2@example.com"}
        response = client.put(f"/users/{user1.id}", json=update_data, headers=headers)
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    def test_update_user_invalid_user_type(
        self, client, db, create_test_user, get_auth_token
    ):
        admin_user = create_test_user("admin@example.com", is_admin=True)
        admin_token = get_auth_token("admin@example.com")
        regular_user = create_test_user("user@example.com")
        headers = {"Authorization": f"Bearer {admin_token}"}
        update_data = {"user_type": "invalid_type"}
        response = client.put(
            f"/users/{regular_user.id}", json=update_data, headers=headers
        )
        assert response.status_code == 400
        assert "Invalid user type" in response.json()["detail"]

    def test_update_user_password_success(
        self, client, db, create_test_user, get_auth_token
    ):
        user = create_test_user("user@example.com")
        user_token = get_auth_token("user@example.com")
        headers = {"Authorization": f"Bearer {user_token}"}
        password_data = {
            "current_password": "password123",
            "new_password": "newpassword123",
        }
        response = client.put(
            f"/users/{user.id}/password", json=password_data, headers=headers
        )
        assert response.status_code == 200
        assert "Password updated successfully" in response.json()["message"]

    def test_update_user_password_wrong_current_password(
        self, client, db, create_test_user, get_auth_token
    ):
        user = create_test_user("user@example.com")
        user_token = get_auth_token("user@example.com")
        headers = {"Authorization": f"Bearer {user_token}"}
        password_data = {
            "current_password": "wrongpassword",
            "new_password": "newpassword123",
        }
        response = client.put(
            f"/users/{user.id}/password", json=password_data, headers=headers
        )
        assert response.status_code == 400
        assert "Current password is incorrect" in response.json()["detail"]

    def test_delete_user_success(self, client, db, create_test_user, get_auth_token):
        admin_user = create_test_user("admin@example.com", is_admin=True)
        admin_token = get_auth_token("admin@example.com")
        regular_user = create_test_user("user@example.com")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.delete(f"/users/{regular_user.id}", headers=headers)
        assert response.status_code == 200
        assert "User deleted successfully" in response.json()["message"]

    def test_delete_user_admin_cannot_delete_self(
        self, client, db, create_test_user, get_auth_token
    ):
        admin_user = create_test_user("admin@example.com", is_admin=True)
        admin_token = get_auth_token("admin@example.com")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.delete(f"/users/{admin_user.id}", headers=headers)
        assert response.status_code == 400
        assert "Cannot delete your own account" in response.json()["detail"]

    def test_delete_user_cannot_delete_admin(
        self, client, db, create_test_user, get_auth_token
    ):
        admin1 = create_test_user("admin1@example.com", is_admin=True)
        admin2 = create_test_user("admin2@example.com", is_admin=True)
        admin1_token = get_auth_token("admin1@example.com")
        headers = {"Authorization": f"Bearer {admin1_token}"}
        response = client.delete(f"/users/{admin2.id}", headers=headers)
        assert response.status_code == 400
        assert "Cannot delete admin accounts" in response.json()["detail"]

    def test_get_all_users_pagination(
        self, client, db, create_test_user, get_auth_token
    ):
        admin_user = create_test_user("admin@example.com", is_admin=True)
        admin_token = get_auth_token("admin@example.com")
        for i in range(15):
            create_test_user(f"user{i}@example.com")
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

    def test_get_all_users_search(self, client, db, create_test_user, get_auth_token):
        admin_user = create_test_user("admin@example.com", is_admin=True)
        admin_token = get_auth_token("admin@example.com")
        create_test_user("john@example.com")
        create_test_user("jane@example.com")
        create_test_user("bob@example.com")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/users/?search=john", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["users"]) == 1
        assert data["users"][0]["email"] == "john@example.com"

    def test_get_all_users_filter_by_type(
        self, client, db, create_test_user, get_auth_token
    ):
        admin_user = create_test_user("admin@example.com", is_admin=True)
        admin_token = get_auth_token("admin@example.com")
        create_test_user("customer1@example.com", "customer")
        create_test_user("supporter1@example.com", "supporter")
        create_test_user("customer2@example.com", "customer")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/users/?user_type=customer", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["users"]) == 2
        for user in data["users"]:
            assert user["user_type"] == "customer"

    def test_get_user_detail_success(
        self, client, db, create_test_user, get_auth_token
    ):
        user = create_test_user("user@example.com")
        user_token = get_auth_token("user@example.com")
        headers = {"Authorization": f"Bearer {user_token}"}
        response = client.get(f"/users/{user.id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user.id
        assert data["email"] == "user@example.com"
        assert "chat_count" in data

    def test_get_user_detail_unauthorized(self, client, db, create_test_user):
        user = create_test_user("user@example.com")
        response = client.get(f"/users/{user.id}")
        assert response.status_code == 403
        assert "Not authenticated" in response.json()["detail"]

    def test_get_user_detail_wrong_user(
        self, client, db, create_test_user, get_auth_token
    ):
        user1 = create_test_user("user1@example.com")
        user2 = create_test_user("user2@example.com")
        user1_token = get_auth_token("user1@example.com")
        headers = {"Authorization": f"Bearer {user1_token}"}
        response = client.get(f"/users/{user2.id}", headers=headers)
        assert response.status_code == 403
        assert "Can only view your own user details" in response.json()["detail"]

    def test_find_user_by_email_success(
        self, client, db, create_test_user, get_auth_token
    ):
        admin_user = create_test_user("admin@example.com", is_admin=True)
        admin_token = get_auth_token("admin@example.com")
        regular_user = create_test_user("user@example.com")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/users/search/user@example.com", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user@example.com"
        assert data["id"] == regular_user.id

    def test_find_user_by_email_not_found(
        self, client, db, create_test_user, get_auth_token
    ):
        admin_user = create_test_user("admin@example.com", is_admin=True)
        admin_token = get_auth_token("admin@example.com")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/users/search/nonexistent@example.com", headers=headers)
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    def test_get_my_profile_success(self, client, db, create_test_user, get_auth_token):
        user = create_test_user("user@example.com")
        user_token = get_auth_token("user@example.com")
        headers = {"Authorization": f"Bearer {user_token}"}
        response = client.get("/users/me/profile", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user@example.com"
        assert data["id"] == user.id
        assert "chat_count" in data

    def test_update_my_profile_success(
        self, client, db, create_test_user, get_auth_token
    ):
        user = create_test_user("user@example.com")
        user_token = get_auth_token("user@example.com")
        headers = {"Authorization": f"Bearer {user_token}"}
        update_data = {"first_name": "Updated", "last_name": "Name"}
        response = client.put("/users/me/profile", json=update_data, headers=headers)
        assert response.status_code == 200
        assert "Profile updated successfully" in response.json()["message"]

    def test_update_my_profile_cannot_change_user_type(
        self, client, db, create_test_user, get_auth_token
    ):
        user = create_test_user("user@example.com")
        user_token = get_auth_token("user@example.com")
        headers = {"Authorization": f"Bearer {user_token}"}
        update_data = {"user_type": "admin"}
        response = client.put("/users/me/profile", json=update_data, headers=headers)
        assert response.status_code == 400
        assert "Cannot change user type" in response.json()["detail"]

    def test_update_my_profile_cannot_change_verification(
        self, client, db, create_test_user, get_auth_token
    ):
        user = create_test_user("user@example.com")
        user_token = get_auth_token("user@example.com")
        headers = {"Authorization": f"Bearer {user_token}"}
        update_data = {"is_verified": True}
        response = client.put("/users/me/profile", json=update_data, headers=headers)
        assert response.status_code == 400
        assert "Cannot change verification status" in response.json()["detail"]
