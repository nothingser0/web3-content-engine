#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared Utilities - Console Encoding and Common Helpers
Centralized utilities to avoid code duplication
"""

import sys
import os
from typing import NoReturn


def setup_console_encoding() -> None:
    """
    Setup Windows console encoding for UTF-8 support
    Call this at the start of every script that outputs Unicode
    """
    if sys.platform == 'win32':
        # Prefer reconfigure to avoid replacing/wrapping streams repeatedly.
        try:
            stdout_reconfigure = getattr(sys.stdout, 'reconfigure', None)
            stderr_reconfigure = getattr(sys.stderr, 'reconfigure', None)

            if not getattr(sys.stdout, 'closed', False) and callable(stdout_reconfigure):
                stdout_reconfigure(encoding='utf-8', errors='replace')
            if not getattr(sys.stderr, 'closed', False) and callable(stderr_reconfigure):
                stderr_reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

        # Set console code page to UTF-8
        os.system('chcp 65001 > nul 2>&1')


def exit_with_error(message: str, code: int = 1) -> NoReturn:
    """
    Print error message and exit
    
    Args:
        message: Error message to display
        code: Exit code (default: 1)
    """
    print(f"\n[ERROR] {message}", file=sys.stderr)
    
    # Only prompt for input when running interactively (not from batch/subprocess)
    if sys.stdin.isatty():
        try:
            input("\nPress Enter to close...")
        except (EOFError, KeyboardInterrupt):
            pass
    
    sys.exit(code)


def print_section(title: str, width: int = 60) -> None:
    """
    Print a formatted section header
    
    Args:
        title: Section title
        width: Total width of the header
    """
    print("\n" + "=" * width)
    print(title.center(width))
    print("=" * width)



def print_info(message: str) -> None:
    """Print info message with formatting"""
    print(f"\nℹ {message}")
