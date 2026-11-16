#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Angle Deduplication System

Tracks previously selected angles and filters out duplicates/similar angles
to prevent content repetition across multiple runs.
"""

import json
import os
import time
from pathlib import Path
from difflib import SequenceMatcher
from contextlib import contextmanager
from typing import List, Dict, Any, Optional


def _get_dedup_file() -> Path:
    """Get path to selected angles tracking file"""
    project_root = Path(__file__).resolve().parent.parent.parent
    return project_root / "data" / "selected_angles.json"


@contextmanager
def _file_lock(path: Path, timeout: float = 10.0):
    lock_path = path.with_suffix(path.suffix + ".lock")
    deadline = time.time() + timeout
    lock_fd = None
    while lock_fd is None:
        try:
            lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.time() >= deadline:
                raise TimeoutError(f"Timed out waiting for lock: {lock_path}")
            time.sleep(0.05)

    try:
        yield
    finally:
        os.close(lock_fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


def load_selected_angles() -> List[str]:
    """
    Load previously selected angle titles from history
    
    Returns:
        List of angle titles that have been selected before
    """
    dedup_file = _get_dedup_file()
    
    if not dedup_file.exists():
        return []
    
    try:
        with open(dedup_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("selected_angles", [])
    except (json.JSONDecodeError, IOError):
        return []


def save_selected_angle(angle_data: Dict[str, Any]) -> None:
    """
    Save newly selected angle to history
    
    Args:
        angle_data: Angle dictionary with at least 'title' key
    """
    dedup_file = _get_dedup_file()
    dedup_file.parent.mkdir(parents=True, exist_ok=True)
    
    with _file_lock(dedup_file):
        selected_angles = load_selected_angles()

        angle_title = angle_data.get("title", "")
        if angle_title and angle_title not in selected_angles:
            selected_angles.append(angle_title)

        _write_json_atomic(dedup_file, {"selected_angles": selected_angles})


def is_similar(text1: str, text2: str, threshold: float = 0.8) -> bool:
    """
    Check if two texts are similar using fuzzy string matching
    
    Args:
        text1: First text to compare
        text2: Second text to compare
        threshold: Similarity threshold (0.0 to 1.0, default 0.8)
    
    Returns:
        True if similarity ratio >= threshold
    """
    # Normalize: lowercase and strip
    text1_norm = text1.lower().strip()
    text2_norm = text2.lower().strip()
    
    # Calculate similarity ratio
    ratio = SequenceMatcher(None, text1_norm, text2_norm).ratio()
    
    return ratio >= threshold


def filter_duplicate_angles(
    angles: List[Dict[str, Any]], 
    threshold: float = 0.8,
    verbose: bool = True
) -> List[Dict[str, Any]]:
    """
    Filter out angles that are similar to previously selected ones
    
    Args:
        angles: List of angle dictionaries (each must have 'title' key)
        threshold: Similarity threshold for duplicate detection (default 0.8)
        verbose: Print filtering info (default True)
    
    Returns:
        Filtered list of angles (non-duplicates only)
    """
    # Load history
    selected_angles = load_selected_angles()
    
    if not selected_angles:
        # No history yet, return all angles
        return angles
    
    # Filter angles
    filtered_angles = []
    duplicates_found = []
    
    for angle in angles:
        angle_title = angle.get("title", "")
        
        # Check if similar to any previous angle
        is_duplicate = any(
            is_similar(angle_title, prev_title, threshold)
            for prev_title in selected_angles
        )
        
        if is_duplicate:
            duplicates_found.append(angle_title)
        else:
            filtered_angles.append(angle)
    
    # Print info if verbose
    if verbose and duplicates_found:
        print(f"\n[Dedup] Filtered {len(duplicates_found)} duplicate/similar angle(s):")
        for dup in duplicates_found:
            print(f"  - {dup[:80]}...")
        print(f"[Dedup] {len(filtered_angles)} unique angle(s) remaining\n")
    
    return filtered_angles


def reset_angle_history(confirm: bool = False) -> bool:
    """
    Reset the angle selection history
    
    Args:
        confirm: Must be True to actually reset (safety check)
    
    Returns:
        True if reset was performed
    """
    if not confirm:
        print("[Dedup] Reset cancelled - confirm parameter must be True")
        return False
    
    dedup_file = _get_dedup_file()
    
    if dedup_file.exists():
        dedup_file.unlink()
        print("[Dedup] Angle history reset successfully")
        return True
    else:
        print("[Dedup] No history file found")
        return False


def get_angle_stats() -> Dict[str, Any]:
    """
    Get statistics about angle selection history
    
    Returns:
        Dictionary with stats (total_selected, sample_angles)
    """
    selected_angles = load_selected_angles()
    
    return {
        "total_selected": len(selected_angles),
        "sample_angles": selected_angles[:5] if selected_angles else [],
        "dedup_file": str(_get_dedup_file())
    }
