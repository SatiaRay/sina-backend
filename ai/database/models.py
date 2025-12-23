import enum
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
from datetime import datetime
import os
from dotenv import load_dotenv, find_dotenv
import pymysql

pymysql.install_as_MySQLdb()

# Force reload of environment variables
print("Loading environment from:", find_dotenv())
load_dotenv(override=True)

# Debug: Print database configuration
print("Environment Variables:")
print(f"Current Directory: {os.getcwd()}")
print(f"MYSQL_DATABASE from env: {os.environ.get('MYSQL_DATABASE')}")
print(f"MYSQL_DATABASE from getenv: {os.getenv('MYSQL_DATABASE')}")
print("\nDatabase Configuration:")
print(f"Host: {os.getenv('MYSQL_HOST')}")
print(f"User: {os.getenv('MYSQL_USER')}")
print(f"Database: {os.getenv('MYSQL_DATABASE')}")
print(f"Port: {os.getenv('MYSQL_PORT')}")

# Create SQLAlchemy engine
DATABASE_URL = f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DATABASE')}"
print(f"Database URL: {DATABASE_URL}")
engine = create_engine(DATABASE_URL)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


# Base model with common fields
class BaseModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Uuid)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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

    # Relationship for self-referential hierarchy
    parent = relationship("Wizard", remote_side=lambda: [Wizard.id], backref="children")


class Chat(BaseModel):
    __tablename__ = "chats"
    session_id = Column(String(255), unique=True, nullable=False)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    chat_history = relationship("ChatHistory", backref="session", lazy=True)


class ChatHistory(BaseModel):
    __tablename__ = "chat_history"
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    role = Column(Enum("developer", "assistant", "user", "system", name="role_enum"))
    body = Column(TEXT, nullable=False)
    hidden = Column(Boolean, default=False, nullable=True)
    type = Column(Enum("text", "image"), default="text", nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Renamed 'metadata' to 'extra_metadata'
    extra_metadata = Column(JSON, nullable=True)


class Workflow(BaseModel):
    __tablename__ = "workflows"
    name = Column(String(255), unique=True, nullable=False)
    flow = Column(JSON)
    status = Column(Boolean, default=True)

class Instruction(BaseModel):
    __tablename__ = "instructions"
    label = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    status = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
class FunctionCallLog(BaseModel):
    __tablename__ = "function_call_logs"
    
    timestamp = Column(DateTime, nullable=False, index=True)
    tool = Column(String(255), nullable=False, index=True)
    params = Column(JSON, nullable=True)
    session_id = Column(String(255), nullable=True, index=True)
    response = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=False)
    tokens_used = Column(Integer, nullable=True)
    additional_metadata = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<FunctionCallLog(tool='{self.tool}', timestamp={self.timestamp})>"


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
