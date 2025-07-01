from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime
from database.models import get_db, User
from api.auth import get_current_user, get_password_hash

router = APIRouter(prefix="/operators", tags=["Operator Management"])

# Pydantic models
class OperatorCreateRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class OperatorUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None

class OperatorOut(BaseModel):
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class PaginatedOperatorResponse(BaseModel):
    operators: List[OperatorOut]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool

# Dependency: require operator access

def require_operator_access(current_user: User = Depends(get_current_user)) -> User:
    if current_user.user_type != "operator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator access required for this operation"
        )
    return current_user

# Create operator
@router.post("/", response_model=OperatorOut)
def create_operator(
    operator: OperatorCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_access)
):
    existing = db.query(User).filter(User.email == operator.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=operator.email,
        password_hash=get_password_hash(operator.password),
        first_name=operator.first_name,
        last_name=operator.last_name,
        user_type="operator",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

# List operators with pagination
@router.get("/", response_model=PaginatedOperatorResponse)
def list_operators(
    page: int = Query(1, ge=1, description="Page number (starting from 1)"),
    per_page: int = Query(10, ge=1, le=100, description="Number of operators per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_access)
):
    offset = (page - 1) * per_page
    query = db.query(User).filter(User.user_type == "operator")
    total = query.count()
    total_pages = (total + per_page - 1) // per_page
    operators = query.offset(offset).limit(per_page).all()
    return PaginatedOperatorResponse(
        operators=operators,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )

# Get operator detail
@router.get("/{operator_id}", response_model=OperatorOut)
def get_operator_detail(
    operator_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_access)
):
    user = db.query(User).filter(User.id == operator_id, User.user_type == "operator").first()
    if not user:
        raise HTTPException(status_code=404, detail="Operator not found")
    return user

# Update operator
@router.put("/{operator_id}", response_model=OperatorOut)
def update_operator(
    operator_id: int,
    operator_data: OperatorUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_access)
):
    user = db.query(User).filter(User.id == operator_id, User.user_type == "operator").first()
    if not user:
        raise HTTPException(status_code=404, detail="Operator not found")
    if operator_data.email and operator_data.email != user.email:
        existing = db.query(User).filter(User.email == operator_data.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        user.email = operator_data.email
    if operator_data.first_name is not None:
        user.first_name = operator_data.first_name
    if operator_data.last_name is not None:
        user.last_name = operator_data.last_name
    if operator_data.is_active is not None:
        user.is_active = operator_data.is_active
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user

# Delete operator
@router.delete("/{operator_id}", status_code=204)
def delete_operator(
    operator_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_access)
):
    user = db.query(User).filter(User.id == operator_id, User.user_type == "operator").first()
    if not user:
        raise HTTPException(status_code=404, detail="Operator not found")
    db.delete(user)
    db.commit()
    return 