"""
Utility package for the Satya Support Chatbot application.
Contains various helper functions, constants, and configurations.
"""

from .constants import *
from .logging_config import configure_logging

__all__ = [
    'configure_logging',
    'APP_NAME',
    'APP_VERSION',
    'CHROMA_PERSIST_DIRECTORY',
    'COLLECTION_NAME',
    'MAX_DEPTH',
    'ALLOWED_DOMAINS',
    'EXCLUDED_PATHS',
    'MAX_CHUNK_SIZE',
    'CHUNK_OVERLAP',
    'MAX_TOKENS',
    'REQUEST_TIMEOUT',
    'LOGS_DIR',
    'DATA_DIR',
    'CRAWLED_FILES_DIR',
    'DEFAULT_LANGUAGE',
    'SUPPORTED_LANGUAGES'
] 