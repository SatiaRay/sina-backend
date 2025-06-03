from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import DropTable, DropConstraint, MetaData
from sqlalchemy.ext.declarative import declarative_base
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DATABASE')}"

def init_db():
    """Initialize the database by creating all tables"""
    from .models import Base, Document, CrawledDomain, Wizard, Chat, ChatHistory
    
    # Create engine
    engine = create_engine(DATABASE_URL)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

def drop_all_tables():
    """Drop all tables in the database"""
    from .models import Base
    
    # Create engine
    engine = create_engine(DATABASE_URL)
    
    # Drop all tables
    Base.metadata.drop_all(bind=engine)
    print("All tables dropped successfully!")

def reset_db():
    """Reset the database by dropping all tables and recreating them"""
    drop_all_tables()
    init_db()
    print("Database reset successfully!")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Database migration tools')
    parser.add_argument('command', choices=['init', 'drop', 'reset'], 
                       help='Command to execute: init, drop, or reset')
    
    args = parser.parse_args()
    
    if args.command == 'init':
        init_db()
    elif args.command == 'drop':
        drop_all_tables()
    elif args.command == 'reset':
        reset_db() 