"""
Constants used throughout the application
"""

# Application Information
APP_NAME = "Satya Support Chatbot"
APP_VERSION = "1.0.0"

# Database Constants
CHROMA_PERSIST_DIRECTORY = "chroma_db"
COLLECTION_NAME = "knowledge_base"

# Crawler Constants
MAX_DEPTH = 3
ALLOWED_DOMAINS = ["satia.co"]
EXCLUDED_PATHS = ["/admin", "/login", "/register"]

# Text Processing
MAX_CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# API Limits
MAX_TOKENS = 4096
REQUEST_TIMEOUT = 30  # seconds

# File Paths
LOGS_DIR = "logs"
DATA_DIR = "data"
CRAWLED_FILES_DIR = "data/crawled"

# Language Settings
DEFAULT_LANGUAGE = "fa"
SUPPORTED_LANGUAGES = ["fa", "en"] 