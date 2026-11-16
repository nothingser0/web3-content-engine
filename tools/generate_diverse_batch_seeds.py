#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate diverse batch seeds for weekly content with deduplication
Uses evergreen.json topic pool and tracks used topics to avoid repetition
"""

import json
import os
import random
from pathlib import Path
from datetime import datetime


def _get_data_path(filename):
    """Get path to data file"""
    # Get project root (2 levels up from tools/)
    project_root = Path(__file__).resolve().parent.parent
    return project_root / "data" / filename


def _load_evergreen_topics():
    """Load all evergreen topics from JSON"""
    topics_file = _get_data_path("topic_templates/evergreen.json")
    with open(topics_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_used_topics():
    """Load previously used topics"""
    used_file = _get_data_path("used_topics.json")
    if not used_file.exists():
        return {"used_topics": [], "last_reset": None}
    
    with open(used_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_used_topics(used_data):
    """Save used topics to file"""
    used_file = _get_data_path("used_topics.json")
    used_file.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(used_file, used_data)


def _write_json_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, path)


def generate_diverse_seeds(count=5, mode="batch"):
    """
    Generate diverse seeds from evergreen topics with deduplication
    
    Args:
        count: Number of topics to generate (default: 5)
        mode: Content mode (default: "batch")
    
    Returns:
        List of topic dictionaries with text, context, pillar, and mode
    """
    # Load all evergreen topics
    all_topics = _load_evergreen_topics()
    
    # Load used topics
    used_data = _load_used_topics()
    used_topics_list = used_data.get("used_topics") or []
    used_topics = set(used_topics_list)
    
    # Get available topics (not yet used)
    available_topics = [t for t in all_topics if t not in used_topics]
    
    # If not enough available, reset the used list
    if len(available_topics) < count:
        print(f"[*] Only {len(available_topics)} topics available. Resetting used topics pool.", flush=True)
        available_topics = all_topics.copy()
        used_topics = set()
        used_data = {
            "used_topics": [],
            "last_reset": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    # Randomly select topics
    selected_topics = random.sample(available_topics, min(count, len(available_topics)))
    
    # Update used topics
    used_topics.update(selected_topics)
    used_data["used_topics"] = list(used_topics)
    _save_used_topics(used_data)
    
    # Format as seed dictionaries
    seeds = []
    for topic in selected_topics:
        seeds.append({
            "text": topic,
            "context": f"Mode: {mode}. Generate evergreen educational content.",
            "pillar": "general",  # Evergreen topics don't have pillar categorization
            "mode": mode
        })
    
    return seeds

def main():
    mode = "Evergreen"  # Default mode
    
    # Generate 5 diverse seeds
    seeds = generate_diverse_seeds(count=5, mode=mode)
    
    print(f"Generated {len(seeds)} diverse seeds for batch:", flush=True)
    for i, seed in enumerate(seeds, 1):
        print(f"  {i}. [{seed['pillar']}] {seed['text']}", flush=True)
    print(flush=True)
    
    # Save to file
    output_file = 'temp_batch_diverse_input.json'
    _write_json_atomic(output_file, seeds)
    
    print(f"Saved to: {output_file}", flush=True)
    return 0

if __name__ == '__main__':
    exit(main())
