#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import requests
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from src.utils.logger import setup_logger
    from src.utils.common import setup_console_encoding
    from src.qc.format_specific import detect_format
else:
    from ..utils.logger import setup_logger
    from ..utils.common import setup_console_encoding
    from ..qc.format_specific import detect_format

setup_console_encoding()
logger = setup_logger(__name__)


def _load_engagement_prompt_template() -> str:
    prompt_file = Path(__file__).parent.parent.parent / 'prompts' / 'engagement' / 'engagement_surabaya.txt'
    return prompt_file.read_text(encoding='utf-8')

def call_engagement_ai(content: str, format_type: str) -> Optional[str]:
    prompt_template = _load_engagement_prompt_template()
    
    current_date = datetime.now().strftime("%B %d, %Y")
    current_day_of_week = datetime.now().strftime("%A")
    current_month = datetime.now().strftime("%B %Y")
    current_year = str(datetime.now().year)
    
    prompt = prompt_template.replace('{content}', content).replace('{format_type}', format_type)
    prompt = prompt.replace('{current_date}', current_date)
    prompt = prompt.replace('{current_day_of_week}', current_day_of_week)
    prompt = prompt.replace('{current_month}', current_month)
    prompt = prompt.replace('{current_year}', current_year)

    from src.utils.config import load_api_config, WEB3_CONTENT_MODEL_OVERRIDE
    from src.core.model_router import ModelRouter
    
    api_url, api_key = load_api_config()
    
    use_router = True
    router = None
    model = None
    
    if WEB3_CONTENT_MODEL_OVERRIDE:
        logger.info(f"[Engagement] Using override model: {WEB3_CONTENT_MODEL_OVERRIDE}")
        model = WEB3_CONTENT_MODEL_OVERRIDE
        use_router = False
    else:
        router = ModelRouter(api_url, api_key)
    
    messages = [{"role": "user", "content": prompt}]
    
    if use_router and router:
        logger.info(f"[Engagement] Using router (Kategori C)")
        
        import sys
        print(f"    Task: Generate posting strategy & engagement plan", file=sys.stderr)
        print(f"    Expected: Optimal posting time, hashtags, CTA, first comment", file=sys.stderr)
        print(f"    Time estimate: 30-60 seconds", file=sys.stderr)
        print(f"", file=sys.stderr)
        
        content_result = router.call_with_fallback(
            role="engagement",
            messages=messages,
            max_tokens=3000,
            temperature=0.8
        )
        return content_result
    elif model:
        logger.info(f"[Engagement] Using override model: {model}")
        try:
            response = requests.post(
                f"{api_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.8,
                    "max_tokens": 3000
                },
                timeout=600
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                logger.error(f"API Error: {response.status_code}")
                return None
        
        except Exception as e:
            logger.error(f"Error calling AI: {e}")
            return None
    else:
        logger.error("[Engagement] No router or model available")
        return None

def save_engagement_strategy(content_file, strategy, output_dir=None):
    """Save engagement strategy to file"""
    if output_dir:
        # Session folder mode: simple filename
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_file = out_dir / "engagement.txt"
    else:
        # Legacy mode: timestamp-based in output/engagement/
        content_path = Path(content_file)
        out_dir = Path(__file__).parent.parent / 'output' / 'engagement'
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract topic from filename
        filename = content_path.stem
        if '_content_' in filename:
            topic_part = filename.split('_content_')[0]
            timestamp = filename.split('_content_')[1]
            
            # Remove format prefix if exists
            if '__' in topic_part:
                parts = topic_part.split('__', 1)
                topic = parts[1] if len(parts) > 1 else topic_part
            else:
                topic = topic_part
        else:
            topic = "engagement"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save
        output_file = out_dir / f"{topic}_engagement_{timestamp}.txt"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("═══════════════════════════════════════════════════════\n")
        f.write("ENGAGEMENT STRATEGY - FROM CONTENT ANALYSIS\n")
        f.write("═══════════════════════════════════════════════════════\n\n")
        f.write(strategy)
        f.write("\n\n═══════════════════════════════════════════════════════\n")
        f.write("END OF ENGAGEMENT STRATEGY\n")
        f.write("═══════════════════════════════════════════════════════\n")
    
    return output_file

def main():
    import argparse
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Engagement Strategy Generator - AI-powered')
    parser.add_argument('content_file', help='Input content file')
    parser.add_argument('--output-dir', help='Session output directory (optional)')
    args = parser.parse_args()
    
    if not os.path.exists(args.content_file):
        print(f"[!] File not found: {args.content_file}")
        sys.exit(1)
    
    # Read content
    with open(args.content_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Detect format
    format_type = detect_format(content)
    
    print("============================================================")
    print("ENGAGEMENT STRATEGY GENERATOR - AI-POWERED")
    print("============================================================")
    print(f"[*] Detected format: {format_type}")
    print(f"[*] Analyzing content for specific strategy...")
    print()
    
    # Generate strategy
    strategy = call_engagement_ai(content, format_type)
    
    if not strategy:
        print("[!] Failed to generate engagement strategy")
        sys.exit(1)
    
    # Save
    output_file = save_engagement_strategy(args.content_file, strategy, args.output_dir)
    
    print("[*] Engagement strategy generated!")
    print()
    print("============================================================")
    print("ENGAGEMENT STRATEGY")
    print("============================================================")
    print()
    print(f"[*] Saved to: {output_file}")
    print()

if __name__ == "__main__":
    main()
