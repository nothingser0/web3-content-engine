#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fallback niche topic templates for sparse content generation.

Topics are now stored in JSON files for easier maintenance:
- data/topic_templates/evergreen.json (205 evergreen topics)
- data/topic_templates/batch.json (20 batch ideas)
"""

from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
import json
import random


@lru_cache(maxsize=2)
def _load_topics(topic_type: str) -> list[str]:
    """Load topics from JSON file with caching.
    
    Args:
        topic_type: Either "evergreen" or "batch"
        
    Returns:
        List of topic strings
        
    Raises:
        FileNotFoundError: If JSON file doesn't exist
        json.JSONDecodeError: If JSON file is malformed
    """
    # Go up 3 levels: src/core/topic_templates.py -> src/core/ -> src/ -> project_root/
    project_root = Path(__file__).parent.parent.parent
    json_path = project_root / "data" / "topic_templates" / f"{topic_type}.json"
    
    if not json_path.exists():
        raise FileNotFoundError(f"Topic file not found: {json_path}")
    
    with open(json_path, "r", encoding="utf-8") as f:
        topics: list[str] = json.load(f)
    
    if not isinstance(topics, list):
        raise ValueError(f"Expected list in {json_path}, got {type(topics)}")
    
    return topics


def get_topic_templates(mode: str = "evergreen", include_batch: bool = False, *, shuffle: bool = True) -> list[str]:
    """Return fallback topics for requested mode.
    
    Args:
        mode: Topic mode ("evergreen" or "batch")
        include_batch: Whether to include batch topics in addition to mode topics
        shuffle: Whether to shuffle the results (keyword-only)
        
    Returns:
        List of topic template strings
        
    Example:
        >>> topics = get_topic_templates("evergreen", include_batch=True, shuffle=True)
        >>> len(topics)  # 205 evergreen + 20 batch = 225
        225
    """
    normalized = (mode or "evergreen").strip().lower()
    
    # Load base topics - "batch" if mode is "batch", otherwise "evergreen"
    if normalized == "batch":
        topics = list(_load_topics("batch"))
    else:
        topics = list(_load_topics("evergreen"))
    
    # Add batch topics if requested
    if include_batch:
        topics.extend(_load_topics("batch"))
    
    # Shuffle if requested
    if shuffle:
        random.shuffle(topics)
    
    return topics


def merge_unique_topics(primary_topics: Iterable[str], fallback_topics: Iterable[str]) -> list[str]:
    """Append fallback topics without repeating normalized values.
    
    Deduplication is case-insensitive (normalized to lowercase).
    Order is preserved: primary topics first, then fallback topics.
    
    Args:
        primary_topics: Primary topic list (appears first)
        fallback_topics: Fallback topic list (appended after primary)
        
    Returns:
        Merged list with no duplicates (case-insensitive comparison)
        
    Example:
        >>> primary = ["Topic A", "Topic B"]
        >>> fallback = ["topic b", "Topic C"]
        >>> merge_unique_topics(primary, fallback)
        ['Topic A', 'Topic B', 'Topic C']  # "topic b" deduplicated
    """
    merged: list[str] = []
    seen: set[str] = set()

    for topic in list(primary_topics) + list(fallback_topics):
        cleaned = str(topic).strip()
        normalized = cleaned.lower()
        if not cleaned or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(cleaned)

    return merged
