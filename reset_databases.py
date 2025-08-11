#!/usr/bin/env python3
"""
Database Reset Script for AI Chatbot
This script resets both MySQL and ChromaDB databases to a clean state.
"""

import os
import sys
import shutil
import subprocess
import pymysql
from pymysql import Error
import chromadb
from chromadb.config import Settings
import argparse
from typing import Optional
import time
from dotenv import load_dotenv

load_dotenv()


# Database configuration
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_HOST'),
    'user': os.getenv('MYSQL_USER'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DATABASE'),
    'port': int(os.getenv('MYSQL_PORT', 3306))
}

CHROMA_CONFIG = {
    'persist_directory': os.getenv('CHROMA_PERSIST_DIRECTORY', './data/chroma'),
    'collection_name': os.getenv('CHROMA_COLLECTION_NAME', 'satya_docs')
}

class DatabaseResetter:
    def __init__(self, force: bool = False, skip_confirmation: bool = False):
        self.force = force
        self.skip_confirmation = skip_confirmation
        
    def print_banner(self):
        """Print a banner for the reset operation"""
        print("=" * 60)
        print("           DATABASE RESET SCRIPT")
        print("=" * 60)
        print("This script will reset both MySQL and ChromaDB databases.")
        print("⚠️  WARNING: This will DELETE ALL DATA!")
        print("=" * 60)
        
    def confirm_reset(self) -> bool:
        """Ask for user confirmation before proceeding"""
        if self.skip_confirmation:
            return True
            
        print("\n⚠️  WARNING: This operation will DELETE ALL DATA from:")
        print(f"   - MySQL Database: {MYSQL_CONFIG['database']}")
        print(f"   - ChromaDB Collection: {CHROMA_CONFIG['collection_name']}")
        print(f"   - ChromaDB Directory: {CHROMA_CONFIG['persist_directory']}")
        
        response = input("\nAre you sure you want to proceed? (yes/no): ").lower().strip()
        return response in ['yes', 'y']
    
    def test_mysql_connection(self) -> bool:
        """Test MySQL connection"""
        try:
            print("🔍 Testing MySQL connection...")
            connection = pymysql.connect(
                host=MYSQL_CONFIG['host'],
                user=MYSQL_CONFIG['user'],
                password=MYSQL_CONFIG['password'],
                port=MYSQL_CONFIG['port']
            )
            connection.close()
            print("✅ MySQL connection successful")
            return True
        except Error as e:
            print(f"❌ MySQL connection failed: {e}")
            return False
    
    def reset_mysql(self) -> bool:
        """Reset MySQL database by dropping and recreating it"""
        try:
            print("\n🗄️  Resetting MySQL database...")
            
            # Connect to MySQL server (without specifying database)
            connection = pymysql.connect(
                host=MYSQL_CONFIG['host'],
                user=MYSQL_CONFIG['user'],
                password=MYSQL_CONFIG['password'],
                port=MYSQL_CONFIG['port']
            )
            
            cursor = connection.cursor()
            
            # Drop database if exists
            print(f"   Dropping database '{MYSQL_CONFIG['database']}'...")
            cursor.execute(f"DROP DATABASE IF EXISTS `{MYSQL_CONFIG['database']}`")
            
            # Create database
            print(f"   Creating database '{MYSQL_CONFIG['database']}'...")
            cursor.execute(f"CREATE DATABASE `{MYSQL_CONFIG['database']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            
            # Use the database
            cursor.execute(f"USE `{MYSQL_CONFIG['database']}`")
            
            cursor.close()
            connection.close()
            
            print("✅ MySQL database reset successful")
            return True
            
        except Error as e:
            print(f"❌ MySQL reset failed: {e}")
            return False
    
    def reset_chromadb(self) -> bool:
        """Reset ChromaDB by deleting the persist directory and recreating collection"""
        try:
            print("\n🔍 Resetting ChromaDB...")
            
            # Delete persist directory if it exists
            if os.path.exists(CHROMA_CONFIG['persist_directory']):
                print(f"   Deleting ChromaDB directory: {CHROMA_CONFIG['persist_directory']}")
                shutil.rmtree(CHROMA_CONFIG['persist_directory'])
            
            # Create fresh directory
            os.makedirs(CHROMA_CONFIG['persist_directory'], exist_ok=True)
            
            # Initialize ChromaDB client
            print("   Initializing ChromaDB client...")
            client = chromadb.PersistentClient(
                path=CHROMA_CONFIG['persist_directory'],
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Create fresh collection
            print(f"   Creating collection: {CHROMA_CONFIG['collection_name']}")
            collection = client.create_collection(
                name=CHROMA_CONFIG['collection_name'],
                metadata={"hnsw:space": "cosine"}
            )
            
            print("✅ ChromaDB reset successful")
            return True
            
        except Exception as e:
            print(f"❌ ChromaDB reset failed: {e}")
            return False
    
    def run_alembic_migrations(self) -> bool:
        """Run Alembic migrations to set up database schema"""
        try:
            print("\n🔄 Running Alembic migrations...")
            
            # Set environment variables for Alembic
            env = os.environ.copy()
            env.update({
                'MYSQL_HOST': MYSQL_CONFIG['host'],
                'MYSQL_USER': MYSQL_CONFIG['user'],
                'MYSQL_PASSWORD': MYSQL_CONFIG['password'],
                'MYSQL_DATABASE': MYSQL_CONFIG['database'],
                'MYSQL_PORT': str(MYSQL_CONFIG['port'])
            })
            
            # Run alembic upgrade head
            result = subprocess.run(
                ['alembic', 'upgrade', 'head'],
                env=env,
                capture_output=True,
                text=True,
                cwd=os.getcwd()
            )
            
            if result.returncode == 0:
                print("✅ Alembic migrations completed successfully")
                return True
            else:
                print(f"❌ Alembic migrations failed:")
                print(f"   STDOUT: {result.stdout}")
                print(f"   STDERR: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to run Alembic migrations: {e}")
            return False
    
    def reset_docker_volumes(self) -> bool:
        """Reset Docker volumes if running in Docker environment"""
        try:
            print("\n🐳 Checking Docker environment...")
            
            # Check if we're in a Docker environment
            if os.path.exists('/.dockerenv'):
                print("   Running in Docker container")
                return True
            
            # Check if docker-compose is available and has volumes
            if os.path.exists('docker-compose.yml'):
                print("   Found docker-compose.yml, checking for volumes...")
                
                # List volumes
                result = subprocess.run(
                    ['docker-compose', 'down', '-v'],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print("✅ Docker volumes removed")
                    
                    # Start services again
                    print("   Starting Docker services...")
                    start_result = subprocess.run(
                        ['docker-compose', 'up', '-d'],
                        capture_output=True,
                        text=True
                    )
                    
                    if start_result.returncode == 0:
                        print("✅ Docker services restarted")
                        # Wait for services to be ready
                        time.sleep(10)
                        return True
                    else:
                        print(f"❌ Failed to start Docker services: {start_result.stderr}")
                        return False
                else:
                    print(f"❌ Failed to remove Docker volumes: {result.stderr}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Docker volume reset failed: {e}")
            return False
    
    def run(self) -> bool:
        """Run the complete database reset process"""
        self.print_banner()
        
        if not self.confirm_reset():
            print("❌ Reset cancelled by user")
            return False
        
        print("\n🚀 Starting database reset process...")
        
        # Test MySQL connection first
        if not self.test_mysql_connection():
            print("❌ Cannot proceed without MySQL connection")
            return False
        
        # Reset Docker volumes if applicable
        if not self.reset_docker_volumes():
            print("⚠️  Docker volume reset failed, continuing with direct reset...")
        
        # Reset MySQL
        if not self.reset_mysql():
            print("❌ MySQL reset failed")
            return False
        
        # Reset ChromaDB
        if not self.reset_chromadb():
            print("❌ ChromaDB reset failed")
            return False
        
        # Run migrations
        if not self.run_alembic_migrations():
            print("❌ Alembic migrations failed")
            return False
        
        print("\n" + "=" * 60)
        print("✅ DATABASE RESET COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("Both MySQL and ChromaDB have been reset to a clean state.")
        print("The application is ready to use with fresh databases.")
        print("=" * 60)
        
        return True

def main():
    """Main function to handle command line arguments and run the reset"""
    parser = argparse.ArgumentParser(
        description="Reset MySQL and ChromaDB databases for AI Chatbot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python reset_databases.py                    # Interactive mode
  python reset_databases.py --force           # Force reset without confirmation
  python reset_databases.py --skip-confirm    # Skip confirmation prompt
        """
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force reset without any prompts (use with caution)'
    )
    
    parser.add_argument(
        '--skip-confirm',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    parser.add_argument(
        '--mysql-only',
        action='store_true',
        help='Reset only MySQL database'
    )
    
    parser.add_argument(
        '--chroma-only',
        action='store_true',
        help='Reset only ChromaDB'
    )
    
    args = parser.parse_args()
    
    # Create resetter instance
    resetter = DatabaseResetter(
        force=args.force,
        skip_confirmation=args.skip_confirm
    )
    
    # Run the reset
    success = resetter.run()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
