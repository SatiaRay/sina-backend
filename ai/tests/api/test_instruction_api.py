# tests/test_instructions_api.py - Updated tests
import pytest
from fastapi import status
from datetime import datetime, timezone
from src.database.models import Instruction


class TestInstructionAPI:
    """Test instruction API endpoints with workspace isolation"""
    
    def test_create_instruction_success(self, client, db, mock_token_info):
        """Test creating an instruction in current workspace"""
        instruction_data = {
            "label": "Test Instruction",
            "text": "This is a test instruction",
            "status": True
        }
        
        response = client.post("/instructions/", json=instruction_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["label"] == instruction_data["label"]
        assert data["text"] == instruction_data["text"]
        assert data["status"] == instruction_data["status"]
        assert data["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"
        assert data["created_by"] == mock_token_info["sub"]  # Check created_by is set
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        
        # Verify in database
        db_instruction = db.query(Instruction).first()
        assert db_instruction is not None
        assert db_instruction.label == instruction_data["label"]
        assert db_instruction.workspace_id == "39354e1f-b9cc-30eb-9700-963b3a53e977"
        assert db_instruction.created_by == mock_token_info["sub"]
    
    def test_create_instruction_with_explicit_workspace_ignored(self, client, mock_token_info):
        """Test that explicit workspace_id in request is ignored"""
        instruction_data = {
            "label": "Test Instruction",
            "text": "Content",
            "status": True,
            "workspace_id": "some-other-workspace"  # Should be ignored
        }
        
        response = client.post("/instructions/", json=instruction_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Should be set to workspace from token, not the one in request
        assert data["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"
        assert data["workspace_id"] != "some-other-workspace"
        # created_by should be set from token
        assert data["created_by"] == mock_token_info["sub"]
    
    def test_get_instructions_paginated(self, client, create_test_instruction, mock_token_info):
        """Test getting paginated instructions from current workspace"""
        # Create test instructions
        for i in range(15):
            create_test_instruction(
                label=f"Test Instruction {i}",
                text=f"Content {i}",
                status=(i % 2 == 0)
            )
        
        # Test first page
        response = client.get("/instructions/", params={"page": 1, "size": 10})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert len(data["items"]) == 10
        assert data["total"] == 15
        assert data["page"] == 1
        assert data["size"] == 10
        assert data["pages"] == 2
        
        # All items should be from the current workspace
        for item in data["items"]:
            assert item["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"
            assert item["created_by"] == mock_token_info["sub"]
    
    def test_get_instructions_active_only(self, client, create_test_instruction, mock_token_info):
        """Test getting only active instructions"""
        # Create mixed status instructions
        create_test_instruction(label="Active 1", text="Content", status=True)
        create_test_instruction(label="Inactive 1", text="Content", status=False)
        create_test_instruction(label="Active 2", text="Content", status=True)
        
        # Get all instructions
        response = client.get("/instructions/")
        assert response.status_code == status.HTTP_200_OK
        all_data = response.json()
        assert all_data["total"] == 3
        
        # Get active only
        response = client.get("/instructions/", params={"active_only": True})
        assert response.status_code == status.HTTP_200_OK
        active_data = response.json()
        
        assert active_data["total"] == 2
        for item in active_data["items"]:
            assert item["status"] is True
            assert item["created_by"] == mock_token_info["sub"]
    
    def test_get_instruction_success(self, client, create_test_instruction, mock_token_info):
        """Test getting a specific instruction"""
        instruction = create_test_instruction()
        
        response = client.get(f"/instructions/{instruction.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == instruction.id
        assert data["label"] == instruction.label
        assert data["text"] == instruction.text
        assert data["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"
        assert data["created_by"] == mock_token_info["sub"]
    
    def test_get_instruction_not_found(self, client):
        """Test getting non-existent instruction"""
        response = client.get("/instructions/999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_get_instruction_wrong_workspace(self, client, create_test_instruction, db):
        """Test that instruction from another workspace is not accessible"""
        instruction = create_test_instruction()
        
        # Change instruction to another workspace
        instruction.workspace_id = "another-workspace-id"
        db.commit()
        
        # Try to access from current workspace (token workspace)
        response = client.get(f"/instructions/{instruction.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_instruction_success(self, client, create_test_instruction, mock_token_info):
        """Test updating an instruction"""
        instruction = create_test_instruction(label="Old Label", text="Old Text")
        
        update_data = {
            "label": "Updated Label",
            "text": "Updated Text"
        }
        
        response = client.put(f"/instructions/{instruction.id}", json=update_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["label"] == update_data["label"]
        assert data["text"] == update_data["text"]
        assert data["id"] == instruction.id
        assert data["created_by"] == mock_token_info["sub"]  # created_by should remain
    
    def test_update_instruction_partial(self, client, create_test_instruction, mock_token_info):
        """Test partial update of an instruction"""
        instruction = create_test_instruction(label="Old Label", text="Old Text")
        
        # Update only label
        update_data = {"label": "Updated Label Only"}
        
        response = client.put(f"/instructions/{instruction.id}", json=update_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["label"] == update_data["label"]
        assert data["text"] == "Old Text"  # Should remain unchanged
        assert data["created_by"] == mock_token_info["sub"]
    
    def test_update_instruction_not_found(self, client):
        """Test updating non-existent instruction"""
        update_data = {
            "label": "Updated Label",
            "text": "Updated Text"
        }
        
        response = client.put("/instructions/999", json=update_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_instruction_wrong_workspace(self, client, create_test_instruction, db):
        """Test cannot update instruction from another workspace"""
        instruction = create_test_instruction()
        
        # Change instruction to another workspace
        instruction.workspace_id = "another-workspace-id"
        db.commit()
        
        update_data = {"label": "Updated Label"}
        response = client.put(f"/instructions/{instruction.id}", json=update_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_instruction_success(self, client, create_test_instruction, db):
        """Test deleting an instruction"""
        instruction = create_test_instruction()
        instruction_id = instruction.id  # Store the ID before deletion
        
        response = client.delete(f"/instructions/{instruction_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["message"] == "Instruction deleted successfully"
        
        # Verify deleted from database - use the stored ID
        db_instruction = db.query(Instruction).filter(Instruction.id == instruction_id).first()
        assert db_instruction is None
    
    def test_delete_instruction_not_found(self, client):
        """Test deleting non-existent instruction"""
        response = client.delete("/instructions/999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_enable_instruction(self, client, create_test_instruction, db, mock_token_info):
        """Test enabling a disabled instruction"""
        instruction = create_test_instruction(status=False)
        
        response = client.patch(f"/instructions/{instruction.id}/enable")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] is True
        assert data["created_by"] == mock_token_info["sub"]
        
        # Verify in database
        db.refresh(instruction)
        assert instruction.status is True
    
    def test_disable_instruction(self, client, create_test_instruction, db, mock_token_info):
        """Test disabling an enabled instruction"""
        instruction = create_test_instruction(status=True)
        
        response = client.patch(f"/instructions/{instruction.id}/disable")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] is False
        assert data["created_by"] == mock_token_info["sub"]
        
        # Verify in database
        db.refresh(instruction)
        assert instruction.status is False


class TestInstructionValidation:
    """Test input validation for instruction endpoints"""
    
    def test_create_with_empty_fields(self, client):
        """Test creating instruction with empty fields"""
        # Empty label
        response = client.post("/instructions/", json={
            "label": "   ",
            "text": "Valid text",
            "status": True
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Empty text
        response = client.post("/instructions/", json={
            "label": "Valid label",
            "text": "   ",
            "status": True
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_create_with_long_label(self, client):
        """Test creating instruction with label exceeding max length"""
        long_label = "A" * 256  # Exceeds max_length=255
        
        response = client.post("/instructions/", json={
            "label": long_label,
            "text": "Valid text",
            "status": True
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_pagination_validation(self, client):
        """Test pagination parameter validation"""
        # Invalid page (less than 1)
        response = client.get("/instructions/", params={"page": 0})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Invalid size (less than 1)
        response = client.get("/instructions/", params={"size": 0})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Invalid size (greater than max)
        response = client.get("/instructions/", params={"size": 101})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestInstructionAuthentication:
    """Test authentication and authorization aspects"""
    
    def test_missing_authentication(self, unauth_client):
        """Test endpoints without authentication"""
        response = unauth_client.get("/instructions/")
        # Should return 401 or 403
        assert response.status_code in [401, 403]
    
    def test_token_without_workspace_scope(self, auth_client_no_workspace):
        """Test token without workspace scope"""
        response = auth_client_no_workspace.get("/instructions/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "No workspace access" in response.json()["detail"]


class TestInstructionWorkspaceIsolation:
    """Test workspace isolation features"""
    
    def test_instructions_isolated_by_workspace(self, client, create_test_instruction, db, mock_token_info):
        """Test that instructions are properly isolated by workspace"""
        # Create instructions in test workspace
        for i in range(5):
            create_test_instruction(label=f"Workspace 1 - Instruction {i}")
        
        # Create instruction in another workspace
        instruction_other = Instruction(
            label="Workspace 2 Instruction",
            text="Content",
            status=True,
            workspace_id="another-workspace-id",
            created_by=mock_token_info["sub"],  # Add created_by
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(instruction_other)
        db.commit()
        
        # Get instructions from test workspace
        response = client.get("/instructions/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Should only see instructions from workspace 1
        assert data["total"] == 5
        for item in data["items"]:
            assert item["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"
            assert item["created_by"] == mock_token_info["sub"]
    
    def test_cannot_access_other_workspace_instruction(self, client, db, mock_token_info):
        """Test that operations fail on instructions from other workspaces"""
        # Create instruction in another workspace
        instruction = Instruction(
            label="Other Workspace Instruction",
            text="Content",
            status=True,
            workspace_id="another-workspace-id",
            created_by=mock_token_info["sub"],  # Add created_by
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(instruction)
        db.commit()
        
        # Try to get it
        response = client.get(f"/instructions/{instruction.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        # Try to update it
        response = client.put(f"/instructions/{instruction.id}", json={"label": "Updated"})
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        # Try to delete it
        response = client.delete(f"/instructions/{instruction.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        # Try to enable/disable it
        response = client.patch(f"/instructions/{instruction.id}/enable")
        assert response.status_code == status.HTTP_404_NOT_FOUND