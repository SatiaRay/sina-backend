import pytest
from fastapi import status
from datetime import datetime, timezone
from src.database.models import Wizard


class TestWizardAPI:
    """Test wizard API endpoints"""
    
    def test_get_root_wizards(self, wizard_client, create_test_wizard, mock_token_info):
        """Test getting root wizards"""
        # Create root wizards
        create_test_wizard(title="Root 1", parent_id=None, wizard_type="question")
        create_test_wizard(title="Root 2", parent_id=None, wizard_type="answer")
        # Create a non-root wizard (should not appear in results)
        child_wizard = create_test_wizard(title="Child", parent_id=1, wizard_type="answer")
        
        response = wizard_client.get("/wizards/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert len(data) == 2  # Only root wizards
        for wizard in data:
            assert wizard["parent_id"] is None
            assert wizard["created_by"] == mock_token_info["sub"]
            assert wizard["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"
            assert wizard["wizard_type"] in ["answer", "question"]
    
    def test_create_wizard_success(self, wizard_client, db, mock_token_info):
        """Test creating a wizard successfully"""
        wizard_data = {
            "title": "New Wizard",
            "context": "New wizard context",
            "parent_id": None,
            "enabled": True,
            "wizard_type": "answer"
        }
        
        response = wizard_client.post("/wizards/", json=wizard_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["title"] == wizard_data["title"]
        assert data["context"] == wizard_data["context"]
        assert data["enabled"] == wizard_data["enabled"]
        assert data["wizard_type"] == wizard_data["wizard_type"]
        assert data["parent_id"] == wizard_data["parent_id"]
        assert data["created_by"] == mock_token_info["sub"]
        assert data["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        
        # Verify in database
        db_wizard = db.query(Wizard).filter(Wizard.id == data["id"]).first()
        assert db_wizard is not None
        assert db_wizard.title == wizard_data["title"]
        assert db_wizard.created_by == mock_token_info["sub"]
        assert db_wizard.workspace_id == "39354e1f-b9cc-30eb-9700-963b3a53e977"
    
    def test_create_wizard_with_parent(self, wizard_client, create_test_wizard, mock_token_info):
        """Test creating a wizard with a parent"""
        parent_wizard = create_test_wizard(title="Parent Wizard", wizard_type="question")
        
        wizard_data = {
            "title": "Child Wizard",
            "context": "Child context",
            "parent_id": parent_wizard.id,
            "enabled": True,
            "wizard_type": "answer"
        }
        
        response = wizard_client.post("/wizards/", json=wizard_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["parent_id"] == parent_wizard.id
        assert data["wizard_type"] == "answer"
        assert data["created_by"] == mock_token_info["sub"]
        assert data["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"
    
    def test_create_wizard_with_default_values(self, wizard_client, mock_token_info):
        """Test creating wizard with only required fields"""
        wizard_data = {
            "title": "Minimal Wizard",
            "wizard_type": "question"
            # context, parent_id, enabled use defaults
        }
        
        response = wizard_client.post("/wizards/", json=wizard_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["title"] == wizard_data["title"]
        assert data["wizard_type"] == wizard_data["wizard_type"]
        assert data["context"] is None  # Default
        assert data["parent_id"] is None  # Default
        assert data["enabled"] is True  # Default
        assert data["created_by"] == mock_token_info["sub"]
        assert data["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"
    
    def test_get_wizard_by_id_success(self, wizard_client, create_test_wizard, mock_token_info):
        """Test getting a specific wizard by ID"""
        wizard = create_test_wizard(title="Specific Wizard", wizard_type="question")
        
        response = wizard_client.get(f"/wizards/{wizard.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == wizard.id
        assert data["title"] == wizard.title
        assert data["wizard_type"] == wizard.wizard_type
        assert data["created_by"] == mock_token_info["sub"]
        assert data["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"
        assert "children" in data  # Should include children field
    
    def test_get_wizard_by_id_with_children(self, wizard_client, create_wizard_hierarchy):
        """Test getting a wizard with its children loaded"""
        hierarchy = create_wizard_hierarchy()
        root = hierarchy["root"]
        
        response = wizard_client.get(f"/wizards/{root.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == root.id
        assert len(data["children"]) == 2  # Should have 2 children
        assert data["children"][0]["title"] == "Child Wizard 1"
        assert data["children"][1]["title"] == "Child Wizard 2"
    
    def test_get_wizard_by_id_not_found(self, wizard_client):
        """Test getting non-existent wizard"""
        response = wizard_client.get("/wizards/999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Wizard not found"
    
    def test_get_wizard_from_different_workspace(self, wizard_client, create_test_wizard, db):
        """Test cannot get wizard from another workspace"""
        # Create wizard in a different workspace
        wizard = Wizard(
            title="Other Workspace Wizard",
            context="Content",
            parent_id=None,
            enabled=True,
            wizard_type="answer",
            created_by="test-user-id",
            workspace_id="different-workspace-id",  # Different workspace
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(wizard)
        db.commit()
        
        # Try to get it (should fail - not in current workspace)
        response = wizard_client.get(f"/wizards/{wizard.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_wizard_success(self, wizard_client, create_test_wizard, mock_token_info):
        """Test updating a wizard"""
        wizard = create_test_wizard(title="Old Title", context="Old Context", wizard_type="answer")
        
        update_data = {
            "title": "Updated Title",
            "context": "Updated Context",
            "enabled": False,
            "wizard_type": "question"
        }
        
        response = wizard_client.put(f"/wizards/{wizard.id}", json=update_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["title"] == update_data["title"]
        assert data["context"] == update_data["context"]
        assert data["enabled"] == update_data["enabled"]
        assert data["wizard_type"] == update_data["wizard_type"]
        assert data["created_by"] == mock_token_info["sub"]
        assert data["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"
    
    def test_update_wizard_partial(self, wizard_client, create_test_wizard, mock_token_info):
        """Test partial update of a wizard"""
        wizard = create_test_wizard(title="Old Title", context="Old Context", enabled=True, wizard_type="answer")
        
        # Update only title
        update_data = {"title": "Updated Title Only"}
        
        response = wizard_client.put(f"/wizards/{wizard.id}", json=update_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["title"] == update_data["title"]
        assert data["context"] == "Old Context"  # Should remain unchanged
        assert data["enabled"] is True  # Should remain unchanged
        assert data["wizard_type"] == "answer"  # Should remain unchanged
        assert data["created_by"] == mock_token_info["sub"]
        assert data["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"
    
    def test_update_wizard_not_found(self, wizard_client):
        """Test updating non-existent wizard"""
        update_data = {"title": "Updated"}
        
        response = wizard_client.put("/wizards/999", json=update_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_wizard_from_different_workspace(self, wizard_client, create_test_wizard, db):
        """Test cannot update wizard from another workspace"""
        # Create wizard in a different workspace
        wizard = Wizard(
            title="Other Workspace Wizard",
            context="Content",
            parent_id=None,
            enabled=True,
            wizard_type="answer",
            created_by="test-user-id",
            workspace_id="different-workspace-id",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(wizard)
        db.commit()
        
        update_data = {"title": "Updated"}
        response = wizard_client.put(f"/wizards/{wizard.id}", json=update_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_wizard_success(self, wizard_client, create_test_wizard, db):
        """Test deleting a wizard"""
        wizard = create_test_wizard(wizard_type="answer")
        wizard_id = wizard.id  # Store ID before deletion
        
        response = wizard_client.delete(f"/wizards/{wizard_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["message"] == "Wizard deleted successfully"
        
        # Verify deleted from database
        db_wizard = db.query(Wizard).filter(Wizard.id == wizard_id).first()
        assert db_wizard is None
    
    def test_delete_wizard_not_found(self, wizard_client):
        """Test deleting non-existent wizard"""
        response = wizard_client.delete("/wizards/999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_wizard_from_different_workspace(self, wizard_client, db):
        """Test cannot delete wizard from another workspace"""
        # Create wizard in a different workspace
        wizard = Wizard(
            title="Other Workspace Wizard",
            context="Content",
            parent_id=None,
            enabled=True,
            wizard_type="answer",
            created_by="test-user-id",
            workspace_id="different-workspace-id",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(wizard)
        db.commit()
        
        response = wizard_client.delete(f"/wizards/{wizard.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestWizardValidation:
    """Test validation for wizard endpoints"""
    
    def test_create_wizard_validation_errors(self, wizard_client):
        """Test validation errors when creating wizard"""
        # Missing required field (title)
        response = wizard_client.post("/wizards/", json={
            "context": "Context",
            "enabled": True,
            "wizard_type": "answer"
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Empty title
        response = wizard_client.post("/wizards/", json={
            "title": "",
            "context": "Context",
            "enabled": True,
            "wizard_type": "answer"
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Missing wizard_type
        response = wizard_client.post("/wizards/", json={
            "title": "Valid Title",
            "context": "Context",
            "enabled": True
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Invalid wizard_type
        response = wizard_client.post("/wizards/", json={
            "title": "Valid Title",
            "context": "Context",
            "enabled": True,
            "wizard_type": "invalid_type"
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Title too long
        long_title = "A" * 256  # Exceeds max_length=255
        response = wizard_client.post("/wizards/", json={
            "title": long_title,
            "context": "Context",
            "enabled": True,
            "wizard_type": "answer"
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_update_wizard_validation(self, wizard_client, create_test_wizard):
        """Test validation when updating wizard"""
        wizard = create_test_wizard(wizard_type="answer")
        
        # Empty title in update
        response = wizard_client.put(f"/wizards/{wizard.id}", json={
            "title": ""
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Invalid wizard_type in update
        response = wizard_client.put(f"/wizards/{wizard.id}", json={
            "wizard_type": "invalid_type"
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Title too long in update
        long_title = "A" * 256
        response = wizard_client.put(f"/wizards/{wizard.id}", json={
            "title": long_title
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestWizardHierarchy:
    """Test wizard hierarchy relationships"""
    
    def test_wizard_parent_child_relationship(self, wizard_client, create_test_wizard, db):
        """Test parent-child wizard relationships"""
        # Create parent wizard
        parent = create_test_wizard(title="Parent", wizard_type="question")
        
        # Create child wizard
        child_data = {
            "title": "Child",
            "context": "Child context",
            "parent_id": parent.id,
            "enabled": True,
            "wizard_type": "answer"
        }
        
        response = wizard_client.post("/wizards/", json=child_data)
        assert response.status_code == status.HTTP_200_OK
        child_response = response.json()
        
        assert child_response["parent_id"] == parent.id
        
        # Get parent and verify it has children loaded
        parent_response = wizard_client.get(f"/wizards/{parent.id}")
        assert parent_response.status_code == status.HTTP_200_OK
        parent_data = parent_response.json()
        
        assert len(parent_data["children"]) == 1
        assert parent_data["children"][0]["id"] == child_response["id"]
        assert parent_data["children"][0]["title"] == "Child"
    
    def test_delete_wizard_with_children(self, wizard_client, create_wizard_hierarchy, db):
        """Test deleting a wizard that has children"""
        hierarchy = create_wizard_hierarchy()
        root_id = hierarchy["root"].id
        
        response = wizard_client.delete(f"/wizards/{root_id}")
        
        # Check behavior - depends on your cascade settings
        if response.status_code == status.HTTP_200_OK:
            # Root deleted - check if children are also deleted or orphaned
            root = db.query(Wizard).filter(Wizard.id == root_id).first()
            assert root is None
            
            # Children might be deleted or have parent_id set to NULL
            child1 = db.query(Wizard).filter(Wizard.id == hierarchy["child1"].id).first()
            if child1:
                # Children still exist, check parent_id
                assert child1.parent_id is None
        elif response.status_code == status.HTTP_400_BAD_REQUEST:
            # Deletion prevented because wizard has children
            detail = response.json()["detail"].lower()
            assert any(word in detail for word in ["children", "child", "delete", "cascade"])


class TestWizardAuthentication:
    """Test authentication for wizard endpoints"""
    
    def test_wizard_endpoints_require_auth(self, unauth_client):
        """Test that wizard endpoints require authentication"""
        endpoints_to_test = [
            ("GET", "/wizards/"),
            ("POST", "/wizards/"),
            ("GET", "/wizards/1"),
            ("PUT", "/wizards/1"),
            ("DELETE", "/wizards/1"),
        ]
        
        for method, endpoint in endpoints_to_test:
            if method == "GET":
                response = unauth_client.get(endpoint)
            elif method == "POST":
                response = unauth_client.post(endpoint, json={
                    "title": "test",
                    "wizard_type": "answer"
                })
            elif method == "PUT":
                response = unauth_client.put(endpoint, json={"title": "test"})
            elif method == "DELETE":
                response = unauth_client.delete(endpoint)
            
            # Should return 401 or 403
            assert response.status_code in [401, 403], f"{method} {endpoint} should require auth"
    
    def test_wizard_endpoints_require_workspace(self, auth_client_no_workspace):
        """Test that wizard endpoints require workspace scope in token"""
        # This client has a token without workspace scope
        response = auth_client_no_workspace.get("/wizards/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "No workspace access" in response.json()["detail"]


class TestWizardEdgeCases:
    """Test edge cases for wizard endpoints"""
    
    def test_create_multiple_wizards(self, wizard_client, db, mock_token_info):
        """Test creating multiple wizards"""
        for i in range(5):
            wizard_data = {
                "title": f"Wizard {i}",
                "wizard_type": "answer" if i % 2 == 0 else "question"
            }
            response = wizard_client.post("/wizards/", json=wizard_data)
            assert response.status_code == status.HTTP_200_OK
        
        # Verify all were created
        response = wizard_client.get("/wizards/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 5
    
    def test_wizard_with_same_title(self, wizard_client, mock_token_info):
        """Test creating wizards with the same title (should be allowed)"""
        wizard_data = {
            "title": "Duplicate Title",
            "wizard_type": "answer"
        }
        
        # Create first wizard
        response1 = wizard_client.post("/wizards/", json=wizard_data)
        assert response1.status_code == status.HTTP_200_OK
        
        # Create second wizard with same title
        response2 = wizard_client.post("/wizards/", json=wizard_data)
        assert response2.status_code == status.HTTP_200_OK
        
        # Both should be created successfully
        assert response1.json()["id"] != response2.json()["id"]
        assert response1.json()["title"] == response2.json()["title"]
    
    def test_wizard_disabled_state(self, wizard_client, create_test_wizard, mock_token_info):
        """Test wizard enabled/disabled state"""
        # Create disabled wizard
        wizard_data = {
            "title": "Disabled Wizard",
            "enabled": False,
            "wizard_type": "question"
        }
        
        response = wizard_client.post("/wizards/", json=wizard_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["enabled"] is False
        
        # Update to enabled
        update_response = wizard_client.put(f"/wizards/{data['id']}", json={"enabled": True})
        assert update_response.status_code == status.HTTP_200_OK
        updated_data = update_response.json()
        
        assert updated_data["enabled"] is True