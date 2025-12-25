from time import timezone
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    Boolean,
    JSON,
    Enum,
    TEXT,
    Uuid
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
import pymysql

pymysql.install_as_MySQLdb()

# Force reload of environment variables
load_dotenv(override=True)

# Create SQLAlchemy engine
DATABASE_URL = f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DATABASE')}"
engine = create_engine(DATABASE_URL)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


# Base model with common fields
class BaseModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))


# Wizard model
class Wizard(BaseModel):
    __tablename__ = "wizards"

    title = Column(String(255), nullable=False)
    context = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey("wizards.id"), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    wizard_type = Column(
        Enum("answer", "question", name="wizard_type_enum"),
        default="answer",
        nullable=False,
    )
    created_by = Column(String(255), nullable=False)

    # Relationship for self-referential hierarchy
    parent = relationship("Wizard", remote_side=lambda: [Wizard.id], backref="children")


class Chat(BaseModel):
    __tablename__ = "chats"
    session_id = Column(String(255), unique=True, nullable=False)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Relationships
    chat_history = relationship("ChatHistory", backref="session", lazy=True)


class ChatHistory(BaseModel):
    __tablename__ = "chat_history"
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    role = Column(Enum("developer", "assistant", "user", "system", name="role_enum"))
    body = Column(TEXT, nullable=False)
    hidden = Column(Boolean, default=False, nullable=True)
    type = Column(Enum("text", "image"), default="text", nullable=True)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Renamed 'metadata' to 'extra_metadata'
    extra_metadata = Column(JSON, nullable=True)


class Workflow(BaseModel):
    __tablename__ = "workflows"
    name = Column(String(255), unique=True, nullable=False)
    flow = Column(JSON)
    status = Column(Boolean, default=True)
    created_by = Column(String(255), nullable=False)

class Instruction(BaseModel):
    __tablename__ = "instructions"
    label = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    status = Column(Boolean, default=True)
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))


# Database dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Create all tables
def init_db():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database tables created successfully!")
