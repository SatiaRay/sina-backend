"""
Unit tests for workspace tenancy functionality.

Tests row-level isolation, access control, and query scoping between workspaces.
"""

import pytest
from sqlalchemy.orm import Session
from database.models import (
    User, Workspace, WorkspaceUser, Wizard, Document, 
    Workflow, Instruction, CrawledDomain, CrawlJobs
)
from util.tenancy import WorkspaceTenancyManager, ensure_workspace_access
from datetime import datetime


class TestWorkspaceTenancyManager:
    """Test cases for WorkspaceTenancyManager."""
    
    def test_scope_query_by_workspace(self, db_session: Session):
        """Test scoping queries to a specific workspace."""
        # Create test data
        user1 = User(email="user1@test.com", password_hash="hash1")
        user2 = User(email="user2@test.com", password_hash="hash2")
        db_session.add_all([user1, user2])
        db_session.commit()
        
        workspace1 = Workspace(name="Workspace 1", owner_id=user1.id)
        workspace2 = Workspace(name="Workspace 2", owner_id=user2.id)
        db_session.add_all([workspace1, workspace2])
        db_session.commit()
        
        # Create wizards in different workspaces
        wizard1 = Wizard(title="Wizard 1", workspace_id=workspace1.id)
        wizard2 = Wizard(title="Wizard 2", workspace_id=workspace2.id)
        wizard3 = Wizard(title="Wizard 3", workspace_id=workspace1.id)
        db_session.add_all([wizard1, wizard2, wizard3])
        db_session.commit()
        
        # Test scoping to workspace1
        scoped_query = WorkspaceTenancyManager.scope_query_by_workspace(
            db_session, Wizard, workspace1.id
        )
        workspace1_wizards = scoped_query.all()
        
        assert len(workspace1_wizards) == 2
        assert all(w.workspace_id == workspace1.id for w in workspace1_wizards)
        assert "Wizard 1" in [w.title for w in workspace1_wizards]
        assert "Wizard 3" in [w.title for w in workspace1_wizards]
        assert "Wizard 2" not in [w.title for w in workspace1_wizards]
    
    def test_scope_query_by_user_workspaces(self, db_session: Session):
        """Test scoping queries to all workspaces a user has access to."""
        # Create test data
        user1 = User(email="user1@test.com", password_hash="hash1")
        user2 = User(email="user2@test.com", password_hash="hash2")
        db_session.add_all([user1, user2])
        db_session.commit()
        
        workspace1 = Workspace(name="Workspace 1", owner_id=user1.id)
        workspace2 = Workspace(name="Workspace 2", owner_id=user2.id)
        workspace3 = Workspace(name="Workspace 3", owner_id=user1.id)
        db_session.add_all([workspace1, workspace2, workspace3])
        db_session.commit()
        
        # Add user1 to workspace2 as member
        workspace_user = WorkspaceUser(
            workspace_id=workspace2.id, 
            user_id=user1.id, 
            role='member'
        )
        db_session.add(workspace_user)
        db_session.commit()
        
        # Create documents in different workspaces
        doc1 = Document(title="Doc 1", workspace_id=workspace1.id)
        doc2 = Document(title="Doc 2", workspace_id=workspace2.id)
        doc3 = Document(title="Doc 3", workspace_id=workspace3.id)
        doc4 = Document(title="Doc 4", workspace_id=workspace2.id)
        db_session.add_all([doc1, doc2, doc3, doc4])
        db_session.commit()
        
        # Test scoping to user1's accessible workspaces
        scoped_query = WorkspaceTenancyManager.scope_query_by_user_workspaces(
            db_session, Document, user1.id
        )
        user1_docs = scoped_query.all()
        
        # User1 should have access to workspace1 (owner), workspace2 (member), workspace3 (owner)
        assert len(user1_docs) == 4
        workspace_ids = [doc.workspace_id for doc in user1_docs]
        assert workspace1.id in workspace_ids
        assert workspace2.id in workspace_ids
        assert workspace3.id in workspace_ids
    
    def test_validate_workspace_access(self, db_session: Session):
        """Test workspace access validation."""
        # Create test data
        user1 = User(email="user1@test.com", password_hash="hash1")
        user2 = User(email="user2@test.com", password_hash="hash2")
        db_session.add_all([user1, user2])
        db_session.commit()
        
        workspace1 = Workspace(name="Workspace 1", owner_id=user1.id)
        workspace2 = Workspace(name="Workspace 2", owner_id=user2.id)
        db_session.add_all([workspace1, workspace2])
        db_session.commit()
        
        # Add user1 to workspace2 as member
        workspace_user = WorkspaceUser(
            workspace_id=workspace2.id, 
            user_id=user1.id, 
            role='member'
        )
        db_session.add(workspace_user)
        db_session.commit()
        
        # Test access validation
        assert WorkspaceTenancyManager.validate_workspace_access(
            db_session, user1.id, workspace1.id
        )  # Owner access
        assert WorkspaceTenancyManager.validate_workspace_access(
            db_session, user1.id, workspace2.id
        )  # Member access
        assert not WorkspaceTenancyManager.validate_workspace_access(
            db_session, user2.id, workspace1.id
        )  # No access
    
    def test_get_user_workspaces(self, db_session: Session):
        """Test getting all workspaces a user has access to."""
        # Create test data
        user1 = User(email="user1@test.com", password_hash="hash1")
        user2 = User(email="user2@test.com", password_hash="hash2")
        db_session.add_all([user1, user2])
        db_session.commit()
        
        workspace1 = Workspace(name="Workspace 1", owner_id=user1.id)
        workspace2 = Workspace(name="Workspace 2", owner_id=user2.id)
        workspace3 = Workspace(name="Workspace 3", owner_id=user1.id)
        db_session.add_all([workspace1, workspace2, workspace3])
        db_session.commit()
        
        # Add user1 to workspace2 as member
        workspace_user = WorkspaceUser(
            workspace_id=workspace2.id, 
            user_id=user1.id, 
            role='member'
        )
        db_session.add(workspace_user)
        db_session.commit()
        
        # Test getting user1's workspaces
        user1_workspaces = WorkspaceTenancyManager.get_user_workspaces(
            db_session, user1.id
        )
        
        assert len(user1_workspaces) == 3
        workspace_names = [w.name for w in user1_workspaces]
        assert "Workspace 1" in workspace_names
        assert "Workspace 2" in workspace_names
        assert "Workspace 3" in workspace_names
    
    def test_get_user_workspace_role(self, db_session: Session):
        """Test getting user's role in a specific workspace."""
        # Create test data
        user1 = User(email="user1@test.com", password_hash="hash1")
        user2 = User(email="user2@test.com", password_hash="hash2")
        db_session.add_all([user1, user2])
        db_session.commit()
        
        workspace1 = Workspace(name="Workspace 1", owner_id=user1.id)
        workspace2 = Workspace(name="Workspace 2", owner_id=user2.id)
        db_session.add_all([workspace1, workspace2])
        db_session.commit()
        
        # Add user1 to workspace2 as admin
        workspace_user = WorkspaceUser(
            workspace_id=workspace2.id, 
            user_id=user1.id, 
            role='admin'
        )
        db_session.add(workspace_user)
        db_session.commit()
        
        # Test role retrieval
        assert WorkspaceTenancyManager.get_user_workspace_role(
            db_session, user1.id, workspace1.id
        ) == 'owner'  # Default owner role
        assert WorkspaceTenancyManager.get_user_workspace_role(
            db_session, user1.id, workspace2.id
        ) == 'admin'
        assert WorkspaceTenancyManager.get_user_workspace_role(
            db_session, user2.id, workspace1.id
        ) is None  # No access
    
    def test_create_workspace_scoped_object(self, db_session: Session):
        """Test creating workspace-scoped objects."""
        # Create test data
        user = User(email="user@test.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        workspace = Workspace(name="Test Workspace", owner_id=user.id)
        db_session.add(workspace)
        db_session.commit()
        
        # Test creating a wizard
        wizard = WorkspaceTenancyManager.create_workspace_scoped_object(
            db_session, Wizard, workspace.id, title="Test Wizard"
        )
        
        assert wizard.workspace_id == workspace.id
        assert wizard.title == "Test Wizard"
        assert wizard.id is not None
        
        # Test creating a workflow
        workflow = WorkspaceTenancyManager.create_workspace_scoped_object(
            db_session, Workflow, workspace.id, 
            name="Test Workflow", flow={"steps": []}
        )
        
        assert workflow.workspace_id == workspace.id
        assert workflow.name == "Test Workflow"
        assert workflow.id is not None
    
    def test_get_workspace_scoped_object(self, db_session: Session):
        """Test retrieving workspace-scoped objects."""
        # Create test data
        user = User(email="user@test.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        workspace1 = Workspace(name="Workspace 1", owner_id=user.id)
        workspace2 = Workspace(name="Workspace 2", owner_id=user.id)
        db_session.add_all([workspace1, workspace2])
        db_session.commit()
        
        # Create wizards in different workspaces
        wizard1 = Wizard(title="Wizard 1", workspace_id=workspace1.id)
        wizard2 = Wizard(title="Wizard 2", workspace_id=workspace2.id)
        db_session.add_all([wizard1, wizard2])
        db_session.commit()
        
        # Test retrieving wizard1 from workspace1
        retrieved_wizard = WorkspaceTenancyManager.get_workspace_scoped_object(
            db_session, Wizard, wizard1.id, workspace1.id
        )
        assert retrieved_wizard is not None
        assert retrieved_wizard.id == wizard1.id
        assert retrieved_wizard.title == "Wizard 1"
        
        # Test retrieving wizard1 from workspace2 (should fail)
        retrieved_wizard = WorkspaceTenancyManager.get_workspace_scoped_object(
            db_session, Wizard, wizard1.id, workspace2.id
        )
        assert retrieved_wizard is None
    
    def test_row_level_isolation(self, db_session: Session):
        """Test that data is properly isolated between workspaces."""
        # Create test data
        user1 = User(email="user1@test.com", password_hash="hash1")
        user2 = User(email="user2@test.com", password_hash="hash2")
        db_session.add_all([user1, user2])
        db_session.commit()
        
        workspace1 = Workspace(name="Workspace 1", owner_id=user1.id)
        workspace2 = Workspace(name="Workspace 2", owner_id=user2.id)
        db_session.add_all([workspace1, workspace2])
        db_session.commit()
        
        # Create documents with same title in different workspaces
        doc1 = Document(title="Same Title", workspace_id=workspace1.id)
        doc2 = Document(title="Same Title", workspace_id=workspace2.id)
        doc3 = Document(title="Different Title", workspace_id=workspace1.id)
        db_session.add_all([doc1, doc2, doc3])
        db_session.commit()
        
        # Test that workspace1 only sees its own documents
        workspace1_docs = WorkspaceTenancyManager.scope_query_by_workspace(
            db_session, Document, workspace1.id
        ).all()
        
        assert len(workspace1_docs) == 2
        assert all(doc.workspace_id == workspace1.id for doc in workspace1_docs)
        
        # Test that workspace2 only sees its own documents
        workspace2_docs = WorkspaceTenancyManager.scope_query_by_workspace(
            db_session, Document, workspace2.id
        ).all()
        
        assert len(workspace2_docs) == 1
        assert all(doc.workspace_id == workspace2.id for doc in workspace2_docs)
    
    def test_ensure_workspace_access(self, db_session: Session):
        """Test the ensure_workspace_access function."""
        # Create test data
        user1 = User(email="user1@test.com", password_hash="hash1")
        user2 = User(email="user2@test.com", password_hash="hash2")
        db_session.add_all([user1, user2])
        db_session.commit()
        
        workspace1 = Workspace(name="Workspace 1", owner_id=user1.id)
        workspace2 = Workspace(name="Workspace 2", owner_id=user2.id)
        db_session.add_all([workspace1, workspace2])
        db_session.commit()
        
        # Test successful access
        assert ensure_workspace_access(db_session, user1.id, workspace1.id) is True
        
        # Test failed access
        with pytest.raises(PermissionError):
            ensure_workspace_access(db_session, user2.id, workspace1.id)
    
    def test_multi_tenant_unique_constraints(self, db_session: Session):
        """Test that unique constraints work within workspace scope but not across workspaces."""
        # Create test data
        user1 = User(email="user1@test.com", password_hash="hash1")
        user2 = User(email="user2@test.com", password_hash="hash2")
        db_session.add_all([user1, user2])
        db_session.commit()
        
        workspace1 = Workspace(name="Workspace 1", owner_id=user1.id)
        workspace2 = Workspace(name="Workspace 2", owner_id=user2.id)
        db_session.add_all([workspace1, workspace2])
        db_session.commit()
        
        # Create workflows with same name in different workspaces (should work)
        workflow1 = Workflow(name="Same Name", workspace_id=workspace1.id)
        workflow2 = Workflow(name="Same Name", workspace_id=workspace2.id)
        db_session.add_all([workflow1, workflow2])
        db_session.commit()
        
        # Verify both workflows exist
        assert workflow1.id is not None
        assert workflow2.id is not None
        assert workflow1.name == workflow2.name
        assert workflow1.workspace_id != workflow2.workspace_id
        
        # Create domains with same domain in different workspaces (should work)
        domain1 = CrawledDomain(domain="example.com", workspace_id=workspace1.id)
        domain2 = CrawledDomain(domain="example.com", workspace_id=workspace2.id)
        db_session.add_all([domain1, domain2])
        db_session.commit()
        
        # Verify both domains exist
        assert domain1.id is not None
        assert domain2.id is not None
        assert domain1.domain == domain2.domain
        assert domain1.workspace_id != domain2.workspace_id


class TestWorkspaceScopedModels:
    """Test cases for workspace-scoped model behavior."""
    
    def test_workspace_scoped_model_inheritance(self, db_session: Session):
        """Test that workspace-scoped models have the required fields."""
        # Create test data
        user = User(email="user@test.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        workspace = Workspace(name="Test Workspace", owner_id=user.id)
        db_session.add(workspace)
        db_session.commit()
        
        # Test Wizard model
        wizard = Wizard(title="Test Wizard", workspace_id=workspace.id)
        db_session.add(wizard)
        db_session.commit()
        
        assert hasattr(wizard, 'workspace_id')
        assert wizard.workspace_id == workspace.id
        assert hasattr(wizard, 'workspace')
        assert wizard.workspace == workspace
        
        # Test Document model
        document = Document(title="Test Document", workspace_id=workspace.id)
        db_session.add(document)
        db_session.commit()
        
        assert hasattr(document, 'workspace_id')
        assert document.workspace_id == workspace.id
        assert hasattr(document, 'workspace')
        assert document.workspace == workspace
        
        # Test Workflow model
        workflow = Workflow(name="Test Workflow", workspace_id=workspace.id)
        db_session.add(workflow)
        db_session.commit()
        
        assert hasattr(workflow, 'workspace_id')
        assert workflow.workspace_id == workspace.id
        assert hasattr(workflow, 'workspace')
        assert workflow.workspace == workspace
    
    def test_workspace_relationship(self, db_session: Session):
        """Test the workspace relationship in scoped models."""
        # Create test data
        user = User(email="user@test.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        workspace = Workspace(name="Test Workspace", owner_id=user.id)
        db_session.add(workspace)
        db_session.commit()
        
        # Create multiple scoped objects
        wizard = Wizard(title="Test Wizard", workspace_id=workspace.id)
        document = Document(title="Test Document", workspace_id=workspace.id)
        workflow = Workflow(name="Test Workflow", workspace_id=workspace.id)
        instruction = Instruction(label="Test Instruction", text="Test text", workspace_id=workspace.id)
        
        db_session.add_all([wizard, document, workflow, instruction])
        db_session.commit()
        
        # Test that workspace has access to all scoped models
        assert wizard in workspace.wizards
        assert document in workspace.documents
        assert workflow in workspace.workflows
        assert instruction in workspace.instructions
        
        # Verify the relationship works in both directions
        assert wizard.workspace == workspace
        assert document.workspace == workspace
        assert workflow.workspace == workspace
        assert instruction.workspace == workspace 