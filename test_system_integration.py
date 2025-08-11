#!/usr/bin/env python3
"""
Integration test script for system export/import functionality
This script demonstrates how to use the export/import endpoints
"""

import requests
import json
import tempfile
import os
from pathlib import Path

def test_system_endpoints():
    """Test the system export/import endpoints"""
    
    # Base URL for the API
    base_url = "http://localhost:8000"
    
    print("Testing System Export/Import Endpoints")
    print("=" * 50)
    
    # Test 1: Check export status (should be not available initially)
    print("\n1. Checking export status...")
    try:
        response = requests.get(f"{base_url}/system/export/status")
        if response.status_code == 200:
            status_data = response.json()
            print(f"   Status: {status_data.get('status', 'unknown')}")
            if status_data.get('status') == 'available':
                print(f"   File: {status_data.get('filename')}")
                print(f"   Size: {status_data.get('size_mb', 0)} MB")
        else:
            print(f"   Error: {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 2: Export database
    print("\n2. Exporting database...")
    try:
        response = requests.post(f"{base_url}/system/export")
        if response.status_code == 200:
            # Save the exported file
            export_filename = f"database_export_test_{int(os.time.time())}.zip"
            with open(export_filename, 'wb') as f:
                f.write(response.content)
            print(f"   Export successful: {export_filename}")
            print(f"   File size: {len(response.content)} bytes")
            
            # Check export status again
            status_response = requests.get(f"{base_url}/system/export/status")
            if status_response.status_code == 200:
                status_data = status_response.json()
                print(f"   Export status: {status_data.get('status')}")
        else:
            print(f"   Export failed: {response.status_code}")
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Export error: {e}")
        return
    
    # Test 3: Import database (this will replace all data!)
    print("\n3. Testing import functionality...")
    print("   WARNING: This will replace all existing data!")
    
    # Ask for confirmation
    confirm = input("   Do you want to proceed with import test? (yes/no): ")
    if confirm.lower() != 'yes':
        print("   Import test skipped.")
        return
    
    try:
        # Import the exported file
        with open(export_filename, 'rb') as f:
            files = {'file': (export_filename, f, 'application/zip')}
            response = requests.post(f"{base_url}/system/import", files=files)
        
        if response.status_code == 200:
            import_data = response.json()
            print(f"   Import successful!")
            print(f"   Message: {import_data.get('message')}")
            
            # Show import results
            mysql_results = import_data.get('mysql_results', {})
            chroma_results = import_data.get('chroma_results', {})
            
            print(f"   MySQL results:")
            for table, result in mysql_results.items():
                print(f"     {table}: {result.get('imported', 0)} records imported")
            
            print(f"   ChromaDB results:")
            print(f"     Status: {chroma_results.get('status')}")
            print(f"     Total records: {chroma_results.get('total_records', 0)}")
        else:
            print(f"   Import failed: {response.status_code}")
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Import error: {e}")
    
    # Cleanup
    if os.path.exists(export_filename):
        os.remove(export_filename)
        print(f"\n   Cleaned up: {export_filename}")

def test_invalid_import():
    """Test import with invalid file"""
    print("\n4. Testing invalid file import...")
    
    base_url = "http://localhost:8000"
    
    # Create a temporary invalid file
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp_file:
        tmp_file.write(b"This is not a valid export file")
        tmp_file.flush()
        
        try:
            with open(tmp_file.name, 'rb') as f:
                files = {'file': ('invalid.txt', f, 'text/plain')}
                response = requests.post(f"{base_url}/system/import", files=files)
            
            if response.status_code == 400:
                print("   ✓ Correctly rejected invalid file")
            else:
                print(f"   Unexpected response: {response.status_code}")
                print(f"   Response: {response.text}")
        except Exception as e:
            print(f"   Error: {e}")
        finally:
            os.unlink(tmp_file.name)

if __name__ == "__main__":
    print("System Export/Import Integration Test")
    print("Make sure the FastAPI server is running on localhost:8000")
    print("=" * 60)
    
    # Test basic functionality
    test_system_endpoints()
    
    # Test error handling
    test_invalid_import()
    
    print("\n" + "=" * 60)
    print("Integration test completed!")
