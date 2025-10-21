# app/models/user.py
from sqlalchemy import Boolean, Column, Integer, String, DateTime, func
from .database import Base
from datetime import datetime

class BaseModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Document(BaseModel):
    __tablename__ = "documents"

    vector_id = Column(String(255), index=True, unique=True)
    status = Column(Boolean, default=True)