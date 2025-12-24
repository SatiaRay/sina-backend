# dependencies.py
from typing import Optional, Dict, Any, List
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .oauth_service import OAuthIntrospectionService

# Create HTTP Bearer scheme
security_scheme = HTTPBearer(auto_error=False)

# Create a single instance of the service
oauth_service = OAuthIntrospectionService()

async def get_token_from_header(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> str:
    """Extract token from Authorization header"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return credentials.credentials

async def get_current_user(
    token: str = Depends(get_token_from_header)
) -> Dict[str, Any]:
    """
    Main dependency that validates the token and returns user info
    """
    token_info = await oauth_service.introspect_token(token)
    return token_info

async def get_current_user_with_scopes(
    required_scopes: Optional[List[str]] = None
):
    """
    Dependency that validates token and checks for required scopes
    """
    async def dependency(
        token: str = Depends(get_token_from_header)
    ) -> Dict[str, Any]:
        token_info = await oauth_service.introspect_token(token)
        
        # Check scopes if required
        if required_scopes:
            user_scopes = token_info.get("scope", "").split()
            for required_scope in required_scopes:
                if required_scope not in user_scopes:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Missing required scope: {required_scope}"
                    )
        
        return token_info
    
    return dependency

async def extract_workspace_id(token_info: Dict[str, Any]) -> Optional[str]:
    """
    Extract workspace ID from token scopes
    Format in your example: "workspace:39354e1f-b9cc-30eb-9700-963b3a53e977"
    """
    scope = token_info.get("scope", "")
    scopes = scope.split()
    
    for scope_item in scopes:
        if scope_item.startswith("workspace:"):
            # Extract workspace ID after "workspace:"
            return scope_item.split(":", 1)[1]
    
    return None

async def extract_all_workspace_ids(token_info: Dict[str, Any]) -> List[str]:
    """
    Extract all workspace IDs from token scopes
    Useful when user has access to multiple workspaces
    """
    scope = token_info.get("scope", "")
    scopes = scope.split()
    
    workspace_ids = []
    for scope_item in scopes:
        if scope_item.startswith("workspace:"):
            workspace_id = scope_item.split(":", 1)[1]
            workspace_ids.append(workspace_id)
    
    return workspace_ids

async def get_current_workspace(
    token_info: Dict[str, Any] = Depends(get_current_user)
) -> str:
    """
    Dependency that extracts and validates the current workspace
    Requires exactly one workspace in the token
    """
    workspace_id = await extract_workspace_id(token_info)
    
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No workspace access found in token"
        )
    
    return workspace_id

async def get_current_workspace_or_none(
    token_info: Dict[str, Any] = Depends(get_current_user)
) -> Optional[str]:
    """
    Dependency that extracts workspace if present, returns None otherwise
    """
    return await extract_workspace_id(token_info)

async def get_workspace_from_param_or_token(
    workspace_id: Optional[str] = None,
    token_info: Dict[str, Any] = Depends(get_current_user)
) -> str:
    """
    Dependency that gets workspace from parameter or token
    Useful for endpoints that accept workspace_id as parameter
    """
    if workspace_id:
        # Validate that the user has access to the requested workspace
        user_workspace_ids = await extract_all_workspace_ids(token_info)
        
        if workspace_id not in user_workspace_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to workspace: {workspace_id}"
            )
        
        return workspace_id
    
    # No parameter provided, get from token
    token_workspace_id = await extract_workspace_id(token_info)
    
    if not token_workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workspace ID required - either provide as parameter or include in token scope"
        )
    
    return token_workspace_id

async def require_workspace_access(
    workspace_id: str,
    token_info: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Dependency that validates access to a specific workspace
    """
    user_workspace_ids = await extract_all_workspace_ids(token_info)
    
    if workspace_id not in user_workspace_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to workspace: {workspace_id}"
        )
    
    return token_info