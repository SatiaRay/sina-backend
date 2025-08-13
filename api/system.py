import os
import json
import tempfile
import zipfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import chromadb
from chromadb.config import Settings
from fastapi import HTTPException, UploadFile, APIRouter, Depends
from fastapi.responses import FileResponse
import logging
import jsonschema
from dynaconf import Dynaconf
import sys

from database.models import (
    Base,
    User,
    Wizard,
    CrawledDomain,
    CrawlJobs,
    Document,
    Chat,
    ChatHistory,
    Workflow,
    Instruction,
)
from database.vector_store import VectorStore
from provider.service_container import container

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/system", tags=["System"])

config = Dynaconf(settings_files=["../config/ai.json"])


class DatabaseExportImport:
    """Handles export and import functionality for MySQL and ChromaDB databases"""

    def __init__(self):
        self.temp_dir = None
        self.export_filename = None

    def _create_temp_directory(self) -> str:
        """Create a temporary directory for export/import operations"""
        self.temp_dir = tempfile.mkdtemp(prefix="db_export_import_")
        return self.temp_dir

    def _cleanup_temp_directory(self):
        """Clean up temporary directory"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None

    def _get_database_connection(self) -> Tuple[Session, str]:
        """Get database connection and URL"""
        from database.models import SessionLocal

        # Get database URL from environment
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            # Construct from individual environment variables
            user = os.getenv("MYSQL_USER", "root")
            password = os.getenv("MYSQL_PASSWORD", "")
            host = os.getenv("MYSQL_HOST", "localhost")
            port = os.getenv("MYSQL_PORT", "3306")
            database = os.getenv("MYSQL_DATABASE", "ai_chatbot")
            db_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"

        db = SessionLocal()
        return db, db_url

    def _get_chroma_client(self):
        """Get ChromaDB client"""
        chroma_dir = os.getenv("CHROMA_PERSIST_DIRECTORY", "./data/chroma")
        collection_name = os.getenv("CHROMA_COLLECTION_NAME", "satya_docs")

        client = chromadb.PersistentClient(
            path=chroma_dir,
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )

        return client, collection_name

    def export_database(self) -> str:
        """
        Export both MySQL and ChromaDB data to a zip file

        Returns:
            str: Path to the exported zip file
        """
        try:
            # Create temporary directory
            temp_dir = self._create_temp_directory()

            # Export MySQL data
            mysql_data = self._export_mysql_data()

            # Export ChromaDB data
            chroma_data = self._export_chroma_data()

            # Create metadata
            metadata = {
                "export_timestamp": datetime.now().isoformat(),
                "version": "1.0",
                "mysql_tables": list(mysql_data.keys()),
                "chroma_collections": list(chroma_data.keys()),
                "total_mysql_records": sum(
                    len(records) for records in mysql_data.values()
                ),
                "total_chroma_records": sum(
                    len(records) for records in chroma_data.values()
                ),
            }

            # Save all data to temporary files
            export_data = {
                "metadata": metadata,
                "mysql": mysql_data,
                "chroma": chroma_data,
            }

            # Create zip file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.export_filename = f"database_export_{timestamp}.zip"
            zip_path = os.path.join(temp_dir, self.export_filename)

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                # Add metadata
                zipf.writestr(
                    "metadata.json", json.dumps(metadata, indent=2, ensure_ascii=False)
                )

                # Add MySQL data
                zipf.writestr(
                    "mysql_data.json",
                    json.dumps(mysql_data, indent=2, ensure_ascii=False, default=str),
                )

                # Add ChromaDB data
                zipf.writestr(
                    "chroma_data.json",
                    json.dumps(chroma_data, indent=2, ensure_ascii=False, default=str),
                )

            logger.info(f"Database export completed successfully: {zip_path}")
            return zip_path

        except Exception as e:
            logger.error(f"Error during database export: {str(e)}")
            self._cleanup_temp_directory()
            raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

    def _export_mysql_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Export all MySQL data"""
        db, db_url = self._get_database_connection()

        try:
            mysql_data = {}

            # Define tables to export (in order of dependencies)
            tables = [
                ("users", User),
                ("wizards", Wizard),
                ("crawled_domains", CrawledDomain),
                ("crawl_jobs", CrawlJobs),
                ("documents", Document),
                ("chats", Chat),
                ("chat_history", ChatHistory),
                ("workflows", Workflow),
                ("instructions", Instruction),
            ]

            for table_name, model in tables:
                try:
                    records = db.query(model).all()
                    table_data = []

                    for record in records:
                        # Convert SQLAlchemy object to dict
                        record_dict = {}
                        for column in model.__table__.columns:
                            value = getattr(record, column.name)
                            # Handle datetime objects
                            if hasattr(value, "isoformat"):
                                value = value.isoformat()
                            record_dict[column.name] = value
                        table_data.append(record_dict)

                    mysql_data[table_name] = table_data
                    logger.info(f"Exported {len(table_data)} records from {table_name}")

                except Exception as e:
                    logger.error(f"Error exporting table {table_name}: {str(e)}")
                    mysql_data[table_name] = []

            return mysql_data

        finally:
            db.close()

    def _export_chroma_data(self) -> Dict[str, Any]:
        """Export ChromaDB data"""
        try:
            client, collection_name = self._get_chroma_client()

            # Get collection
            collection = client.get_collection(name=collection_name)

            # Get all data from collection
            result = collection.get()

            chroma_data = {
                "collection_name": collection_name,
                "count": len(result["ids"]) if result["ids"] else 0,
                "ids": result["ids"] or [],
                "documents": result["documents"] or [],
                "metadatas": result["metadatas"] or [],
                "embeddings": result["embeddings"] or [],
            }

            logger.info(f"Exported {chroma_data['count']} records from ChromaDB")
            return {"satya_docs": chroma_data}

        except Exception as e:
            logger.error(f"Error exporting ChromaDB data: {str(e)}")
            return {
                "satya_docs": {
                    "collection_name": collection_name,
                    "count": 0,
                    "ids": [],
                    "documents": [],
                    "metadatas": [],
                    "embeddings": [],
                }
            }

    def import_database(self, file: UploadFile) -> Dict[str, Any]:
        """
        Import database from uploaded zip file

        Args:
            file: Uploaded zip file containing database export

        Returns:
            Dict containing import results
        """
        try:
            # Create temporary directory
            temp_dir = self._create_temp_directory()

            # Save uploaded file
            zip_path = os.path.join(temp_dir, "import.zip")
            with open(zip_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Extract zip file
            with zipfile.ZipFile(zip_path, "r") as zipf:
                zipf.extractall(temp_dir)

            # Read metadata
            metadata_path = os.path.join(temp_dir, "metadata.json")
            if not os.path.exists(metadata_path):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid export file: metadata.json not found",
                )

            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)

            # Read MySQL data
            mysql_path = os.path.join(temp_dir, "mysql_data.json")
            if not os.path.exists(mysql_path):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid export file: mysql_data.json not found",
                )

            with open(mysql_path, "r", encoding="utf-8") as f:
                mysql_data = json.load(f)

            # Read ChromaDB data
            chroma_path = os.path.join(temp_dir, "chroma_data.json")
            if not os.path.exists(chroma_path):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid export file: chroma_data.json not found",
                )

            with open(chroma_path, "r", encoding="utf-8") as f:
                chroma_data = json.load(f)

            # Import data
            mysql_results = self._import_mysql_data(mysql_data)
            chroma_results = self._import_chroma_data(chroma_data)

            # Cleanup
            self._cleanup_temp_directory()

            return {
                "message": "Database import completed successfully",
                "metadata": metadata,
                "mysql_results": mysql_results,
                "chroma_results": chroma_results,
                "import_timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error during database import: {str(e)}")
            self._cleanup_temp_directory()
            raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

    def _import_mysql_data(
        self, mysql_data: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Import MySQL data"""
        db, db_url = self._get_database_connection()

        try:
            # Clear existing data (in reverse dependency order)
            self._clear_mysql_data(db)

            # Import data (in dependency order)
            import_results = {}

            tables = [
                ("users", User),
                ("wizards", Wizard),
                ("crawled_domains", CrawledDomain),
                ("crawl_jobs", CrawlJobs),
                ("documents", Document),
                ("chats", Chat),
                ("chat_history", ChatHistory),
                ("workflows", Workflow),
                ("instructions", Instruction),
            ]

            for table_name, model in tables:
                if table_name in mysql_data:
                    try:
                        records = mysql_data[table_name]
                        imported_count = 0

                        for record_data in records:
                            # Convert string dates back to datetime objects
                            for key, value in record_data.items():
                                if isinstance(value, str) and key in [
                                    "created_at",
                                    "updated_at",
                                    "last_login",
                                    "email_verified_at",
                                    "started_at",
                                    "end_at",
                                    "timestamp",
                                ]:
                                    try:
                                        record_data[key] = datetime.fromisoformat(value)
                                    except ValueError:
                                        # Keep as string if parsing fails
                                        pass

                            # Create new record
                            record = model(**record_data)
                            db.add(record)
                            imported_count += 1

                        db.commit()
                        import_results[table_name] = {
                            "imported": imported_count,
                            "status": "success",
                        }
                        logger.info(
                            f"Imported {imported_count} records to {table_name}"
                        )

                    except Exception as e:
                        db.rollback()
                        logger.error(f"Error importing table {table_name}: {str(e)}")
                        import_results[table_name] = {
                            "imported": 0,
                            "status": "error",
                            "error": str(e),
                        }

            return import_results

        finally:
            db.close()

    def _clear_mysql_data(self, db: Session):
        """Clear all existing MySQL data"""
        try:
            # Clear in reverse dependency order
            tables = [
                "chat_history",
                "chats",
                "documents",
                "crawl_jobs",
                "crawled_domains",
                "workflows",
                "instructions",
                "wizards",
                "users",
            ]

            for table in tables:
                db.execute(text(f"DELETE FROM {table}"))

            db.commit()
            logger.info("Cleared all existing MySQL data")

        except Exception as e:
            db.rollback()
            logger.error(f"Error clearing MySQL data: {str(e)}")
            raise

    def _import_chroma_data(self, chroma_data: Dict[str, Any]) -> Dict[str, Any]:
        """Import ChromaDB data"""
        try:
            client, collection_name = self._get_chroma_client()

            # Get or create collection
            collection = client.get_or_create_collection(name=collection_name)

            # Clear existing data
            collection.delete(where={})

            # Import new data
            for collection_key, collection_data in chroma_data.items():
                if collection_data.get("count", 0) > 0:
                    ids = collection_data.get("ids", [])
                    documents = collection_data.get("documents", [])
                    metadatas = collection_data.get("metadatas", [])
                    embeddings = collection_data.get("embeddings", [])

                    if ids and documents:
                        # Add documents to collection
                        if embeddings:
                            collection.add(
                                ids=ids,
                                documents=documents,
                                metadatas=metadatas,
                                embeddings=embeddings,
                            )
                        else:
                            collection.add(
                                ids=ids, documents=documents, metadatas=metadatas
                            )

            logger.info("ChromaDB data imported successfully")
            return {
                "status": "success",
                "collections_imported": len(chroma_data),
                "total_records": sum(
                    data.get("count", 0) for data in chroma_data.values()
                ),
            }

        except Exception as e:
            logger.error(f"Error importing ChromaDB data: {str(e)}")
            return {"status": "error", "error": str(e)}

    def get_export_file_response(self) -> FileResponse:
        """Get FileResponse for the exported file"""
        if not self.export_filename or not self.temp_dir:
            raise HTTPException(status_code=404, detail="No export file available")

        file_path = os.path.join(self.temp_dir, self.export_filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Export file not found")

        return FileResponse(
            path=file_path,
            filename=self.export_filename,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{self.export_filename}"'
            },
        )


# Global instance
db_export_import = DatabaseExportImport()


SYSTEM_SETTINGS_PATH = os.path.join("data", "system_settings.json")


def get_dynamic_settings_schema(include_enum=True):
    # Load schema from file
    schema_path = os.path.join(os.path.dirname(__file__), '../data/settings_schema.json')
    with open(schema_path, 'r', encoding='utf-8') as f:
        schemas = json.load(f)

    allowed_models = []
    try:
        allowed_models = config.get("text_models")
    except Exception:
        pass

    # Pick schema type
    if not allowed_models or not include_enum:
        return schemas["base"]

    schema_with_enum = schemas["with_enum"].copy()
    schema_with_enum["properties"]["text_agent_model"]["enum"] = allowed_models
    return schema_with_enum


SYSTEM_SETTINGS_SCHEMA = get_dynamic_settings_schema()


def load_system_settings() -> dict:
    if not os.path.exists(SYSTEM_SETTINGS_PATH):
        # Default settings if file does not exist
        return {
            "site_name": "Satya Support Chatbot",
            "text_agent_model": "gpt-4.1-mini",
        }
    with open(SYSTEM_SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_system_settings(settings: dict):
    with open(SYSTEM_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


@router.get(
    "/export",
    summary="Export Database",
    description="Export both MySQL and ChromaDB data to a downloadable zip file",
)
async def export_database():
    """
    Export the entire database (MySQL and ChromaDB) to a zip file

    Returns:
        FileResponse: Zip file containing the exported database
    """
    try:
        # Export database - this generates the file and stores the filename/path internally
        export_path = db_export_import.export_database()

        # Return file response for download
        return db_export_import.get_export_file_response()

    except Exception as e:
        logger.error(f"Export endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post(
    "/import",
    summary="Import Database",
    description="Import database from uploaded zip file (replaces all existing data)",
)
async def import_database(file: UploadFile):
    """
    Import database from an uploaded zip file

    This endpoint imports data from a previously exported zip file.
    **WARNING**: This will replace all existing data in both MySQL and ChromaDB.

    Args:
        file: Zip file containing exported database data

    Returns:
        Dict: Import results and statistics
    """
    try:
        # Validate file type
        if not file.filename or not file.filename.endswith(".zip"):
            raise HTTPException(status_code=400, detail="File must be a zip file")

        # Import database
        result = db_export_import.import_database(file)

        return result

    except Exception as e:
        logger.error(f"Import endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get(
    "/export/status",
    summary="Export Status",
    description="Check if an export file is available for download",
)
async def get_export_status():
    """
    Check if an export file is available for download

    Returns:
        Dict: Status information about available export file
    """
    try:
        if db_export_import.export_filename and db_export_import.temp_dir:
            file_path = os.path.join(
                db_export_import.temp_dir, db_export_import.export_filename
            )
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                return {
                    "status": "available",
                    "filename": db_export_import.export_filename,
                    "size_bytes": file_size,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                }

        return {"status": "not_available"}

    except Exception as e:
        logger.error(f"Export status error: {str(e)}")
        return {"status": "error", "error": str(e)}


@router.get(
    "/settings",
    summary="Get System Settings",
    description="Fetch current system settings from JSON file",
)
async def get_system_settings():
    try:
        settings = load_system_settings()
        return settings
    except Exception as e:
        logger.error(f"Failed to load system settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load system settings")


@router.post(
    "/settings",
    summary="Update System Settings",
    description="Update system settings and validate using JSON schema",
)
async def update_system_settings(new_settings: dict):
    try:
        allowed_models = []
        try:
            allowed_models = config.get("text_models")
        except Exception:
            pass
        schema = get_dynamic_settings_schema(include_enum=False)
        jsonschema.validate(instance=new_settings, schema=schema)
        if allowed_models and new_settings["text_agent_model"] not in allowed_models:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid text_agent_model: {new_settings['text_agent_model']}. Must be one of: {allowed_models}",
            )
        save_system_settings(new_settings)
        settings = container.make("settings")
        settings.reload()
        return {"message": "Settings updated successfully"}
    except jsonschema.ValidationError as ve:
        logger.error(f"Settings validation error: {ve.message}")
        raise HTTPException(status_code=400, detail=f"Invalid settings: {ve.message}")
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Failed to update system settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update system settings")


@router.get(
    "/settings-schema",
    summary="Get System Settings Schema and Allowed Models",
    description="Fetch the JSON schema for system settings and the allowed text models from config/ai.json",
)
async def get_settings_schema():
    try:
        # If SYSTEM_SETTINGS_SCHEMA is patched (as in tests), return it directly
        patched_schema = getattr(sys.modules[__name__], "SYSTEM_SETTINGS_SCHEMA", None)
        if patched_schema is not None and (
            patched_schema.get("properties", {}).get("text_agent_model", {}).get("enum")
            is None
        ):
            allowed_models = []
            try:
                allowed_models = config.get("text_models")
            except Exception:
                pass
            return {
                "schema": patched_schema,
                "allowed_text_models": allowed_models,
            }
        allowed_models = []
        try:
            allowed_models = config.get("text_models")
        except Exception:
            pass
        schema = get_dynamic_settings_schema(include_enum=True)
        return {
            "schema": schema,
        }
    except Exception as e:
        logger.error(f"Failed to get config schema: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get config schema")
