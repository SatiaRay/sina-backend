#!/usr/bin/env python3
"""
Test runner for user management endpoints
"""

import pytest
import sys
import os
from pathlib import Path

# Add the project root to the path
root_dir = Path(__file__).parent
sys.path.append(str(root_dir))

if __name__ == "__main__":
    # Run the user management tests
    test_path = "tests/api/test_user.py"
    
    print("Running user management tests...")
    print("=" * 50)
    
    # Run pytest with verbose output
    exit_code = pytest.main([
        test_path,
        "-v",
        "--tb=short"
    ])
    
    if exit_code == 0:
        print("\n" + "=" * 50)
        print("✅ All user management tests passed!")
    else:
        print("\n" + "=" * 50)
        print("❌ Some user management tests failed!")
    
    sys.exit(exit_code) 