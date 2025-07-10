from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey, Boolean, JSON, Enum, TEXT, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base, declared_attr
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

# Base model for workspace-scoped models (row-level isolation)
class WorkspaceScopedModel(BaseModel):
    __abstract__ = True

    @declared_attr
    def workspace_id(cls):
        return Column(Integer, ForeignKey("workspaces.id"), nullable=False, index=True)

    @declared_attr
    def workspace(cls):
        return relationship("Workspace", back_populates=cls.__tablename__)

# User model for authentication
class User(BaseModel):
    __tablename__ = "users"
    
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    user_type = Column(Enum('admin', 'supporter', 'customer', 'operator', name='user_type_enum'), default='customer', nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    last_login = Column(DateTime, nullable=True)
    email_verified_at = Column(DateTime, nullable=True)
    
    # New: Current workspace selection
    current_workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True)
    current_workspace = relationship("Workspace", foreign_keys="User.current_workspace_id", post_update=True)
    
    # Relationships
    chats = relationship("Chat", back_populates="user")
    owned_workspaces = relationship("Workspace", back_populates="owner", foreign_keys="Workspace.owner_id")
    workspaces = relationship("WorkspaceUser", back_populates="user", cascade="all, delete-orphan")
    owned_aibots = relationship("AiBot", back_populates="owner", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', user_type='{self.user_type}')>"

# Workspace model
class Workspace(BaseModel):
    __tablename__ = "workspaces"
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    owner = relationship("User", back_populates="owned_workspaces", foreign_keys=[owner_id])
    users = relationship("WorkspaceUser", back_populates="workspace", cascade="all, delete-orphan")
    # Add one-to-many relationships for each workspace-scoped model
    wizards = relationship("Wizard", back_populates="workspace", cascade="all, delete-orphan")
    crawled_domains = relationship("CrawledDomain", back_populates="workspace", cascade="all, delete-orphan")
    crawl_jobs = relationship("CrawlJobs", back_populates="workspace", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="workspace", cascade="all, delete-orphan")
    workflows = relationship("Workflow", back_populates="workspace", cascade="all, delete-orphan")
    instructions = relationship("Instruction", back_populates="workspace", cascade="all, delete-orphan")
    aibots = relationship("AiBot", back_populates="workspace", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Workspace(id={self.id}, name='{self.name}', owner_id={self.owner_id})>"

# Association table for many-to-many relationship between users and workspaces
class WorkspaceUser(BaseModel):
    __tablename__ = "workspace_users"
    
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(Enum('owner', 'admin', 'member', 'viewer', name='workspace_role_enum'), default='member', nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    workspace = relationship("Workspace", back_populates="users")
    user = relationship("User", back_populates="workspaces")
    
    def __repr__(self):
        return f"<WorkspaceUser(workspace_id={self.workspace_id}, user_id={self.user_id}, role='{self.role}')>"

# Wizard model - now workspace-scoped
class Wizard(WorkspaceScopedModel):
    __tablename__ = "wizards"
    
    title = Column(String(255), nullable=False)
    context = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey("wizards.id"), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    aibot_id = Column(Integer, ForeignKey("aibots.id"), nullable=True)
    
    # Relationship for self-referential hierarchy
    parent = relationship(
        "Wizard",
        remote_side=lambda: [Wizard.id],
        backref="children"
    )
    aibot = relationship("AiBot", back_populates="wizards")
    
    def __repr__(self):
        return f"<Wizard(id={self.id}, title='{self.title}', workspace_id={self.workspace_id})>"

# CrawledDomain model - now workspace-scoped
class CrawledDomain(WorkspaceScopedModel):
    __tablename__ = "crawled_domains"
    
    domain = Column(String(255), nullable=False)  # Removed unique constraint for multi-tenant
    documents = relationship("Document", back_populates="domain")
    
    def __repr__(self):
        return f"<CrawledDomain(id={self.id}, domain='{self.domain}', workspace_id={self.workspace_id})>"

# CrawlJobs model - now workspace-scoped
class CrawlJobs(WorkspaceScopedModel):
    __tablename__ = "crawl_jobs"
    
    job_id = Column(String(255), nullable=False)  # Removed unique constraint for multi-tenant
    init_url = Column(String(255), nullable=False)
    recursive = Column(Boolean, default=False, nullable=False)
    save_in_vector = Column(Boolean, default=False, nullable=False)
    logs = Column(Text, nullable=True)
    status = Column(JSON, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    end_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<CrawlJobs(id={self.id}, job_id='{self.job_id}', workspace_id={self.workspace_id})>"

# Document model - now workspace-scoped
class Document(WorkspaceScopedModel):
    __tablename__ = "documents"
    
    title = Column(String(255))
    _html = Column("html", Text(length=4294967295))  # MySQL LONGTEXT
    markdown = Column(Text(length=4294967295), nullable=True)  # MySQL LONGTEXT
    ai_markdown = Column(Boolean, default=False, comment="Indicates the document markdown generated with AI model or is simple text or html text output")
    uri = Column(String(255), nullable=True)
    domain_id = Column(Integer, ForeignKey("crawled_domains.id"), nullable=True)
    aibot_id = Column(Integer, ForeignKey("aibots.id"), nullable=True)
    vector_id = Column(String(255), nullable=True)
    type = Column(Enum('manual', 'crawl'), default="crawl")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    domain = relationship("CrawledDomain", back_populates="documents")
    aibot = relationship("AiBot", back_populates="documents")

    @property
    def html(self):
        """Get decoded HTML content"""
        return self.decode_html(self._html)

    @html.setter
    def html(self, value):
        """Set encoded HTML content"""
        self._html = self.encode_html(value)

    def __init__(self, **kwargs):
        if 'html' in kwargs:
            kwargs['_html'] = self.encode_html(kwargs.pop('html'))
        super().__init__(**kwargs)

    @staticmethod
    def encode_html(html_content):
        """Encode HTML content for storage"""
        if html_content is None:
            return None
        return html_content.encode('utf-8').hex()

    @staticmethod
    def decode_html(encoded_html):
        """Decode HTML content from storage"""
        if encoded_html is None:
            return None
        try:
            return bytes.fromhex(encoded_html).decode('utf-8')
        except:
            return encoded_html  # Return original if decoding fails
    
    def __repr__(self):
        return f"<Document(id={self.id}, title='{self.title}', workspace_id={self.workspace_id})>"
        
class Chat(BaseModel):
    __tablename__ = 'chats'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(255), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Link to user
    status = Column(String(20), default='active')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    aibot_id = Column(Integer, ForeignKey('aibots.id'), nullable=True)

    # Relationships
    user = relationship("User", back_populates="chats")
    chat_history = relationship('ChatHistory', backref='session', lazy=True)
    aibot = relationship("AiBot", back_populates="chats")

class ChatHistory(BaseModel):
    __tablename__ = 'chat_history'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    chat_id = Column(Integer, ForeignKey('chats.id'), nullable=False)
    role = Column(Enum('developer', 'assistant', 'user', 'system', name='role_enum'))
    body = Column(TEXT, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Renamed 'metadata' to 'extra_metadata'
    extra_metadata = Column(JSON, nullable=True)

class Workflow(WorkspaceScopedModel):
    __tablename__ = 'workflows'
    
    name = Column(String(255), nullable=False)  # Removed unique constraint for multi-tenant
    flow = Column(JSON)
    status = Column(Boolean, default=True)
    aibot_id = Column(Integer, ForeignKey('aibots.id'), nullable=True)
    aibot = relationship("AiBot", back_populates="workflows")
    
    def __repr__(self):
        return f"<Workflow(id={self.id}, name='{self.name}', workspace_id={self.workspace_id})>"

class Instruction(WorkspaceScopedModel):
    __tablename__ = 'instructions'
    
    label = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    status = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    aibot_id = Column(Integer, ForeignKey('aibots.id'), nullable=True)
    aibot = relationship("AiBot", back_populates="instructions")
    
    def __repr__(self):
        return f"<Instruction(id={self.id}, label='{self.label}', workspace_id={self.workspace_id})>"

# AiBot model
class AiBot(BaseModel):
    __tablename__ = 'aibots'
    name = Column(String(255), nullable=False)
    workspace_id = Column(Integer, ForeignKey('workspaces.id'), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    token = Column(String(64), unique=True, nullable=False, default=lambda: AiBot.generate_token())

    # Relationships
    workspace = relationship('Workspace', back_populates='aibots')
    owner = relationship('User', back_populates='owned_aibots')
    documents = relationship('Document', back_populates='aibot', cascade="all, delete-orphan")
    chats = relationship('Chat', back_populates='aibot', cascade="all, delete-orphan")
    workflows = relationship('Workflow', back_populates='aibot', cascade="all, delete-orphan")
    instructions = relationship('Instruction', back_populates='aibot', cascade="all, delete-orphan")
    wizards = relationship('Wizard', back_populates='aibot', cascade="all, delete-orphan")

    @staticmethod
    def generate_token():
        import secrets
        return secrets.token_hex(32)

    def __init__(self, **kwargs):
        if 'token' not in kwargs or not kwargs.get('token'):
            kwargs['token'] = self.generate_token()
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<AiBot(id={self.id}, name='{self.name}', workspace_id={self.workspace_id}, owner_id={self.owner_id})>"

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