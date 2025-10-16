import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import traceback
from datetime import datetime


def get_error_details():
    """Get formatted error details including traceback"""
    exc_info = traceback.format_exc()
    return exc_info


def setup_logger(name, log_file, level=logging.INFO, console=True):
    """Setup a logger with file handler and optionally console handler"""
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"  # 10MB
    )
    file_handler.setFormatter(formatter)

    # Setup logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(file_handler)

    if console:
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def configure_logging():
    """
    Configure logging for the application with separate files for different log levels
    """
    # Create logs directory structure
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Create separate directories for different log types
    error_dir = log_dir / "errors"
    api_dir = log_dir / "api"
    error_dir.mkdir(exist_ok=True)
    api_dir.mkdir(exist_ok=True)

    # Setup main application logger
    main_logger = setup_logger("satya", log_dir / "app.log")

    # Setup error logger with more detailed formatting
    error_logger = setup_logger(
        "satya.error", error_dir / "error.log", level=logging.ERROR
    )

    # Setup API logger (file only, no console)
    api_logger = setup_logger("satya.api", api_dir / "api.log", console=False)
    
    # Setup Debug logger
    debug_logger = setup_logger("app.debug", log_dir / "debug.log", level=logging.DEBUG)

    # Set specific logger levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)

    # Log startup message
    main_logger.info("Logging system initialized")

    return main_logger, error_logger, api_logger, debug_logger


def log_error(error_logger, error, context=None):
    """
    Log an error with full details

    Args:
        error_logger: The error logger instance
        error: The exception object
        context: Additional context about where the error occurred
    """
    error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    error_message = f"""
Time: {error_time}
Error Type: {type(error).__name__}
Error Message: {str(error)}
Context: {context or 'No context provided'}
Traceback:
{get_error_details()}
{'='*80}
"""
    error_logger.error(error_message)
