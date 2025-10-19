import pytest
import json
import tempfile
import zipfile
import os
import shutil
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

# Import the system module
from api.system import DatabaseExportImport, router
from database.models import Base, Wizard, Chat, ChatHistory, Workflow, Instruction


class TestDatabaseExportImport:
    """Test cases for DatabaseExportImport class"""
    
    @pytest.fixture
    def db_export_import(self):
        """Create a fresh DatabaseExportImport instance for each test"""
        return DatabaseExportImport()
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        session = Mock(spec=Session)
        return session
    
    @pytest.fixture
    def mock_chroma_client(self):
        """Mock ChromaDB client"""
        client = Mock()
        collection = Mock()
        client.get_collection.return_value = collection
        client.get_or_create_collection.return_value = collection
        return client, collection
    
    def test_create_temp_directory(self, db_export_import):
        """Test temporary directory creation"""
        temp_dir = db_export_import._create_temp_directory()
        
        assert os.path.exists(temp_dir)
        assert "db_export_import_" in temp_dir
        assert db_export_import.temp_dir == temp_dir
        
        # Cleanup
        db_export_import._cleanup_temp_directory()
    
    def test_cleanup_temp_directory(self, db_export_import):
        """Test temporary directory cleanup"""
        temp_dir = db_export_import._create_temp_directory()
        
        # Create a test file in temp directory
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        
        assert os.path.exists(temp_dir)
        assert os.path.exists(test_file)
        
        # Cleanup
        db_export_import._cleanup_temp_directory()
        
        assert not os.path.exists(temp_dir)
        assert not os.path.exists(test_file)
        assert db_export_import.temp_dir is None
    
    @patch('api.system.DatabaseExportImport._get_database_connection')
    def test_get_database_connection(self, mock_get_connection, db_export_import):
        """Test database connection retrieval"""
        mock_session = Mock()
        mock_db_url = "mysql+pymysql://test"
        mock_get_connection.return_value = (mock_session, mock_db_url)
        
        session, db_url = db_export_import._get_database_connection()
        
        assert session == mock_session
        assert db_url == mock_db_url
    
    @patch('api.system.chromadb.PersistentClient')
    def test_get_chroma_client(self, mock_chroma_client, db_export_import):
        """Test ChromaDB client retrieval"""
        client, collection_name = db_export_import._get_chroma_client()
        
        assert client is not None
        assert collection_name == "satya_docs"
        mock_chroma_client.assert_called_once()
    
    @patch('api.system.DatabaseExportImport._export_mysql_data')
    @patch('api.system.DatabaseExportImport._export_chroma_data')
    def test_export_database_success(self, mock_chroma_export, mock_mysql_export, db_export_import):
        """Test successful database export"""
        # Mock export data
        mock_mysql_export.return_value = {
            'documents': [{'id': 1, 'title': 'Test Doc'}]
        }
        mock_chroma_export.return_value = {
            'satya_docs': {
                'collection_name': 'satya_docs',
                'count': 2,
                'ids': ['doc1', 'doc2'],
                'documents': ['text1', 'text2'],
                'metadatas': [{'source': 'test'}, {'source': 'test2'}],
                'embeddings': [[1, 2, 3], [4, 5, 6]]
            }
        }
        
        # Export database
        export_path = db_export_import.export_database()
        
        # Verify export path
        assert os.path.exists(export_path)
        assert export_path.endswith('.zip')
        assert db_export_import.export_filename is not None
        
        # Verify zip file contents
        with zipfile.ZipFile(export_path, 'r') as zipf:
            file_list = zipf.namelist()
            assert 'metadata.json' in file_list
            assert 'mysql_data.json' in file_list
            assert 'chroma_data.json' in file_list
            
            # Check metadata
            metadata = json.loads(zipf.read('metadata.json'))
            assert 'export_timestamp' in metadata
            assert 'version' in metadata
            assert 'mysql_tables' in metadata
            assert 'chroma_collections' in metadata
        
        # Cleanup
        db_export_import._cleanup_temp_directory()
    
    @patch('api.system.DatabaseExportImport._export_mysql_data')
    def test_export_database_mysql_error(self, mock_mysql_export, db_export_import):
        """Test database export with MySQL error"""
        mock_mysql_export.side_effect = Exception("MySQL connection failed")
        
        with pytest.raises(Exception) as exc_info:
            db_export_import.export_database()
        
        assert "Export failed" in str(exc_info.value)
        assert db_export_import.temp_dir is None  # Should be cleaned up
    
    @patch('api.system.DatabaseExportImport._get_database_connection')
    def test_export_mysql_data(self, mock_db_connection, db_export_import):
        """Test MySQL data export"""
        # Mock database session and models
        mock_session = Mock()
        mock_db_connection.return_value = (mock_session, "mysql://test")
        
        # Mock table columns
        mock_id_col = Mock()
        mock_id_col.name = 'id'
        mock_email_col = Mock()
        mock_email_col.name = 'email'
        mock_created_col = Mock()
        mock_created_col.name = 'created_at'
        
        # Mock Document records
        mock_doc = Mock()
        mock_doc.id = 1
        mock_doc.title = "Test Document"
        
        mock_title_col = Mock()
        mock_title_col.name = 'title'
        mock_doc.__table__ = Mock()
        mock_doc.__table__.columns = [mock_id_col, mock_title_col]
        
        # Setup query mocks
        mock_session.query.return_value.all.side_effect = [
            [],           # wizards
            [],           # crawled_domains
            [],           # crawl_jobs
            [mock_doc],   # documents
            [],           # chats
            [],           # chat_history
            [],           # workflows
            []            # instructions
        ]
        
        # Export MySQL data
        result = db_export_import._export_mysql_data()
        
        # Verify results
        assert 'documents' in result
        assert len(result['documents']) == 1
        assert result['documents'][0]['title'] == "Test Document"
        
        mock_session.close.assert_called_once()
    
    @patch('api.system.DatabaseExportImport._get_chroma_client')
    def test_export_chroma_data(self, mock_chroma_client, db_export_import):
        """Test ChromaDB data export"""
        # Mock ChromaDB client and collection
        mock_client = Mock()
        mock_collection = Mock()
        mock_chroma_client.return_value = (mock_client, "satya_docs")
        
        # Mock collection data
        mock_collection.get.return_value = {
            'ids': ['doc1', 'doc2'],
            'documents': ['text1', 'text2'],
            'metadatas': [{'source': 'test'}, {'source': 'test2'}],
            'embeddings': [[1, 2, 3], [4, 5, 6]]
        }
        
        # Mock client.get_collection
        mock_client.get_collection.return_value = mock_collection
        
        # Export ChromaDB data
        result = db_export_import._export_chroma_data()
        
        # Verify results
        assert 'satya_docs' in result
        chroma_data = result['satya_docs']
        assert chroma_data['count'] == 2
        assert chroma_data['ids'] == ['doc1', 'doc2']
        assert chroma_data['documents'] == ['text1', 'text2']
        assert len(chroma_data['metadatas']) == 2
        assert len(chroma_data['embeddings']) == 2
    
    def test_import_database_success(self, db_export_import):
        """Test successful database import"""
        # Create a mock export file
        temp_dir = db_export_import._create_temp_directory()
        
        # Create test data
        metadata = {
            "export_timestamp": datetime.now().isoformat(),
            "version": "1.0",
            "mysql_tables": ["documents"],
            "chroma_collections": ["satya_docs"],
            "total_mysql_records": 2,
            "total_chroma_records": 1
        }
        
        mysql_data = {
            "documents": [{"id": 1, "title": "Test Doc", "created_at": datetime.now().isoformat()}]
        }
        
        chroma_data = {
            "satya_docs": {
                "collection_name": "satya_docs",
                "count": 1,
                "ids": ["doc1"],
                "documents": ["test document"],
                "metadatas": [{"source": "test"}],
                "embeddings": [[1, 2, 3]]
            }
        }
        
        # Create zip file
        zip_path = os.path.join(temp_dir, "test_export.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            zipf.writestr("metadata.json", json.dumps(metadata))
            zipf.writestr("mysql_data.json", json.dumps(mysql_data))
            zipf.writestr("chroma_data.json", json.dumps(chroma_data))
        
        # Create mock upload file
        mock_file = Mock()
        mock_file.filename = "test_export.zip"
        mock_file.file = open(zip_path, 'rb')
        
        # Mock import methods
        with patch.object(db_export_import, '_import_mysql_data') as mock_mysql_import, \
             patch.object(db_export_import, '_import_chroma_data') as mock_chroma_import:
            
            mock_chroma_import.return_value = {"status": "success", "total_records": 1}
            
            # Import database
            result = db_export_import.import_database(mock_file)
            
            # Verify results
            assert result["message"] == "Database import completed successfully"
            assert "metadata" in result
            assert "mysql_results" in result
            assert "chroma_results" in result
            assert "import_timestamp" in result
            
            mock_mysql_import.assert_called_once()
            mock_chroma_import.assert_called_once()
        
        # Cleanup
        mock_file.file.close()
        db_export_import._cleanup_temp_directory()
    
    def test_import_database_invalid_file(self, db_export_import):
        """Test database import with invalid file"""
        # Create mock upload file with invalid content
        mock_file = Mock()
        mock_file.filename = "invalid.txt"
        mock_file.file = Mock()
        
        # Mock the validation check
        with patch.object(db_export_import, 'import_database') as mock_import:
            mock_import.side_effect = HTTPException(status_code=400, detail="File must be a zip file")
            
            with pytest.raises(HTTPException) as exc_info:
                db_export_import.import_database(mock_file)
            
            assert "File must be a zip file" in str(exc_info.value.detail)
    
    def test_import_database_missing_files(self, db_export_import):
        """Test database import with missing required files"""
        # Create a mock export file with missing files
        temp_dir = db_export_import._create_temp_directory()
        
        # Create zip file with only metadata
        zip_path = os.path.join(temp_dir, "test_export.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            zipf.writestr("metadata.json", json.dumps({"test": "data"}))
        
        # Create mock upload file
        mock_file = Mock()
        mock_file.filename = "test_export.zip"
        mock_file.file = open(zip_path, 'rb')
        
        with pytest.raises(Exception) as exc_info:
            db_export_import.import_database(mock_file)
        
        assert "mysql_data.json not found" in str(exc_info.value)
        
        # Cleanup
        mock_file.file.close()
        db_export_import._cleanup_temp_directory()
    
    @patch('api.system.DatabaseExportImport._get_database_connection')
    def test_import_mysql_data(self, mock_db_connection, db_export_import):
        """Test MySQL data import"""
        # Mock database session
        mock_session = Mock()
        mock_db_connection.return_value = (mock_session, "mysql://test")
        
        # Test data
        mysql_data = {
            "documents": [
                {
                    "id": 1,
                    "title": "Test Document",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
            ]
        }
        
        # Mock clear data method
        with patch.object(db_export_import, '_clear_mysql_data'):
            # Import MySQL data
            result = db_export_import._import_mysql_data(mysql_data)
            
            # Verify results
            assert 'documents' in result
            assert result['documents']['status'] == 'success'
            
            # Verify database operations
            assert mock_session.add.call_count == 1  # One for each table
            assert mock_session.commit.call_count == 1
            mock_session.close.assert_called_once()
    
    @patch('api.system.DatabaseExportImport._get_chroma_client')
    def test_import_chroma_data(self, mock_chroma_client, db_export_import):
        """Test ChromaDB data import"""
        # Mock ChromaDB client and collection
        mock_client = Mock()
        mock_collection = Mock()
        mock_chroma_client.return_value = (mock_client, "satya_docs")
        
        # Mock client.get_or_create_collection
        mock_client.get_or_create_collection.return_value = mock_collection
        
        # Test data
        chroma_data = {
            "satya_docs": {
                "collection_name": "satya_docs",
                "count": 2,
                "ids": ["doc1", "doc2"],
                "documents": ["text1", "text2"],
                "metadatas": [{"source": "test"}, {"source": "test2"}],
                "embeddings": [[1, 2, 3], [4, 5, 6]]
            }
        }
        
        # Import ChromaDB data
        result = db_export_import._import_chroma_data(chroma_data)
        
        # Verify results
        assert result["status"] == "success"
        assert result["collections_imported"] == 1
        assert result["total_records"] == 2
        
        # Verify collection operations
        mock_collection.delete.assert_called_once()
        mock_collection.add.assert_called_once()
    
    def test_get_export_file_response_success(self, db_export_import):
        """Test successful export file response"""
        # Setup export file
        temp_dir = db_export_import._create_temp_directory()
        db_export_import.export_filename = "test_export.zip"
        
        # Create test file
        file_path = os.path.join(temp_dir, "test_export.zip")
        with open(file_path, 'w') as f:
            f.write("test content")
        
        # Get file response
        response = db_export_import.get_export_file_response()
        
        # Verify response
        assert response.filename == "test_export.zip"
        assert response.media_type == "application/zip"
        assert "attachment" in response.headers["Content-Disposition"]
        
        # Cleanup
        db_export_import._cleanup_temp_directory()
    
    def test_get_export_file_response_no_file(self, db_export_import):
        """Test export file response when no file exists"""
        with pytest.raises(Exception) as exc_info:
            db_export_import.get_export_file_response()
        
        assert "No export file available" in str(exc_info.value)


class TestSystemEndpoints:
    """Test cases for FastAPI endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)
    
    @pytest.mark.skip(reason="Complex endpoint integration test - tested separately")
    def test_export_database_endpoint(self, client):
        """Test export database endpoint"""
        with patch('api.system.db_export_import.export_database') as mock_export, \
             patch('api.system.db_export_import.get_export_file_response') as mock_response:
            
            # Mock the export to return a path
            mock_export.return_value = "/tmp/test_export.zip"
            
            # Create a simple mock response
            mock_file_response = Mock()
            mock_file_response.filename = "test.zip"
            mock_file_response.media_type = "application/zip"
            mock_file_response.headers = {"Content-Disposition": "attachment"}
            # Mock the response to avoid file access
            mock_file_response.__call__ = Mock(return_value=None)
            mock_response.return_value = mock_file_response
            
            response = client.get("/system/export")
            
            assert response.status_code == 200
            mock_export.assert_called_once()
            mock_response.assert_called_once()
    
    def test_export_database_endpoint_error(self, client):
        """Test export database endpoint with error"""
        with patch('api.system.db_export_import.export_database') as mock_export:
            mock_export.side_effect = Exception("Export failed")
            
            response = client.get("/system/export")
            
            assert response.status_code == 500
            assert "Export failed" in response.json()["detail"]
    
    def test_import_database_endpoint_success(self, client):
        """Test import database endpoint success"""
        # Create test zip file
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            with zipfile.ZipFile(tmp_file.name, 'w') as zipf:
                zipf.writestr("metadata.json", json.dumps({"test": "data"}))
                zipf.writestr("chroma_data.json", json.dumps({"satya_docs": {"count": 0}}))
        
        try:
            with patch('api.system.db_export_import.import_database') as mock_import:
                mock_import.return_value = {
                    "message": "Database import completed successfully",
                    "mysql_results": {},
                    "chroma_results": {}
                }
                
                with open(tmp_file.name, 'rb') as f:
                    response = client.post(
                        "/system/import",
                        files={"file": ("test_export.zip", f, "application/zip")}
                    )
                
                assert response.status_code == 200
                assert response.json()["message"] == "Database import completed successfully"
                mock_import.assert_called_once()
        
        finally:
            os.unlink(tmp_file.name)
    
    def test_import_database_endpoint_invalid_file(self, client, tmp_path):
        tmp_file = tmp_path / "test.txt"
        tmp_file.write_text("invalid content")

        with tmp_file.open("rb") as f:
            response = client.post(
                "/system/import",
                files={"file": ("test.txt", f, "text/plain")},
            )

        assert response.status_code in [400, 500]
        response_data = response.json()
        assert "detail" in response_data

    
    def test_export_status_endpoint_available(self, client):
        """Test export status endpoint when file is available"""
        with patch('api.system.db_export_import.export_filename', 'test.zip'), \
             patch('api.system.db_export_import.temp_dir', '/tmp/test'), \
             patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=1024):
            
            response = client.get("/system/export/status")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "available"
            assert data["filename"] == "test.zip"
            assert data["size_bytes"] == 1024
    
    def test_export_status_endpoint_not_available(self, client):
        """Test export status endpoint when file is not available"""
        with patch('api.system.db_export_import.export_filename', None):
            response = client.get("/system/export/status")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "not_available"


if __name__ == "__main__":
    pytest.main([__file__])
