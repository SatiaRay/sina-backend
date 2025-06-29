from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime

from database.models import get_db, User, SessionLocal
from api.auth import get_current_user, verify_password, get_password_hash

# Create router
router = APIRouter(prefix="/users", tags=["User Management"])

# Pydantic models
class UserUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    user_type: Optional[str] = None
    is_verified: Optional[bool] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "updated@example.com",
                "first_name": "Updated",
                "last_name": "Name",
                "user_type": "supporter",
                "is_verified": True
            }
        }

class UserPasswordUpdateRequest(BaseModel):
    current_password: str
    new_password: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "current_password": "oldpassword123",
                "new_password": "newpassword123"
            }
        }

class UserListResponse(BaseModel):
    users: List[dict]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool
    
    class Config:
        from_attributes = True

class UserDetailResponse(BaseModel):
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    user_type: str
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime]
    email_verified_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    chat_count: Optional[int] = 0
    
    class Config:
        from_attributes = True

class UserStatusUpdateRequest(BaseModel):
    is_active: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "is_active": False
            }
        }

# Helper functions
def require_admin_access(current_user: User = Depends(get_current_user)) -> User:
    """Require admin access for user management operations"""
    if current_user.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for this operation"
        )
    return current_user

def get_user_by_id(user_id: int, db: Session) -> User:
    """Get user by ID or raise 404"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

def validate_user_type(user_type: str) -> bool:
    """Validate user type"""
    valid_types = ["admin", "supporter", "customer"]
    return user_type in valid_types

# Endpoints
@router.put("/{user_id}/status", response_model=UserDetailResponse)
async def update_user_status(
    user_id: int,
    status_data: UserStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_access)
):
    """
    Activate or deactivate a user account
    
    - **user_id**: ID of the user to update
    - **is_active**: True to activate, False to deactivate
    """
    # Prevent admin from deactivating themselves
    if user_id == current_user.id and not status_data.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    user = get_user_by_id(user_id, db)
    
    # Prevent deactivating other admin accounts
    if user.user_type == "admin" and not status_data.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate admin accounts"
        )
    
    user.is_active = status_data.is_active
    user.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        db.refresh(user)
        return user
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user status"
        )

@router.put("/{user_id}", response_model=UserDetailResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_access)
):
    """
    Update user information
    
    - **user_id**: ID of the user to update
    - **user_data**: User information to update
    """
    user = get_user_by_id(user_id, db)
    
    # Check if email is being changed and if it's already taken
    if user_data.email and user_data.email != user.email:
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        user.email = user_data.email
    
    # Validate user type if being changed
    if user_data.user_type and user_data.user_type != user.user_type:
        if not validate_user_type(user_data.user_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user type. Must be one of: admin, supporter, customer"
            )
        
        # Prevent changing admin user types
        if user.user_type == "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change admin user types"
            )
        
        user.user_type = user_data.user_type
    
    # Update other fields
    if user_data.first_name is not None:
        user.first_name = user_data.first_name
    if user_data.last_name is not None:
        user.last_name = user_data.last_name
    if user_data.is_verified is not None:
        user.is_verified = user_data.is_verified
        if user_data.is_verified and not user.email_verified_at:
            user.email_verified_at = datetime.utcnow()
    
    user.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        db.refresh(user)
        return user
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )

@router.put("/{user_id}/password")
async def update_user_password(
    user_id: int,
    password_data: UserPasswordUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update user password
    
    - **user_id**: ID of the user to update (users can only update their own password)
    - **current_password**: Current password for verification
    - **new_password**: New password
    """
    # Users can only update their own password, admins can update any password
    if current_user.user_type != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only update your own password"
        )
    
    user = get_user_by_id(user_id, db)
    
    # Verify current password
    if not verify_password(password_data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    user.password_hash = get_password_hash(password_data.new_password)
    user.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        return {"message": "Password updated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password"
        )

@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_access)
):
    """
    Delete a user account
    
    - **user_id**: ID of the user to delete
    """
    # Prevent admin from deleting themselves
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    user = get_user_by_id(user_id, db)
    
    # Prevent deleting admin accounts
    if user.user_type == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete admin accounts"
        )
    
    try:
        db.delete(user)
        db.commit()
        return {"message": "User deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )

@router.get("/", response_model=UserListResponse)
async def get_all_users(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by email, first name, or last name"),
    user_type: Optional[str] = Query(None, description="Filter by user type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_verified: Optional[bool] = Query(None, description="Filter by verification status"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_access)
):
    """
    Get all users with pagination and filtering options
    
    - **page**: Page number (default: 1)
    - **per_page**: Items per page (default: 10, max: 100)
    - **search**: Search in email, first name, or last name
    - **user_type**: Filter by user type (admin, supporter, customer)
    - **is_active**: Filter by active status
    - **is_verified**: Filter by verification status
    - **sort_by**: Sort field (id, email, first_name, last_name, user_type, created_at)
    - **sort_order**: Sort order (asc or desc)
    """
    # Build query
    query = db.query(User)
    
    # Apply search filter
    if search:
        search_filter = or_(
            User.email.ilike(f"%{search}%"),
            User.first_name.ilike(f"%{search}%"),
            User.last_name.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    # Apply filters
    if user_type:
        if not validate_user_type(user_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user type filter"
            )
        query = query.filter(User.user_type == user_type)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    if is_verified is not None:
        query = query.filter(User.is_verified == is_verified)
    
    # Apply sorting
    valid_sort_fields = ["id", "email", "first_name", "last_name", "user_type", "created_at", "updated_at"]
    if sort_by not in valid_sort_fields:
        sort_by = "created_at"
    
    sort_column = getattr(User, sort_by)
    if sort_order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    users = query.offset(offset).limit(per_page).all()
    
    # Calculate pagination info
    total_pages = (total + per_page - 1) // per_page
    has_next = page < total_pages
    has_prev = page > 1
    
    # Convert users to dict for response
    user_list = []
    for user in users:
        user_dict = {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "user_type": user.user_type,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "last_login": user.last_login,
            "email_verified_at": user.email_verified_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        }
        user_list.append(user_dict)
    
    return UserListResponse(
        users=user_list,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )

@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed user information
    
    - **user_id**: ID of the user to get details for
    """
    # Users can only view their own details, admins can view any user
    if current_user.user_type != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own user details"
        )
    
    user = get_user_by_id(user_id, db)
    
    # Get chat count for the user
    chat_count = db.query(user.__class__).join(user.__class__.chats).filter(user.__class__.id == user_id).count()
    
    # Create response with chat count
    response_data = {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "user_type": user.user_type,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "last_login": user.last_login,
        "email_verified_at": user.email_verified_at,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "chat_count": chat_count
    }
    
    return UserDetailResponse(**response_data)

@router.get("/search/{email}")
async def find_user_by_email(
    email: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_access)
):
    """
    Find user by email address
    
    - **email**: Email address to search for
    """
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get chat count
    chat_count = db.query(user.__class__).join(user.__class__.chats).filter(user.__class__.id == user.id).count()
    
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "user_type": user.user_type,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "last_login": user.last_login,
        "email_verified_at": user.email_verified_at,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "chat_count": chat_count
    }

@router.get("/me/profile", response_model=UserDetailResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's profile information
    """
    # Get chat count for current user
    chat_count = db.query(current_user.__class__).join(current_user.__class__.chats).filter(current_user.__class__.id == current_user.id).count()
    
    response_data = {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "user_type": current_user.user_type,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "last_login": current_user.last_login,
        "email_verified_at": current_user.email_verified_at,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
        "chat_count": chat_count
    }
    
    return UserDetailResponse(**response_data)

@router.put("/me/profile")
async def update_my_profile(
    user_data: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update current user's profile (excluding user_type and is_verified)
    """
    # Check if email is being changed and if it's already taken
    if user_data.email and user_data.email != current_user.email:
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        current_user.email = user_data.email
    
    # Update allowed fields
    if user_data.first_name is not None:
        current_user.first_name = user_data.first_name
    if user_data.last_name is not None:
        current_user.last_name = user_data.last_name
    
    # Users cannot change their own user_type or verification status
    if user_data.user_type is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change user type"
        )
    
    if user_data.is_verified is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change verification status"
        )
    
    current_user.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        db.refresh(current_user)
        return {"message": "Profile updated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        ) 