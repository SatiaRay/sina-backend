import pytest
from fastapi import status
from datetime import datetime, timezone
from io import BytesIO
import json

from src.database.models import Workflow


class TestWorkflowAPI:
    """Test workflow API endpoints with workspace isolation"""
    
    def test_create_workflow_success(self, workflow_client, db, mock_token_info):
        """Test creating a workflow successfully with workspace isolation"""
        workflow_data = {
            "name": "Test Workflow",
            "flow": [{"id": "1", "label": "Start", "type": "start", "position": None, "conditions": None, "next": None, "description": None, "ele": None}],
            "status": True
        }
        
        response = workflow_client.post("/workflows", json=workflow_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["name"] == workflow_data["name"]
        assert data["flow"] == workflow_data["flow"]
        assert data["status"] == workflow_data["status"]
        assert data["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"  # From token
        assert data["created_by"] == mock_token_info["sub"]
        assert "id" in data
        
        # Verify in database with workspace isolation
        db_workflow = db.query(Workflow).filter(Workflow.id == data["id"]).first()
        assert db_workflow is not None
        assert db_workflow.name == workflow_data["name"]
        assert db_workflow.workspace_id == "39354e1f-b9cc-30eb-9700-963b3a53e977"
        assert db_workflow.created_by == mock_token_info["sub"]
    
    def test_create_workflow_duplicate_name_same_workspace(self, workflow_client, create_test_workflow, mock_token_info):
        """Test cannot create workflow with duplicate name in same workspace"""
        workflow = create_test_workflow(name="Duplicate Workflow")
        
        workflow_data = {
            "name": "Duplicate Workflow",  # Same name
            "flow": [{"id": "1", "label": "Different", "type": "start"}],
            "status": True
        }
        
        response = workflow_client.post("/workflows", json=workflow_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in response.json()["detail"].lower()
    
    def test_create_workflow_same_name_different_workspace(self, workflow_client, db, mock_token_info):
        """Test can create workflow with same name in different workspace"""
        # Create workflow in workspace A
        workflow_in_a = Workflow(
            name="Same Name Workflow",
            flow=[{"id": "1", "label": "Test", "type": "start"}],
            status=True,
            created_by=mock_token_info["sub"],
            workspace_id="different-workspace-id",  # Different workspace
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(workflow_in_a)
        db.commit()
        
        # Try to create workflow with same name in workspace B (current workspace from token)
        workflow_data = {
            "name": "Same Name Workflow",  # Same name, different workspace
            "flow": [{"id": "2", "label": "Different", "type": "start"}],
            "status": False
        }
        
        response = workflow_client.post("/workflows", json=workflow_data)
        assert response.status_code == status.HTTP_200_OK  # Should succeed
        
        data = response.json()
        assert data["name"] == "Same Name Workflow"
        assert data["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"  # Current workspace
    
    def test_get_workflows(self, workflow_client, create_test_workflow):
        """Test getting all workflows in current workspace"""
        # Create workflows in current workspace
        create_test_workflow(name="Workflow 1")
        create_test_workflow(name="Workflow 2")
        
        # Create workflow in different workspace (should not appear)
        workflow_diff = Workflow(
            name="Other Workspace Workflow",
            flow=[{"id": "1", "label": "Test", "type": "start"}],
            status=True,
            created_by="test-user",
            workspace_id="different-workspace-id",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        workflow_client.app.state.db.add(workflow_diff)
        workflow_client.app.state.db.commit()
        
        response = workflow_client.get("/workflows")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert len(data) == 2  # Only workflows in current workspace
        for workflow in data:
            assert workflow["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"
            assert workflow["name"] in ["Workflow 1", "Workflow 2"]
    
    def test_get_workflows_pagination(self, workflow_client, create_test_workflow):
        """Test getting workflows with pagination"""
        # Create 5 workflows
        for i in range(5):
            create_test_workflow(name=f"Workflow {i}")
        
        # Test with skip and limit
        response = workflow_client.get("/workflows?skip=2&limit=2")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert len(data) == 2  # Limited to 2
        # Should get workflows 2 and 3 (0-based skip)
    
    def test_get_workflow_by_id_success(self, workflow_client, create_test_workflow, mock_token_info):
        """Test getting a specific workflow"""
        workflow = create_test_workflow(name="Specific Workflow")
        
        response = workflow_client.get(f"/workflows/{workflow.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == workflow.id
        assert data["name"] == workflow.name
        assert data["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"
        assert data["created_by"] == mock_token_info["sub"]
    
    def test_get_workflow_by_id_not_found(self, workflow_client):
        """Test getting non-existent workflow"""
        response = workflow_client.get("/workflows999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()
    
    def test_get_workflow_from_different_workspace(self, workflow_client, db):
        """Test cannot get workflow from another workspace"""
        # Create workflow in different workspace
        workflow = Workflow(
            name="Other Workspace Workflow",
            flow=[{"id": "1", "label": "Test", "type": "start"}],
            status=True,
            created_by="test-user",
            workspace_id="different-workspace-id",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(workflow)
        db.commit()
        
        response = workflow_client.get(f"/workflows/{workflow.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_workflow_success(self, workflow_client, create_test_workflow, mock_token_info):
        """Test updating a workflow"""
        workflow = create_test_workflow(name="Old Name")
        
        update_data = {
            "name": "Updated Name",
            "flow": [{"id": "1", "label": "Start", "type": "start", "position": None, "conditions": None, "next": None, "description": None, "ele": None}],
            "status": False
        }
        
        response = workflow_client.put(f"/workflows/{workflow.id}", json=update_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["name"] == update_data["name"]
        assert data["flow"] == update_data["flow"]
        assert data["status"] == update_data["status"]
        assert data["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"
        assert data["created_by"] == mock_token_info["sub"]
    
    def test_update_workflow_duplicate_name(self, workflow_client, create_test_workflow):
        """Test cannot update workflow to duplicate name in same workspace"""
        workflow1 = create_test_workflow(name="Workflow One")
        workflow2 = create_test_workflow(name="Workflow Two")
        
        # Try to update workflow2 to have same name as workflow1
        update_data = {
            "name": "Workflow One",  # Duplicate name
            "flow": workflow2.flow,
            "status": workflow2.status
        }
        
        response = workflow_client.put(f"/workflows/{workflow2.id}", json=update_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in response.json()["detail"].lower()
    
    def test_update_workflow_not_found(self, workflow_client):
        """Test updating non-existent workflow"""
        update_data = {
            "name": "Updated",
            "flow": [{"id": "1", "label": "Test", "type": "start"}],
            "status": True
        }
        
        response = workflow_client.put("/workflows999", json=update_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_workflow_from_different_workspace(self, workflow_client, db):
        """Test cannot update workflow from another workspace"""
        # Create workflow in different workspace
        workflow = Workflow(
            name="Other Workspace Workflow",
            flow=[{"id": "1", "label": "Test", "type": "start"}],
            status=True,
            created_by="test-user",
            workspace_id="different-workspace-id",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(workflow)
        db.commit()
        
        update_data = {
            "name": "Updated Name",
            "flow": [{"id": "2", "label": "Updated", "type": "end"}],
            "status": False
        }
        
        response = workflow_client.put(f"/workflows/{workflow.id}", json=update_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_workflow_success(self, workflow_client, create_test_workflow, db):
        """Test deleting a workflow"""
        workflow = create_test_workflow()
        workflow_id = workflow.id
        
        response = workflow_client.delete(f"/workflows/{workflow_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["message"] == "Workflow deleted successfully"
        
        # Verify deleted from database
        db_workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
        assert db_workflow is None
    
    def test_delete_workflow_not_found(self, workflow_client):
        """Test deleting non-existent workflow"""
        response = workflow_client.delete("/workflows999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_workflow_from_different_workspace(self, workflow_client, db):
        """Test cannot delete workflow from another workspace"""
        # Create workflow in different workspace
        workflow = Workflow(
            name="Other Workspace Workflow",
            flow=[{"id": "1", "label": "Test", "type": "start"}],
            status=True,
            created_by="test-user",
            workspace_id="different-workspace-id",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(workflow)
        db.commit()
        
        response = workflow_client.delete(f"/workflows/{workflow.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_export_workflow_success(self, workflow_client, create_test_workflow):
        """Test exporting a workflow"""
        workflow = create_test_workflow(
            name="Export Test Workflow",
            flow= [{"id": "1", "label": "Start", "type": "start", "position": None, "conditions": None, "next": None, "description": None, "ele": None}],
        )
        
        response = workflow_client.get(f"/workflows/{workflow.id}/export")
        assert response.status_code == status.HTTP_200_OK
        
        # Check headers
        assert "application/json" in response.headers["content-type"]
        assert "attachment" in response.headers["content-disposition"]
        assert "Export_Test_Workflow.json" in response.headers["content-disposition"]
        
        # Check content
        content = b"".join(response.iter_bytes())
        exported_data = json.loads(content.decode("utf-8"))
        
        assert exported_data["name"] == "Export Test Workflow"
        assert exported_data["flow"] == [{"id": "1", "label": "Start", "type": "start", "position": None, "conditions": None, "next": None, "description": None, "ele": None}]
        assert "id" not in exported_data  # Should not include ID
        assert "workspace_id" not in exported_data  # Should not include workspace
        assert "created_by" not in exported_data  # Should not include creator
    
    def test_export_workflow_not_found(self, workflow_client):
        """Test exporting non-existent workflow"""
        response = workflow_client.get("/workflows999/export")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_export_workflow_from_different_workspace(self, workflow_client, db):
        """Test cannot export workflow from another workspace"""
        workflow = Workflow(
            name="Other Workspace Export",
            flow=[{"id": "1", "label": "Test", "type": "start"}],
            status=True,
            created_by="test-user",
            workspace_id="different-workspace-id",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(workflow)
        db.commit()
        
        response = workflow_client.get(f"/workflows/{workflow.id}/export")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_import_workflow_success(self, workflow_client, mock_token_info):
        """Test importing a workflow"""
        workflow_data = {
            "name": "Imported Workflow",
            "flow": [{"id": "1", "label": "Start", "type": "start", "position": None, "conditions": None, "next": None, "description": None, "ele": None}],
            "status": True
        }
        
        # Create JSON file
        json_data = json.dumps(workflow_data)
        file_data = BytesIO(json_data.encode("utf-8"))
        
        response = workflow_client.post(
            "/workflows/import",
            files={"file": ("workflow.json", file_data, "application/json")}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["name"] == "Imported Workflow"
        assert data["flow"] == workflow_data["flow"]
        assert data["workspace_id"] == "39354e1f-b9cc-30eb-9700-963b3a53e977"
        assert data["created_by"] == mock_token_info["sub"]
    
    def test_import_workflow_duplicate_name(self, workflow_client, create_test_workflow):
        """Test cannot import workflow with duplicate name"""
        create_test_workflow(name="Existing Workflow")
        
        workflow_data = {
            "name": "Existing Workflow",  # Duplicate name
            "flow": [{"id": "1", "label": "Start", "type": "start", "position": None, "conditions": None, "next": None, "description": None, "ele": None}],
            "status": True
        }
        
        json_data = json.dumps(workflow_data)
        file_data = BytesIO(json_data.encode("utf-8"))
        
        response = workflow_client.post(
            "/workflows/import",
            files={"file": ("workflow.json", file_data, "application/json")}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in response.json()["detail"].lower()
    
    def test_import_workflow_invalid_file_type(self, workflow_client):
        """Test importing non-JSON file"""
        file_data = BytesIO(b"Not a JSON file")
        
        response = workflow_client.post(
            "/workflows/import",
            files={"file": ("workflow.txt", file_data, "text/plain")}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Only .json files" in response.json()["detail"]
    
    def test_import_workflow_invalid_json(self, workflow_client):
        """Test importing invalid JSON file"""
        file_data = BytesIO(b"{invalid json")
        
        response = workflow_client.post(
            "/workflows/import",
            files={"file": ("workflow.json", file_data, "application/json")}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid JSON" in response.json()["detail"]
    
    def test_import_workflow_invalid_structure(self, workflow_client):
        """Test importing JSON with invalid workflow structure"""
        invalid_data = {
            "name": "Invalid Workflow"
            # Missing required 'flow' field
        }
        
        json_data = json.dumps(invalid_data)
        file_data = BytesIO(json_data.encode("utf-8"))
        
        response = workflow_client.post(
            "/workflows/import",
            files={"file": ("workflow.json", file_data, "application/json")}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid workflow structure" in response.json()["detail"]


class TestWorkflowAuthentication:
    """Test authentication for workflow endpoints"""
    
    def test_workflow_endpoints_require_auth(self, unauth_client):
        """Test that workflow endpoints require authentication"""
        endpoints_to_test = [
            ("GET", "/workflows"),
            ("POST", "/workflows"),
            ("GET", "/workflows/1"),
            ("PUT", "/workflows/1"),
            ("DELETE", "/workflows/1"),
            ("GET", "/workflows/1/export"),
            ("POST", "/workflows/import"),
        ]
        
        for method, endpoint in endpoints_to_test:
            if method == "GET":
                response = unauth_client.get(endpoint)
            elif method == "POST":
                if endpoint == "/workflows":
                    response = unauth_client.post(endpoint, json={
                        "name": "test",
                        "flow": [{"id": "1", "label": "test", "type": "start"}]
                    })
                else:  # /import
                    response = unauth_client.post(endpoint)
            elif method == "PUT":
                response = unauth_client.put(endpoint, json={
                    "name": "test",
                    "flow": [{"id": "1", "label": "test", "type": "start"}]
                })
            elif method == "DELETE":
                response = unauth_client.delete(endpoint)
            
            # Should return 401 or 403
            assert response.status_code in [401, 403], f"{method} {endpoint} should require auth"
    
    def test_workflow_endpoints_require_workspace(self, auth_client_no_workspace):
        """Test that workflow endpoints require workspace scope in token"""
        response = auth_client_no_workspace.get("/workflows")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "No workspace access" in response.json()["detail"]


class TestWorkflowValidation:
    """Test validation for workflow endpoints"""
    
    def test_create_workflow_validation_errors(self, workflow_client):
        """Test validation errors when creating workflow"""
        # Missing required field (name)
        response = workflow_client.post("/workflows", json={
            "flow": [{"id": "1", "label": "test", "type": "start"}]
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Missing required field (flow)
        response = workflow_client.post("/workflows", json={
            "name": "Test Workflow"
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Empty name
        response = workflow_client.post("/workflows", json={
            "name": "",
            "flow": [{"id": "1", "label": "test", "type": "start"}]
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Invalid flow structure (missing id in node)
        response = workflow_client.post("/workflows", json={
            "name": "Test Workflow",
            "flow": [{"label": "test", "type": "start"}]  # Missing id
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_update_workflow_validation(self, workflow_client, create_test_workflow):
        """Test validation when updating workflow"""
        workflow = create_test_workflow()
        
        # Empty name
        response = workflow_client.put(f"/workflows/{workflow.id}", json={
            "name": "",
            "flow": workflow.flow,
            "status": workflow.status
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Invalid flow structure
        response = workflow_client.put(f"/workflows/{workflow.id}", json={
            "name": "Updated",
            "flow": [{"label": "test"}],  # Missing id and type
            "status": True
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestWorkflowEdgeCases:
    """Test edge cases for workflow endpoints"""
    
    def test_create_multiple_workflows(self, workflow_client, mock_token_info):
        """Test creating multiple workflows"""
        for i in range(5):
            workflow_data = {
                "name": f"Workflow {i}",
                "flow": [{"id": str(i), "label": f"Node {i}", "type": "start"}],
                "status": i % 2 == 0  # Alternate status
            }
            response = workflow_client.post("/workflows", json=workflow_data)
            assert response.status_code == status.HTTP_200_OK
        
        # Verify all were created
        response = workflow_client.get("/workflows")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 5
    
    def test_workflow_status_toggle(self, workflow_client, create_test_workflow):
        """Test enabling/disabling workflow"""
        # Create disabled workflow
        workflow_data = {
            "name": "Disabled Workflow",
            "flow": [{"id": "1", "label": "Start", "type": "start"}],
            "status": False
        }
        
        response = workflow_client.post("/workflows", json=workflow_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] is False
        
        # Update to enabled
        update_data = workflow_data.copy()
        update_data["status"] = True
        
        update_response = workflow_client.put(f"/workflows/{data['id']}", json=update_data)
        assert update_response.status_code == status.HTTP_200_OK
        updated_data = update_response.json()
        
        assert updated_data["status"] is True