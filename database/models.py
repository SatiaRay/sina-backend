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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# User model for authentication
class User(BaseModel):
    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    user_type = Column(
        Enum("admin", "supporter", "customer", name="user_type_enum"),
        default="customer",
        nullable=False,
    )
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    last_login = Column(DateTime, nullable=True)
    email_verified_at = Column(DateTime, nullable=True)

    # Relationships
    chats = relationship("Chat", back_populates="user")

    def __repr__(self):
        return (
            f"<User(id={self.id}, email='{self.email}', user_type='{self.user_type}')>"
        )


# Wizard model
class Wizard(BaseModel):
    __tablename__ = "wizards"

    title = Column(String(255), nullable=False)
    context = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey("wizards.id"), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)

    # Relationship for self-referential hierarchy
    parent = relationship("Wizard", remote_side=lambda: [Wizard.id], backref="children")


# CrawledDomain model
class CrawledDomain(BaseModel):
    __tablename__ = "crawled_domains"

    domain = Column(String(255), unique=True, nullable=False)
    documents = relationship("Document", back_populates="domain")


class CrawlJobs(BaseModel):
    __tablename__ = "crawl_jobs"
    job_id = Column(String(255), unique=True, nullable=False)
    init_url = Column(String(255), nullable=False)
    recursive = Column(Boolean, default=False, nullable=False)
    save_in_vector = Column(Boolean, default=False, nullable=False)
    logs = Column(Text, nullable=True)
    status = Column(JSON, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    end_at = Column(DateTime, nullable=True)


# Document model
class Document(BaseModel):
    __tablename__ = "documents"
    title = Column(String(255))
    _html = Column("html", Text(length=4294967295))  # MySQL LONGTEXT
    markdown = Column(Text(length=4294967295), nullable=True)  # MySQL LONGTEXT
    ai_markdown = Column(
        Boolean,
        default=False,
        comment="Indicates the document markdown generated with AI model or is simple text or html text output",
    )
    uri = Column(String(255), nullable=True)
    domain_id = Column(Integer, ForeignKey("crawled_domains.id"), nullable=True)
    type = Column(Enum("manual", "crawl"), default="crawl")
    agent_type = Column(
        Enum("voice_agent", "text_agent", "both", name="agent_type_enum"),
        default="text_agent",
        nullable=False,
    )
    status = Column(Enum("pending", "vectorized", "error", name="status_enum"), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    domain = relationship("CrawledDomain", back_populates="documents")

    @property
    def html(self):
        """Get decoded HTML content"""
        return self.decode_html(self._html)

    @html.setter
    def html(self, value):
        """Set encoded HTML content"""
        self._html = self.encode_html(value)

    def __init__(self, **kwargs):
        if "html" in kwargs:
            kwargs["_html"] = self.encode_html(kwargs.pop("html"))
        super().__init__(**kwargs)

    @staticmethod
    def encode_html(html_content):
        """Encode HTML content for storage"""
        if html_content is None:
            return None
        return html_content.encode("utf-8").hex()

    @staticmethod
    def decode_html(encoded_html):
        """Decode HTML content from storage"""
        if encoded_html is None:
            return None
        try:
            return bytes.fromhex(encoded_html).decode("utf-8")
        except:
            return encoded_html  # Return original if decoding fails


class Chat(BaseModel):
    __tablename__ = "chats"
    session_id = Column(String(255), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Link to user
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="chats")
    chat_history = relationship("ChatHistory", backref="session", lazy=True)


class ChatHistory(BaseModel):
    __tablename__ = "chat_history"
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    role = Column(Enum("developer", "assistant", "user", "system", name="role_enum"))
    body = Column(TEXT, nullable=False)
    hidden = Column(Boolean, default=False, nullable=True)
    type = Column(Enum("text", "file"), default="text", nullable=True)
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
    agent_type = Column(
        Enum("voice_agent", "text_agent", "both", name="agent_type_enum"),
        default="text_agent",
        nullable=False,
    )


class Instruction(BaseModel):
    __tablename__ = "instructions"
    label = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    status = Column(Boolean, default=True)
    agent_type = Column(
        Enum("voice_agent", "text_agent", "both", name="agent_type_enum"),
        default="text_agent",
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
class FunctionCallLog(BaseModel):
    __tablename__ = "function_call_logs"
    
    timestamp = Column(DateTime, nullable=False, index=True)
    tool = Column(String(255), nullable=False, index=True)
    params = Column(JSON, nullable=True)
    user_id = Column(String(255), nullable=True, index=True)
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
