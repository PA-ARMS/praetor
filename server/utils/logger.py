"""
Logging Utility - Centralized Logging Configuration

This module provides a consistent logging setup across the entire application.
All modules should use this utility instead of Python's basic logging to ensure
consistent formatting and log levels.

Usage:
    from server.utils.logger import setup_logger
    logger = setup_logger("module_name")
    logger.info("This is an info message")
    logger.error("This is an error message")
"""
import logging
import sys
from pathlib import Path
from server.config import settings


def setup_logger(name: str = "lawfirm_ai") -> logging.Logger:
    """
    Create and configure a logger instance for a specific module
    
    Args:
        name: Logger name (typically the module name, e.g., "rag", "chat")
              This appears in log output to identify where the log came from
    
    Returns:
        Configured Logger instance ready to use
    
    Features:
        - Log level controlled by settings.DEBUG (DEBUG if True, INFO if False)
        - Outputs to console (stdout) with formatted timestamps
        - Prevents duplicate handlers if called multiple times
        - Prevents propagation to root logger (avoids duplicate logs)
    """
    # Get or create logger with the specified name
    logger = logging.getLogger(name)
    
    # Set log level based on DEBUG setting from config
    # DEBUG mode: Shows all logs (DEBUG, INFO, WARNING, ERROR)
    # Production mode: Shows INFO and above (INFO, WARNING, ERROR)
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    logger.setLevel(log_level)
    
    # Prevent duplicate handlers - if logger already has handlers, return it
    # This happens if setup_logger is called multiple times for the same name
    if logger.handlers:
        return logger
    
    # Create console handler - outputs logs to stdout (terminal/console)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Create formatter - defines how log messages are displayed
    # Format: "2025-11-18 13:00:00 - module_name - INFO - Message text"
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # Attach handler to logger
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    # Without this, logs would also go to the root logger, causing duplicates
    logger.propagate = False
    
    return logger


# Create default logger instance for this module
# This can be used if the module itself needs to log something
logger = setup_logger("lawfirm_ai")

