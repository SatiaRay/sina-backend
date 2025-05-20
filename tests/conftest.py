import sys
import os
<<<<<<< HEAD
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
=======

# Add project root to sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
>>>>>>> feature/store-chat-history
