"""
Error handling and logging utilities for the chatbot application.
Provides centralized error management and structured logging.
"""

import logging
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, Optional, Union
from functools import wraps
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('chatbot_errors.log')
    ]
)

logger = logging.getLogger(__name__)


class ChatbotError(Exception):
    """Base exception class for chatbot-specific errors."""
    
    def __init__(self, message: str, error_code: str = "UNKNOWN_ERROR", details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for API responses."""
        return {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "timestamp": datetime.now().isoformat()
        }
    
    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"


class APIError(ChatbotError):
    """Exception for API-related errors."""
    pass


class ValidationError(ChatbotError):
    """Exception for data validation errors."""
    pass


class ConfigurationError(ChatbotError):
    """Exception for configuration errors."""
    pass


class MediaProcessingError(ChatbotError):
    """Exception for media processing errors."""
    pass


class CodeGenerationError(ChatbotError):
    """Exception for code generation errors."""
    pass


def handle_exceptions(func):
    """
    Decorator to handle exceptions and log them appropriately.
    
    Args:
        func: Function to wrap with exception handling
        
    Returns:
        Wrapped function with exception handling
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ChatbotError as e:
            # Log chatbot-specific errors
            logger.error(f"ChatbotError in {func.__name__}: {e}", 
                        extra={"error_code": e.error_code, "details": e.details})
            raise
        except Exception as e:
            # Log unexpected errors
            error_details = {
                "function": func.__name__,
                "args": str(args),
                "kwargs": str(kwargs),
                "traceback": traceback.format_exc()
            }
            logger.critical(f"Unexpected error in {func.__name__}: {str(e)}", 
                          extra=error_details)
            raise ChatbotError(
                message="An unexpected error occurred",
                error_code="INTERNAL_ERROR",
                details={"original_error": str(e)}
            )
    return wrapper


def log_api_call(api_name: str, success: bool = True, duration: Optional[float] = None, 
                 details: Optional[Dict[str, Any]] = None):
    """
    Log API calls with standardized format.
    
    Args:
        api_name: Name of the API being called
        success: Whether the API call was successful
        duration: Duration of the API call in seconds
        details: Additional details about the API call
    """
    log_data = {
        "api": api_name,
        "success": success,
        "timestamp": datetime.now().isoformat()
    }
    
    if duration is not None:
        log_data["duration_seconds"] = round(duration, 3)
    
    if details:
        log_data.update(details)
    
    if success:
        logger.info(f"API call successful: {api_name}", extra=log_data)
    else:
        logger.warning(f"API call failed: {api_name}", extra=log_data)


def setup_logging(log_level: str = "INFO", log_file: str = "chatbot.log") -> logging.Logger:
    """
    Set up application-wide logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        
    Returns:
        Configured logger instance
    """
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(filename)s:%(lineno)d'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Create handlers
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(simple_formatter)
    console_handler.setLevel(getattr(logging, log_level))
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(detailed_formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Prevent duplicate logs
    root_logger.propagate = False
    
    return root_logger


class ErrorReporter:
    """
    Centralized error reporting and monitoring.
    """
    
    def __init__(self, enable_reporting: bool = True):
        """
        Initialize error reporter.
        
        Args:
            enable_reporting: Whether to enable error reporting
        """
        self.enable_reporting = enable_reporting
        self.error_stats = {
            "total_errors": 0,
            "error_types": {},
            "recent_errors": []
        }
    
    def report_error(self, error: Union[Exception, ChatbotError], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Report an error and update statistics.
        
        Args:
            error: The exception that occurred
            context: Additional context about the error
            
        Returns:
            Dictionary with error report
        """
        self.error_stats["total_errors"] += 1
        
        error_type = type(error).__name__
        self.error_stats["error_types"][error_type] = self.error_stats["error_types"].get(error_type, 0) + 1
        
        error_report = {
            "type": error_type,
            "message": str(error),
            "timestamp": datetime.now().isoformat(),
            "context": context or {},
            "traceback": traceback.format_exc() if isinstance(error, Exception) else None
        }
        
        # Keep only last 100 errors
        self.error_stats["recent_errors"].append(error_report)
        if len(self.error_stats["recent_errors"]) > 100:
            self.error_stats["recent_errors"].pop(0)
        
        # Log the error
        if isinstance(error, ChatbotError):
            logger.error(f"Reported ChatbotError: {error}", extra=error_report)
        else:
            logger.error(f"Reported Exception: {error}", extra=error_report)
        
        return error_report
    
    def get_error_stats(self) -> Dict[str, Any]:
        """
        Get error statistics.
        
        Returns:
            Dictionary with error statistics
        """
        return self.error_stats.copy()
    
    def clear_stats(self) -> None:
        """Clear error statistics."""
        self.error_stats = {
            "total_errors": 0,
            "error_types": {},
            "recent_errors": []
        }


def validate_environment_variables(required_vars: list) -> bool:
    """
    Validate that required environment variables are set.
    
    Args:
        required_vars: List of required environment variable names
        
    Returns:
        True if all variables are set, False otherwise
        
    Raises:
        ConfigurationError: If any required variable is missing
    """
    import os
    
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        raise ConfigurationError(
            message=error_msg,
            error_code="MISSING_ENV_VARS",
            details={"missing_variables": missing_vars}
        )
    
    return True


def safe_json_parse(json_string: str, default: Any = None) -> Any:
    """
    Safely parse JSON string with error handling.
    
    Args:
        json_string: JSON string to parse
        default: Default value to return if parsing fails
        
    Returns:
        Parsed JSON object or default value
    """
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse JSON: {str(e)}", extra={"json_string": json_string[:100]})
        return default


def format_error_for_ui(error: Exception) -> Dict[str, Any]:
    """
    Format error for UI display.
    
    Args:
        error: Exception to format
        
    Returns:
        Dictionary with formatted error information
    """
    if isinstance(error, ChatbotError):
        return error.to_dict()
    
    return {
        "error": True,
        "error_code": "UNEXPECTED_ERROR",
        "message": "An unexpected error occurred. Please try again.",
        "details": {"original_error": str(error)},
        "timestamp": datetime.now().isoformat()
    }


# Global error reporter instance
error_reporter = ErrorReporter()


@handle_exceptions
def initialize_error_handling(log_level: str = "INFO") -> None:
    """
    Initialize error handling and logging for the application.
    
    Args:
        log_level: Logging level to use
    """
    setup_logging(log_level)
    logger.info("Error handling and logging initialized")
    
    # Log startup information
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    
    # Set up global exception handler
    def global_exception_handler(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Don't capture keyboard interrupts
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        error_reporter.report_error(exc_value, {"handler": "global_exception_handler"})
        
        # Log the error
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    
    sys.excepthook = global_exception_handler


if __name__ == "__main__":
    # Test the error handling
    try:
        initialize_error_handling()
        
        # Test custom exception
        raise APIError("Test API error", "TEST_ERROR", {"test": True})
        
    except ChatbotError as e:
        print(f"Caught ChatbotError: {e}")
        print(f"Error dict: {e.to_dict()}")