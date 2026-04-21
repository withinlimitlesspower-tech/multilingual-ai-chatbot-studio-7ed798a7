"""
Utility functions for the AI chatbot application.
Contains validation, formatting, and common operations.
"""

import re
import json
import logging
import hashlib
import datetime
from typing import Any, Dict, List, Optional, Union, Tuple
from urllib.parse import urlparse
import mimetypes
import os

# Configure logging
logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def validate_api_key(api_key: str, min_length: int = 10) -> bool:
    """
    Validate API key format and length.
    
    Args:
        api_key: The API key to validate
        min_length: Minimum acceptable length for the API key
        
    Returns:
        bool: True if valid, False otherwise
        
    Raises:
        ValidationError: If API key is invalid
    """
    try:
        if not api_key:
            raise ValidationError("API key cannot be empty")
        
        if not isinstance(api_key, str):
            raise ValidationError("API key must be a string")
        
        if len(api_key.strip()) < min_length:
            raise ValidationError(f"API key must be at least {min_length} characters long")
        
        # Check for common invalid patterns
        if api_key.strip().lower() in ["your_api_key_here", "sk-", "test", "demo"]:
            raise ValidationError("API key appears to be a placeholder or test value")
        
        return True
        
    except ValidationError as e:
        logger.warning(f"API key validation failed: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during API key validation: {str(e)}")
        raise ValidationError(f"API key validation failed: {str(e)}")


def validate_url(url: str, allowed_schemes: List[str] = None) -> bool:
    """
    Validate URL format and scheme.
    
    Args:
        url: The URL to validate
        allowed_schemes: List of allowed URL schemes (default: ['http', 'https'])
        
    Returns:
        bool: True if valid, False otherwise
        
    Raises:
        ValidationError: If URL is invalid
    """
    if allowed_schemes is None:
        allowed_schemes = ['http', 'https']
    
    try:
        if not url:
            raise ValidationError("URL cannot be empty")
        
        if not isinstance(url, str):
            raise ValidationError("URL must be a string")
        
        parsed = urlparse(url)
        
        if not parsed.scheme:
            raise ValidationError("URL must include a scheme (http:// or https://)")
        
        if parsed.scheme not in allowed_schemes:
            raise ValidationError(f"URL scheme must be one of: {', '.join(allowed_schemes)}")
        
        if not parsed.netloc:
            raise ValidationError("URL must include a domain name")
        
        return True
        
    except ValidationError as e:
        logger.warning(f"URL validation failed: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during URL validation: {str(e)}")
        raise ValidationError(f"URL validation failed: {str(e)}")


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        str: Sanitized filename
    """
    if not filename:
        return "unnamed_file"
    
    # Remove directory traversal attempts
    filename = os.path.basename(filename)
    
    # Replace invalid characters with underscores
    invalid_chars = '<>:"/\\|?*\'"'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove control characters
    filename = ''.join(char for char in filename if ord(char) >= 32)
    
    # Limit length
    max_length = 255
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        filename = name[:max_length - len(ext)] + ext
    
    return filename.strip('._')


def format_timestamp(timestamp: Optional[datetime.datetime] = None, 
                    format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format timestamp to readable string.
    
    Args:
        timestamp: Datetime object (default: current time)
        format_str: Format string for datetime
        
    Returns:
        str: Formatted timestamp
    """
    if timestamp is None:
        timestamp = datetime.datetime.now()
    
    if not isinstance(timestamp, datetime.datetime):
        try:
            timestamp = datetime.datetime.fromisoformat(str(timestamp))
        except (ValueError, TypeError):
            timestamp = datetime.datetime.now()
    
    return timestamp.strftime(format_str)


def generate_message_id() -> str:
    """
    Generate a unique message ID.
    
    Returns:
        str: Unique message ID
    """
    timestamp = datetime.datetime.now().isoformat()
    random_hash = hashlib.md5(timestamp.encode()).hexdigest()[:8]
    return f"msg_{random_hash}_{int(datetime.datetime.now().timestamp())}"


def parse_language_code(text: str) -> str:
    """
    Detect and parse language code from text.
    
    Args:
        text: Input text to analyze
        
    Returns:
        str: Detected language code (en, ur, hi, etc.)
    """
    if not text or not isinstance(text, str):
        return "en"
    
    text = text.strip().lower()
    
    # Check for Roman English patterns (mix of English with Urdu/Hindi words in Roman script)
    roman_urdu_patterns = [
        r'\b(acha|theek|hai|nahi|kyun|kya|kaise|main|tum|woh|yeh)\b',
        r'\b(jaldi|subah|shaam|raat|din|waqt|dost|ghar|kaam)\b'
    ]
    
    roman_hindi_patterns = [
        r'\b(accha|thik|hai|nahi|kyun|kya|kaise|main|tum|woh|ye)\b',
        r'\b(jaldi|subah|shaam|raat|din|samay|dost|ghar|kaam)\b'
    ]
    
    for pattern in roman_urdu_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return "ur-Latn"  # Urdu in Latin script
    
    for pattern in roman_hindi_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return "hi-Latn"  # Hindi in Latin script
    
    # Simple English detection (could be enhanced with langdetect library)
    english_words = ['the', 'and', 'you', 'that', 'have', 'for', 'with', 'this']
    english_count = sum(1 for word in english_words if word in text.lower().split())
    
    if english_count > 2 or len(text.split()) < 5:
        return "en"
    
    # Default to English
    return "en"


def format_chat_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format chat message for consistent structure.
    
    Args:
        message: Raw message dictionary
        
    Returns:
        Dict[str, Any]: Formatted message
    """
    if not isinstance(message, dict):
        message = {"content": str(message)}
    
    required_fields = ["id", "content", "timestamp", "role"]
    
    # Ensure required fields exist
    if "id" not in message:
        message["id"] = generate_message_id()
    
    if "timestamp" not in message:
        message["timestamp"] = format_timestamp()
    
    if "role" not in message:
        message["role"] = "user"
    
    # Clean content
    if "content" in message:
        message["content"] = str(message["content"]).strip()
    
    # Add metadata if not present
    if "metadata" not in message:
        message["metadata"] = {}
    
    if "language" not in message["metadata"]:
        message["metadata"]["language"] = parse_language_code(message.get("content", ""))
    
    return message


def validate_media_file(file_path: str, allowed_types: List[str] = None) -> Tuple[bool, str]:
    """
    Validate media file type and existence.
    
    Args:
        file_path: Path to the media file
        allowed_types: List of allowed MIME types
        
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if allowed_types is None:
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 
                        'video/mp4', 'video/webm', 'audio/mpeg', 'audio/wav']
    
    if not os.path.exists(file_path):
        return False, f"File does not exist: {file_path}"
    
    if not os.path.isfile(file_path):
        return False, f"Path is not a file: {file_path}"
    
    # Check file size (max 100MB)
    max_size = 100 * 1024 * 1024  # 100MB
    file_size = os.path.getsize(file_path)
    
    if file_size > max_size:
        return False, f"File size ({file_size / (1024*1024):.1f}MB) exceeds maximum ({max_size / (1024*1024)}MB)"
    
    # Check MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    
    if not mime_type:
        return False, "Could not determine file type"
    
    if mime_type not in allowed_types:
        return False, f"File type {mime_type} not allowed. Allowed types: {', '.join(allowed_types)}"
    
    return True, ""


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """
    Truncate text to specified length.
    
    Args:
        text: Input text
        max_length: Maximum length
        suffix: Suffix to add when truncated
        
    Returns:
        str: Truncated text
    """
    if not text or not isinstance(text, str):
        return ""
    
    if len(text) <= max_length:
        return text
    
    # Try to truncate at word boundary
    truncated = text[:max_length - len(suffix)]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.7:  # Only truncate at space if it's not too early
        truncated = truncated[:last_space]
    
    return truncated.strip() + suffix


def extract_code_blocks(text: str) -> List[Dict[str, str]]:
    """
    Extract code blocks from markdown-style text.
    
    Args:
        text: Input text containing code blocks
        
    Returns:
        List[Dict[str, str]]: List of code blocks with language and code
    """
    if not text:
        return []
    
    code_blocks = []
    
    # Pattern for language\ncode\n    pattern = r'(\w*)\n(.*?)\n'
    
    for match in re.finditer(pattern, text, re.DOTALL):
        language = match.group(1) or "text"
        code = match.group(2).strip()