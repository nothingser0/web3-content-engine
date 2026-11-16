#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Writer - Web3 Content Pipeline
Generate full content from selected angle (Surabaya Style)
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from src.utils.config import load_api_config
    from src.utils.logger import setup_logger
    from src.core.api_client import APIClient
    from src.utils.common import setup_console_encoding, print_section, exit_with_error
    from src.utils.validation import validate_format_choice, ValidationError, sanitize_filename
else:
    from ..utils.config import load_api_config
    from ..utils.logger import setup_logger
    from ..core.api_client import APIClient
    from ..utils.common import setup_console_encoding, print_section, exit_with_error
    from ..utils.validation import validate_format_choice, ValidationError, sanitize_filename

# Setup
setup_console_encoding()
logger = setup_logger(__name__)

def _load_prompt_template(prompt_name: str) -> str:
    """Load prompt template from file"""
    prompt_file = Path(__file__).parent.parent.parent / 'prompts' / f'{prompt_name}.txt'
    with open(prompt_file, 'r', encoding='utf-8') as f:
        return f.read()

def _format_key_points(key_points: Any) -> str:
    """Format key points as string"""
    if isinstance(key_points, list):
        return '\n'.join([f"- {p}" for p in key_points])
    return str(key_points)

def _build_prompt(template: str, angle_data: Dict[str, Any], format_choice: str) -> str:
    """Build prompt from template and data"""
    # Add temporal context
    current_date = datetime.now().strftime("%B %d, %Y")  # e.g., "June 28, 2026"
    current_month = datetime.now().strftime("%B %Y")     # e.g., "June 2026"
    current_year = str(datetime.now().year)              # e.g., "2026"
    
    prompt = template.replace('{title}', angle_data.get('title', ''))
    prompt = prompt.replace('{hook}', angle_data.get('hook', ''))
    prompt = prompt.replace('{pillar}', angle_data.get('pillar', ''))
    prompt = prompt.replace('{evergreen_category}', angle_data.get('evergreen_category', 'N/A'))
    prompt = prompt.replace('{key_points}', _format_key_points(angle_data.get('key_points', [])))
    prompt = prompt.replace('{cta}', angle_data.get('cta', ''))
    prompt = prompt.replace('{format}', format_choice)
    prompt = prompt.replace('{current_date}', current_date)
    prompt = prompt.replace('{current_month}', current_month)
    prompt = prompt.replace('{current_year}', current_year)
    return prompt


def _trim_single_tweet(content: str) -> str:
    """Trim single tweet while preserving up to two hashtags."""
    marker = '**SINGLE TWEET:**\n\n'
    clean_content = content.replace(marker, '', 1)
    if len(clean_content) <= 280:
        return content

    hashtags = re.findall(r'#\w+', clean_content)
    unique_hashtags: list[str] = []
    for tag in hashtags:
        if tag not in unique_hashtags:
            unique_hashtags.append(tag)

    hashtag_block = ''
    if unique_hashtags:
        hashtag_block = ' ' + ' '.join(unique_hashtags[:2])
        clean_content = re.sub(r'\s*#\w+', '', clean_content).strip()

    allowed_length = 280 - len(hashtag_block)
    if allowed_length < 20:
        hashtag_block = ''
        allowed_length = 280

    trimmed = clean_content[: max(0, allowed_length - 3)].rstrip(' ,;:-') + '...'
    final_content = (trimmed + hashtag_block).strip()
    return f'{marker}{final_content}'


def _ensure_single_tweet_hashtags_and_tone(content: str) -> str:
    """Add Surabaya flavor for QC stability without forcing hashtags."""
    marker = '**SINGLE TWEET:**\n\n'
    clean_content = content.replace(marker, '', 1).strip()

    tone_words = ['cok', 'rek', 'ojo', 'piye', 'aku', 'kamu']
    found_words = [word for word in tone_words if re.search(rf'\b{re.escape(word)}\b', clean_content.lower())]
    if len(found_words) < 2:
        clean_content = clean_content.rstrip()
        if clean_content.endswith('?'):
            clean_content = clean_content[:-1].rstrip() + ', rek?'
        else:
            clean_content = f"{clean_content} Rek, piye?"

    normalized = f'{marker}{clean_content.strip()}'
    content_without_marker = normalized.replace(marker, '', 1)
    if len(content_without_marker) > 280:
        return _trim_single_tweet(normalized)
    return normalized

def call_writer_ai(
    angle_data: Dict[str, Any], 
    format_choice: str,
    client: Optional[APIClient] = None
) -> Optional[str]:
    """
    Call AI to generate content from selected angle
    
    Args:
        angle_data: Dictionary containing angle information (title, hook, pillar, key_points, cta)
        format_choice: Content format (Thread, Image, etc.)
        client: Optional APIClient instance (for dependency injection)
    
    Returns:
        Generated content string or None on failure
    """
    title = str(angle_data.get('title', '')).strip()

    try:
        format_choice = validate_format_choice(format_choice)
    except ValidationError as e:
        logger.error(f"Invalid format choice: {e}")
        return None
    
    api_url, api_key = load_api_config()
    from src.core.model_router import ModelRouter
    from src.utils.config import WEB3_CONTENT_MODEL_OVERRIDE
    use_router = True
    router = None
    model = None
    
    if WEB3_CONTENT_MODEL_OVERRIDE:
        logger.info(f"[Writer] Using override model: {WEB3_CONTENT_MODEL_OVERRIDE}")
        model = WEB3_CONTENT_MODEL_OVERRIDE
        use_router = False
    else:
        router = ModelRouter(api_url, api_key)
    
    should_close_client = False
    
    if client is None and not use_router:
        # Only need APIClient if using override (router has its own HTTP logic)
        client = APIClient(api_url, api_key, max_retries=3, timeout=600)
        should_close_client = True
    
    try:
        # Load and build prompt
        prompt_template = _load_prompt_template('writer/writer_surabaya')
        prompt = _build_prompt(prompt_template, angle_data, format_choice)
        
        # Call API with router or override
        logger.info(f"Calling AI Writer for format: {format_choice}")
        
        messages = [{"role": "user", "content": prompt}]
        
        if use_router and router:
            # Use router for 3-tier fallback (Kategori B)
            logger.info(f"[Writer] Using router (Kategori B)")
            
            # Show writer context
            import sys
            format_name = angle_data.get('format', 'Unknown')
            print(f"    Format: {format_name}", file=sys.stderr)
            print(f"    Expected: Full content in selected format", file=sys.stderr)
            print(f"    Time estimate: 60-120 seconds (creative writing takes time)", file=sys.stderr)
            print(f"", file=sys.stderr)
            
            content = router.call_with_fallback(
                role="writer",
                messages=messages,
                max_tokens=4096,
                temperature=0.8
            )
        elif client and model:
            # Use override model with APIClient
            logger.info(f"[Writer] Using override model: {model}")
            content = client.call_chat_completion(
                model=model,
                messages=messages,
                max_tokens=4096,
                temperature=0.8
            )
        else:
            logger.error("[Writer] No router or client available")
            return None
        
        if content:
            logger.info("Content generated successfully")
        else:
            logger.error("Failed to generate content")
        
        return content
        
    except Exception as e:
        logger.error(f"Unexpected error in writer: {e}", exc_info=True)
        return None
    finally:
        if should_close_client and client:
            client.close()

def main() -> None:
    """Main function"""
    import sys
    import argparse
    
    print_section("AI WRITER - Web3 Content Pipeline (Surabaya Style)")
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='AI Writer - Generate content from angle')
    parser.add_argument('input_file', nargs='?', help='Input angle JSON file')
    parser.add_argument('--output-dir', help='Session output directory (optional)')
    args = parser.parse_args()
    
    # Read angle from stdin or file
    if args.input_file:
        # Read from file
        input_file = args.input_file
        try:
            with open(input_file, 'r', encoding='utf-8-sig') as f:
                angle_data = json.load(f)
        except Exception as e:
            exit_with_error(f"Error reading file: {e}")
    else:
        # Read from stdin
        try:
            angle_data = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            exit_with_error(f"Invalid JSON from stdin: {e}")
    
    logger.info(f"Loaded angle: {angle_data.get('title', 'Unknown')}")
    
    # Get format choice - prioritize 'format' key (user choice) over suggested_formats
    format_choice = angle_data.get('format')
    
    # If no 'format' key, use first from suggested_formats
    if not format_choice and isinstance(angle_data.get('suggested_formats'), list):
        format_choice = angle_data['suggested_formats'][0]
    
    # Default to Thread if still no format
    if not format_choice:
        format_choice = 'Thread'
    
    logger.info(f"Format: {format_choice}")
    
    # Generate content
    content = call_writer_ai(angle_data, format_choice)
    
    if not content:
        exit_with_error("Failed to generate content")
    
    # Post-processing: Add format marker if not present
    format_markers = {
        'Single Tweet': '**SINGLE TWEET:**',
        'Thread': '**THREAD:**',
        'Image': '**IMAGE:**',
        'Poll': '**POLL:**'
    }
    
    # Check if content already has format marker
    has_marker = any(marker in content for marker in format_markers.values())
    
    if not has_marker:
        # Add format marker at the beginning
        marker = format_markers.get(format_choice, f'**{format_choice.upper()}:**')
        content = f"{marker}\n\n{content}"
    
    # Post-processing: Enforce character limit for Single Tweet
    if format_choice == 'Single Tweet':
        # Remove format marker for character count
        content_without_marker = content.replace('**SINGLE TWEET:**\n\n', '')
        if len(content_without_marker) > 280:
            logger.warning(f"Single Tweet too long ({len(content_without_marker)} chars), truncating to 280")
            content = _trim_single_tweet(content)
        content = _ensure_single_tweet_hashtags_and_tone(content)
    
    logger.info("Content generated successfully")
    
    # Extract topic from angle data (use title, fallback to first line of content)
    if 'title' in angle_data and angle_data['title']:
        topic = angle_data['title']
    else:
        # Fallback: extract from content first line
        first_line = content.split('\n')[0]
        topic = first_line.replace('#', '').replace('*', '').strip()
    
    # Clean topic for filename
    try:
        safe_topic = sanitize_filename(topic[:50])
    except ValidationError:
        safe_topic = "content"
    
    # Output content
    print_section("GENERATED CONTENT")
    
    # Print to stdout (for piping)
    print(content)
    
    # Save to file
    if args.output_dir:
        # New behavior: save to session folder
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "content.txt"
    else:
        # Old behavior: save to output/writer/ with timestamp
        output_dir = Path(__file__).parent.parent / 'output' / 'writer'
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"{safe_topic}_content_{timestamp}.txt"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    logger.info(f"Saved to: {output_file}")

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
