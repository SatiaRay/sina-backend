#!/usr/bin/env python
import os
import sys
import shutil
from datetime import datetime
from typing import Optional
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from database.vector_store import VectorStore
from util.logging_config import configure_logging, log_error
import chromadb
from chromadb.config import Settings

console = Console()

def print_header():
    """Display program header"""
    title = Text("Chatbot Database Management", style="bold magenta")
    console.print(Panel(title, border_style="blue"))

def confirm_action(message: str) -> bool:
    """Get user confirmation for an action"""
    return questionary.confirm(
        message,
        default=False
    ).ask()

def migrate_database() -> None:
    """Migrate database to ensure compatibility"""
    try:
        # Get the current persist directory from VectorStore
        vector_store = VectorStore()
        current_persist_dir = vector_store.persist_directory

        if not os.path.exists(current_persist_dir):
            console.print("No database found to migrate.", style="yellow")
            return

        # Create a backup before migration
        backup_dir = f"data/backup/migration_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(backup_dir, exist_ok=True)

        console.print("Creating backup before migration...", style="yellow")
        for item in os.listdir(current_persist_dir):
            s = os.path.join(current_persist_dir, item)
            d = os.path.join(backup_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)

        console.print("Backup created successfully.", style="green")

        if not confirm_action("Are you sure you want to proceed with database migration? This operation may take some time."):
            console.print("Migration cancelled.", style="yellow")
            return

        # Get all documents from the current database
        console.print("Reading existing documents...", style="yellow")
        try:
            documents = vector_store.get_all_documents()
        except Exception as e:
            console.print(f"Error reading documents: {str(e)}", style="red")
            console.print("Attempting to force migrate...", style="yellow")
            
            # Try to read documents directly from the collection
            try:
                collection = vector_store.collection
                results = collection.get()
                documents = [
                    {
                        'id': doc_id,
                        'text': doc,
                        'metadata': meta
                    }
                    for doc, meta, doc_id in zip(results['documents'], results['metadatas'], results['ids'])
                ]
            except Exception as e2:
                console.print(f"Failed to read documents: {str(e2)}", style="red")
                console.print("Please restore from backup and try again.", style="yellow")
                return

        # Delete the current database
        console.print("Removing old database...", style="yellow")
        try:
            vector_store.delete_all()
        except Exception as e:
            console.print(f"Warning: Could not delete old database: {str(e)}", style="yellow")
            console.print("Attempting to force remove...", style="yellow")
            try:
                # Try to remove the database files directly
                for item in os.listdir(current_persist_dir):
                    item_path = os.path.join(current_persist_dir, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
            except Exception as e2:
                console.print(f"Failed to remove old database: {str(e2)}", style="red")
                console.print("Please restore from backup and try again.", style="yellow")
                return

        # Create a new database with the current ChromaDB version
        console.print("Creating new database...", style="yellow")
        try:
            new_client = chromadb.PersistentClient(
                path=current_persist_dir,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
        except Exception as e:
            console.print(f"Error creating new database: {str(e)}", style="red")
            console.print("Please restore from backup and try again.", style="yellow")
            return

        # Re-add all documents to the new database
        console.print("Migrating documents to new database...", style="yellow")
        try:
            vector_store = VectorStore()
            if documents:
                vector_store.add_documents(documents)
            else:
                console.print("No documents to migrate.", style="yellow")
        except Exception as e:
            console.print(f"Error adding documents to new database: {str(e)}", style="red")
            console.print("Please restore from backup and try again.", style="yellow")
            return

        console.print("Database migration completed successfully!", style="green")
        console.print(f"Backup is available at: {backup_dir}", style="blue")

    except Exception as e:
        console.print(f"Error during database migration: {str(e)}", style="red")
        console.print("You can restore from the backup if needed.", style="yellow")
        console.print(f"Backup location: {backup_dir}", style="blue")

def export_database() -> None:
    """Export database to a specified path"""
    try:
        # Get destination path from user
        export_path = questionary.text(
            "Please enter the destination path for database export:",
            default=f"vector_db_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ).ask()

        if not export_path:
            console.print("Operation cancelled.", style="yellow")
            return

        # Create destination directory if it doesn't exist
        os.makedirs(export_path, exist_ok=True)

        # Get the current persist directory from VectorStore
        vector_store = VectorStore()
        current_persist_dir = vector_store.persist_directory

        # Copy the entire ChromaDB directory to the export location
        if os.path.exists(current_persist_dir):
            # Copy all files and directories from the persist directory
            for item in os.listdir(current_persist_dir):
                s = os.path.join(current_persist_dir, item)
                d = os.path.join(export_path, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
            
            console.print(f"Database successfully exported to {export_path}!", style="green")
        else:
            console.print("No database found to export.", style="yellow")
    except Exception as e:
        console.print(f"Error exporting database: {str(e)}", style="red")

def import_database() -> None:
    """Import database from a specified path"""
    try:
        # Get source path from user
        import_path = questionary.text(
            "Please enter the source path for database import:"
        ).ask()

        if not import_path:
            console.print("Operation cancelled.", style="yellow")
            return

        if not os.path.exists(import_path):
            console.print("The specified path does not exist!", style="red")
            return

        if not confirm_action("Are you sure you want to import the database? This operation may overwrite existing data!"):
            console.print("Operation cancelled.", style="yellow")
            return

        # Get the current persist directory from VectorStore
        vector_store = VectorStore()
        current_persist_dir = vector_store.persist_directory

        # Create the persist directory if it doesn't exist
        os.makedirs(current_persist_dir, exist_ok=True)

        # Copy all files from the import location to the persist directory
        for item in os.listdir(import_path):
            s = os.path.join(import_path, item)
            d = os.path.join(current_persist_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)

        # Reinitialize the VectorStore to load the imported data
        vector_store = VectorStore()
        
        console.print(f"Database successfully imported from {import_path}!", style="green")
    except Exception as e:
        console.print(f"Error importing database: {str(e)}", style="red")

def reset_database() -> None:
    """Delete the entire database"""
    try:
        if not confirm_action("Are you sure you want to delete the entire database? This operation cannot be undone!"):
            console.print("Operation cancelled.", style="yellow")
            return

        vector_store = VectorStore()
        vector_store.delete_all()
        
        # Delete backup files
        backup_dirs = ['data/crawled_data', 'data/plaintext_data']
        for dir_path in backup_dirs:
            if os.path.exists(dir_path):
                for file in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        console.print(f"Backup file deleted: {file_path}", style="yellow")

        console.print("Database successfully deleted!", style="green")
    except Exception as e:
        console.print(f"Error deleting database: {str(e)}", style="red")

def main_menu() -> Optional[str]:
    """Display main menu"""
    choices = [
        "Export Database",
        "Import Database",
        "Migrate Database",
        "Delete Entire Database",
        "Exit"
    ]
    
    return questionary.select(
        "Please select an option:",
        choices=choices
    ).ask()

def main():
    """Main program function"""
    print_header()
    
    while True:
        choice = main_menu()
        
        if choice == "Export Database":
            export_database()
        elif choice == "Import Database":
            import_database()
        elif choice == "Migrate Database":
            migrate_database()
        elif choice == "Delete Entire Database":
            reset_database()
        elif choice == "Exit":
            console.print("Goodbye!", style="cyan")
            sys.exit(0)

if __name__ == "__main__":
    main() 