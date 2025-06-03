from ast import List
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey, Boolean, JSON, Enum, TEXT, false
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

# Wizard model
class Wizard(BaseModel):
    __tablename__ = "wizards"
    
    title = Column(String(255), nullable=False)
    context = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey("wizards.id"), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    
    # Relationship for self-referential hierarchy
    parent = relationship(
        "Wizard",
        remote_side=lambda: [Wizard.id],
        backref="children"
    )

# CrawledDomain model
class CrawledDomain(BaseModel):
    __tablename__ = "crawled_domains"
    
    domain = Column(String(255), unique=True, nullable=False)
    documents = relationship("Document", back_populates="domain")
    
class CrawlJobs(BaseModel):
    __tablename__ = "crawl_jobs"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(String(255), unique=True, nullable=False)
    init_url = Column(String(255), nullable=False)
    logs = Column(Text, nullable=True)
    status = Column(JSON, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    end_at = Column(DateTime, default=datetime.utcnow, nullable=True)

# Document model
class Document(BaseModel):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    _html = Column("html", Text(length=4294967295))  # MySQL LONGTEXT
    markdown = Column(Text(length=4294967295), nullable=True)  # MySQL LONGTEXT
    uri = Column(String(255), nullable=True)
    domain_id = Column(Integer, ForeignKey("crawled_domains.id"), nullable=True)
    vector_id = Column(String(255), nullable=True)
    type = Column(Enum('manual', 'crawl'), default="crawl")
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
        
class Chat(BaseModel):
    __tablename__ = 'chats'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(255), unique=True, nullable=False)
    status = Column(String(20), default='active')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chat_history = relationship('ChatHistory', backref='session', lazy=True)

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

class Workflow(BaseModel):
    __tablename__ = 'workflows'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    schema = Column(JSON)
    status = Column(Boolean, default=True)

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