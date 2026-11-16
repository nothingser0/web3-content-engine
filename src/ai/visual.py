#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Visual Prompt Generator - Dremina-ready prompt output
"""

import os
import re
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple, Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from src.core.model_router import ModelRouter
    from src.utils.config import load_api_config
    from src.utils.logger import setup_logger
    from src.utils.common import setup_console_encoding
    from src.qc.format_specific import detect_format
else:
    from ..core.model_router import ModelRouter
    from ..utils.config import load_api_config
    from ..utils.logger import setup_logger
    from ..utils.common import setup_console_encoding
    from ..qc.format_specific import detect_format

setup_console_encoding()
logger = setup_logger(__name__)


@lru_cache(maxsize=8)
def _load_template(template_name: str) -> str:
    """Load prompt template from file with caching"""
    project_root = Path(__file__).resolve().parent.parent.parent
    template_path = project_root / "prompts" / template_name
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()





def call_visual_ai(
    content: str, format_type: str, visual_type: str = "single"
) -> Optional[str]:
    """
    Call AI to generate specific visual concepts

    Args:
        content: Content to generate visual for
        format_type: Thread, Image, Single Tweet, Poll
        visual_type: "slides" (1-4), "header" (1), "single" (1)

    Returns:
        Visual brief text or None
    """

    # Get current date for context
    current_date = datetime.now().strftime("%B %d, %Y")  # e.g., "June 29, 2026"

    # Load base template
    base_template = _load_template("format/visual_brief_template.txt")

    # Determine format-specific instructions
    if format_type == "Image" and visual_type == "slides":
        format_instructions = _load_template("format/format_image_slides.txt")
    elif format_type == "Thread" and visual_type == "header":
        format_instructions = _load_template("format/format_thread_header.txt")
    elif format_type == "Thread" and visual_type == "slides":
        format_instructions = _load_template("format/format_thread_slides.txt")
    else:
        # Single visual (Single Tweet, Poll, or single Image)
        format_instructions = _load_template("format/format_single.txt")

    # Build final prompt
    prompt = base_template.format(
        current_date=current_date,
        content=content,
        format_type=format_type,
        visual_type=visual_type,
        format_specific_instructions=format_instructions,
    )

    # Call API with fallback model routing
    api_url, api_key = load_api_config()
    
    logger.info(f"Generating visual brief for {format_type} ({visual_type})")
    router = ModelRouter(api_url, api_key)
    return router.call_with_fallback(
        role="visual",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4000,
        temperature=0.8,
    )


def save_visual_brief(content_file, visual_brief, output_dir=None):
    """Save visual brief to file"""
    if output_dir:
        # New behavior: save to session folder
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_file = out_dir / "visual.txt"
    else:
        # Old behavior: save to output/visual/ with timestamp
        content_path = Path(content_file)
        out_dir = Path(__file__).parent.parent / "output" / "visual"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Extract topic from filename
        filename = content_path.stem
        if "_content_" in filename:
            topic_part = filename.split("_content_")[0]
            timestamp = filename.split("_content_")[1]

            # Remove format prefix if exists
            if "__" in topic_part:
                parts = topic_part.split("__", 1)
                topic = parts[1] if len(parts) > 1 else topic_part
            else:
                topic = topic_part
        else:
            topic = content_path.stem or "visual"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save
        output_file = out_dir / f"{topic}_visual_{timestamp}.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("═══════════════════════════════════════════════════════\n")
        f.write("VISUAL DESIGN BRIEF - SPECIFIC CONCEPTS\n")
        f.write("═══════════════════════════════════════════════════════\n\n")
        f.write(visual_brief)
        f.write("\n\n═══════════════════════════════════════════════════════\n")
        f.write("END OF VISUAL BRIEF\n")
        f.write("═══════════════════════════════════════════════════════\n")

    return output_file


class VisualUnit(NamedTuple):
    label: str
    text: str


def _normalize_label(label: str) -> str:
    compact = re.sub(r'\s+', ' ', label).strip()
    compact = compact.replace('**', '').strip()
    compact = re.sub(r'\s*\(\s*', ' (', compact)
    return compact


def _minimal_overlay_text(unit_text: str, max_words: int = 8) -> str:
    # For slide-based content, extract from Text: "..." pattern
    text_quote_match = re.search(r'Text:\s*"([^"]+)"', unit_text, re.DOTALL)
    if text_quote_match:
        text_content = text_quote_match.group(1).strip()
        lines = [line.strip() for line in text_content.splitlines() if line.strip()]
        # Take first meaningful line (usually title/header)
        source = lines[0] if lines else 'Web3 safety'
    else:
        # Fallback: try **Text:** ``` block
        text_block_match = re.search(r'\*\*Text:\*\*\s*```(.*?)```', unit_text, re.DOTALL)
        if text_block_match:
            text_content = text_block_match.group(1).strip()
            lines = [line.strip() for line in text_content.splitlines() if line.strip()]
            source = lines[0] if lines else 'Web3 safety'
        else:
            lines = [line.strip(' -*#') for line in unit_text.splitlines() if line.strip()]
            candidates = [line for line in lines if not line.lower().startswith(('tweet ', 'slide ', 'visual:'))]
            source = candidates[0] if candidates else (lines[0] if lines else 'Web3 safety')
    
    source = re.sub(r'".*?"', '', source)
    source = re.sub(r'\s+', ' ', source).strip(' .,:;!-')
    words = source.split()
    trimmed_words = words[:max_words]
    overlay = ' '.join(trimmed_words).strip()
    return overlay or 'Web3 safety'





def _clean_unit_text(text: str) -> str:
    cleaned = re.sub(r'\n{3,}', '\n\n', text.strip())
    return cleaned


















def main():
    import argparse
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Visual AI - Generate visual brief from content')
    parser.add_argument('content_file', help='Input content file')
    parser.add_argument('--output-dir', help='Session output directory (optional)')
    args = parser.parse_args()
    
    if not os.path.exists(args.content_file):
        print(f"[!] File not found: {args.content_file}")
        sys.exit(1)

    with open(args.content_file, 'r', encoding='utf-8') as f:
        content = f.read()

    format_type = detect_format(content)
    
    # Determine visual type based on format
    if format_type == "Image":
        visual_type = "slides"
    elif format_type == "Thread":
        visual_type = "slides"  # Generate header + additional images for thread tweets
    else:
        visual_type = "single"

    print("============================================================")
    print("VISUAL BRIEF GENERATOR - AI-POWERED")
    print("============================================================")
    print(f"[*] Detected format: {format_type}")
    print(f"[*] Generating visual brief ({visual_type})...")
    print()

    visual_brief = call_visual_ai(content, format_type, visual_type)
    
    if not visual_brief:
        print("[!] Failed to generate visual brief")
        sys.exit(1)

    output_file = save_visual_brief(args.content_file, visual_brief, args.output_dir)

    print("[*] Visual brief generated!")
    print()
    print("============================================================")
    print("VISUAL DESIGN BRIEF")
    print("============================================================")
    print()
    print(f"[*] Saved to: {output_file}")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        
        # Only prompt for input when running interactively
        if sys.stdin.isatty():
            try:
                input("\nPress Enter to close...")
            except (EOFError, KeyboardInterrupt):
                pass
        
        sys.exit(1)
