#!/usr/bin/env python3
"""
Test runner for system export/import functionality
"""

import sys
import os
import pytest

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def run_system_tests():
    """Run system export/import tests"""
    print("Running System Export/Import Tests...")
    print("=" * 50)
    
    # Test file path
    test_file = "tests/test_system_export_import.py"
    
    # Run tests with verbose output
    result = pytest.main([
        test_file,
        "-v",
        "--tb=short",
        "--strict-markers",
        "--disable-warnings"
    ])
    
    if result == 0:
        print("\n✅ All system tests passed!")
    else:
        print("\n❌ Some system tests failed!")
    
    return result

if __name__ == "__main__":
    exit_code = run_system_tests()
    sys.exit(exit_code)
