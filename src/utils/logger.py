#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Centralized Logging Configuration
Structured logging for the entire pipeline
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

# Create logs directory if not exists
LOGS_DIR = Path(__file__).resolve().parent.parent.parent / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# Log file with timestamp
LOG_FILE = LOGS_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log"


class ColoredFormatter(logging.Formatter):
    """Colored console output for better readability"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        if sys.platform == 'win32':
            # Windows console might not support colors
            return super().format(record)
        
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Setup logger with console and file handlers
    
    Args:
        name: Logger name (usually __name__)
        level: Logging level (default: INFO)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_formatter = ColoredFormatter(
        '[%(levelname)s] %(name)s: %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # File handler with detailed format
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)  # Log everything to file
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger


# Default logger for quick imports
default_logger = setup_logger('pipeline')
