#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Centralized Prompt Loading Module

Provides a singleton PromptLoader class for loading AI prompts from the prompts/ directory
with caching and consistent error handling.

Usage:
    from src.prompt_loader import PromptLoader
    
    loader = PromptLoader()
    content = loader.load("strategist/strategist_surabaya_human.txt")
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional


class PromptLoader:
    """Singleton prompt loader with caching.
    
    Provides centralized loading of prompt files from the prompts/ directory
    with automatic caching for performance.
    
    Examples:
        >>> loader = PromptLoader()
        >>> content = loader.load("strategist/strategist_surabaya_human.txt")
        >>> print(len(content))
        26133
    """
    
    _instance: Optional['PromptLoader'] = None
    _prompt_dir: Path = Path()
    
    def __new__(cls) -> 'PromptLoader':
        """Ensure only one instance exists (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self) -> None:
        """Initialize the prompt loader."""
        # Calculate prompts directory: src/core/prompt_loader.py -> project_root/prompts/
        self._prompt_dir = Path(__file__).resolve().parent.parent.parent / "prompts"
        
        if not self._prompt_dir.exists():
            raise FileNotFoundError(
                f"Prompts directory not found: {self._prompt_dir}\n"
                f"Expected location: project_root/prompts/"
            )
    
    @lru_cache(maxsize=32)
    def load(self, path: str, strip: bool = True) -> str:
        """Load a prompt file with caching.
        
        Args:
            path: Relative path from prompts/ directory
                  Example: "strategist/strategist_surabaya_human.txt"
            strip: Whether to strip leading/trailing whitespace (default: True)
        
        Returns:
            Content of the prompt file as string
        
        Raises:
            FileNotFoundError: If the prompt file doesn't exist
            UnicodeDecodeError: If file encoding is not UTF-8
        
        Examples:
            >>> loader = PromptLoader()
            >>> # Load strategist base prompt
            >>> base = loader.load("strategist/strategist_surabaya_human.txt")
            >>> # Load mode-specific overlay
            >>> override = loader.load("strategist/strategist_first_person_override.txt")
        """
        full_path = self._prompt_dir / path
        
        if not full_path.exists():
            # Provide helpful error message
            raise FileNotFoundError(
                f"Prompt file not found: {path}\n"
                f"Expected location: {full_path}\n"
                f"Available folders: {self._list_folders()}"
            )
        
        try:
            content = full_path.read_text(encoding="utf-8")
            return content.strip() if strip else content
        except UnicodeDecodeError as e:
            raise UnicodeDecodeError(
                e.encoding,
                e.object,
                e.start,
                e.end,
                f"Failed to decode {path} as UTF-8. Ensure file is saved with UTF-8 encoding."
            )
    
    def _list_folders(self) -> str:
        """List available prompt folders for error messages."""
        if not self._prompt_dir.exists():
            return "(prompts directory not found)"
        
        folders = [d.name for d in self._prompt_dir.iterdir() if d.is_dir()]
        return ", ".join(sorted(folders)) if folders else "(no folders found)"
    
    def clear_cache(self) -> None:
        """Clear the LRU cache.
        
        Useful for testing or when prompts are modified at runtime.
        
        Examples:
            >>> loader = PromptLoader()
            >>> loader.load("strategist/strategist_surabaya_human.txt")
            >>> # Modify the file externally...
            >>> loader.clear_cache()
            >>> # Next load will read fresh content
            >>> loader.load("strategist/strategist_surabaya_human.txt")
        """
        self.load.cache_clear()
    
    @property
    def prompt_dir(self) -> Path:
        """Get the prompts directory path.
        
        Returns:
            Path object pointing to prompts directory
        """
        return self._prompt_dir
    
    def exists(self, path: str) -> bool:
        """Check if a prompt file exists.
        
        Args:
            path: Relative path from prompts/ directory
        
        Returns:
            True if file exists, False otherwise
        
        Examples:
            >>> loader = PromptLoader()
            >>> loader.exists("strategist/strategist_surabaya_human.txt")
            True
            >>> loader.exists("nonexistent/file.txt")
            False
        """
        full_path = self._prompt_dir / path
        return full_path.exists()


# Convenience function for simple usage
def load_prompt(path: str, strip: bool = True) -> str:
    """Convenience function to load a prompt.
    
    Args:
        path: Relative path from prompts/ directory
        strip: Whether to strip whitespace (default: True)
    
    Returns:
        Content of the prompt file
    
    Examples:
        >>> from src.prompt_loader import load_prompt
        >>> content = load_prompt("strategist/strategist_surabaya_human.txt")
    """
    loader = PromptLoader()
    return loader.load(path, strip=strip)
