#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Input Validation and Sanitization
Prevent injection attacks and validate user input
"""

import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from src.utils.logger import setup_logger
else:
    from .logger import setup_logger

logger = setup_logger(__name__)


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


def sanitize_text(text: str, max_length: int = 10000) -> str:
    """
    Sanitize user text input
    
    Args:
        text: Raw user input
        max_length: Maximum allowed length
    
    Returns:
        Sanitized text
    
    Raises:
        ValidationError: If input is invalid
    """
    if not isinstance(text, str):
        raise ValidationError("Input must be a string")
    
    # Strip whitespace
    text = text.strip()
    
    # Check length
    if len(text) == 0:
        raise ValidationError("Input cannot be empty")
    
    if len(text) > max_length:
        raise ValidationError(f"Input too long (max {max_length} characters)")
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Normalize newlines
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    return text




def validate_format_choice(format_choice: str) -> str:
    """
    Validate content format selection
    
    Args:
        format_choice: User-selected format
    
    Returns:
        Validated format
    
    Raises:
        ValidationError: If format is invalid
    """
    valid_formats = [
        'Single Tweet',
        'Thread',
        'Image',
        'Poll'
    ]
    
    # Normalize
    format_choice = format_choice.strip()
    
    # Case-insensitive match
    for valid_format in valid_formats:
        if format_choice.lower() == valid_format.lower():
            return valid_format
    
    raise ValidationError(f"Invalid format. Must be one of: {', '.join(valid_formats)}")



def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal
    
    Args:
        filename: User-provided filename
    
    Returns:
        Safe filename
    
    Raises:
        ValidationError: If filename is invalid
    """
    if not filename:
        raise ValidationError("Filename cannot be empty")
    
    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove dangerous characters
    filename = re.sub(r'[<>:"|?*\x00-\x1f]', '', filename)
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    
    # Check length
    if len(filename) == 0:
        raise ValidationError("Filename invalid after sanitization")
    
    if len(filename) > 255:
        filename = filename[:255]
    
    return filename
