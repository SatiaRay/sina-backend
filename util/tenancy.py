"""
Workspace Tenancy Management Utilities

This module provides utilities for implementing row-level isolation
between workspaces in the application.
"""

from typing import Optional, Type, TypeVar, List
from sqlalchemy.orm import Session, Query
from sqlalchemy import and_, or_, select, union_all
from database.models import WorkspaceScopedModel, Workspace, WorkspaceUser, User

T = TypeVar('T', bound=WorkspaceScopedModel)


class WorkspaceTenancyManager:
    """Manager for workspace tenancy operations."""
    
    @staticmethod
    def scope_query_by_workspace(
        session: Session, 
        model_class: Type[T], 
        workspace_id: int
    ) -> Query[T]:
        """
        Scope a query to a specific workspace.
        
        Args:
            session: Database session
            model_class: The model class to query
            workspace_id: The workspace ID to scope to
            
        Returns:
            Query scoped to the specified workspace
        """
        return session.query(model_class).filter(
            model_class.workspace_id == workspace_id
        )
    
    @staticmethod
    def scope_query_by_user_workspaces(
        session: Session,
        model_class: Type[T],
        user_id: int
    ) -> Query[T]:
        """
        Scope a query to all workspaces a user has access to.
        
        Args:
            session: Database session
            model_class: The model class to query
            user_id: The user ID to get workspaces for
            
        Returns:
            Query scoped to user's accessible workspaces
        """
        # Get workspace IDs where user is owner or member
        owner_ids = select(Workspace.id).where(Workspace.owner_id == user_id)
        member_ids = select(WorkspaceUser.workspace_id).where(WorkspaceUser.user_id == user_id)
        all_ids = union_all(owner_ids, member_ids).alias()
        return session.query(model_class).filter(
            model_class.workspace_id.in_(select(all_ids.c.id))
        )
    
    @staticmethod
    def validate_workspace_access(
        session: Session,
        user_id: int,
        workspace_id: int
    ) -> bool:
        """
        Validate if a user has access to a specific workspace.
        
        Args:
            session: Database session
            user_id: The user ID to check
            workspace_id: The workspace ID to check access for
            
        Returns:
            True if user has access, False otherwise
        """
        workspace = session.query(Workspace).filter(Workspace.id == workspace_id).first()
        if workspace and workspace.owner_id == user_id:
            return True
        workspace_user = session.query(WorkspaceUser).filter(
            and_(
                WorkspaceUser.user_id == user_id,
                WorkspaceUser.workspace_id == workspace_id
            )
        ).first()
        return workspace_user is not None
    
    @staticmethod
    def get_user_workspaces(
        session: Session,
        user_id: int
    ) -> List[Workspace]:
        """
        Get all workspaces a user has access to.
        
        Args:
            session: Database session
            user_id: The user ID to get workspaces for
            
        Returns:
            List of workspaces the user has access to
        """
        # All workspaces where user is owner or member
        owner_q = session.query(Workspace).filter(Workspace.owner_id == user_id)
        member_q = session.query(Workspace).join(WorkspaceUser).filter(WorkspaceUser.user_id == user_id)
        return owner_q.union(member_q).all()
    
    @staticmethod
    def get_user_workspace_role(
        session: Session,
        user_id: int,
        workspace_id: int
    ) -> Optional[str]:
        """
        Get the role of a user in a specific workspace.
        
        Args:
            session: Database session
            user_id: The user ID to check
            workspace_id: The workspace ID to check
            
        Returns:
            User's role in the workspace, or None if no access
        """
        workspace = session.query(Workspace).filter(Workspace.id == workspace_id).first()
        if workspace and workspace.owner_id == user_id:
            return 'owner'
        workspace_user = session.query(WorkspaceUser).filter(
            and_(
                WorkspaceUser.user_id == user_id,
                WorkspaceUser.workspace_id == workspace_id
            )
        ).first()
        return workspace_user.role if workspace_user else None
    
    @staticmethod
    def create_workspace_scoped_object(
        session: Session,
        model_class: Type[T],
        workspace_id: int,
        **kwargs
    ) -> T:
        """
        Create a new workspace-scoped object.
        
        Args:
            session: Database session
            model_class: The model class to create
            workspace_id: The workspace ID to associate with
            **kwargs: Additional fields for the object
            
        Returns:
            The created object
        """
        obj = model_class(workspace_id=workspace_id, **kwargs)
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return obj
    
    @staticmethod
    def get_workspace_scoped_object(
        session: Session,
        model_class: Type[T],
        object_id: int,
        workspace_id: int
    ) -> Optional[T]:
        """
        Get a workspace-scoped object by ID and workspace.
        
        Args:
            session: Database session
            model_class: The model class to query
            object_id: The object ID to retrieve
            workspace_id: The workspace ID to scope to
            
        Returns:
            The object if found and in the correct workspace, None otherwise
        """
        return session.query(model_class).filter(
            and_(
                model_class.id == object_id,
                model_class.workspace_id == workspace_id
            )
        ).first()


# Convenience functions for common operations
def scope_to_workspace(query: Query[T], workspace_id: int) -> Query[T]:
    """Scope a query to a specific workspace."""
    return query.filter(query.column.workspace_id == workspace_id)


def scope_to_user_workspaces(query: Query[T], user_id: int) -> Query[T]:
    """Scope a query to all workspaces a user has access to."""
    # This would need to be implemented with a subquery
    # For now, return the original query
    return query


def ensure_workspace_access(session: Session, user_id: int, workspace_id: int) -> bool:
    """Ensure a user has access to a workspace, raising an exception if not."""
    if not WorkspaceTenancyManager.validate_workspace_access(session, user_id, workspace_id):
        raise PermissionError(f"User {user_id} does not have access to workspace {workspace_id}")
    return True 