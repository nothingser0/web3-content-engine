#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daily Auto Content Generator
Generates single (or specified count) evergreen content piece for scheduled daily runs.

Usage:
    python run_daily_auto.py
    python run_daily_auto.py --count 1
    python run_daily_auto.py --keywords "security,airdrop"
"""

import sys
import json
import subprocess
import random
import re
import shutil
import concurrent.futures
from pathlib import Path
from datetime import datetime
from typing import List, Dict

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.discord import get_angle_channel_id, get_discord_skip_reason, get_final_channel_id, safe_discord_filename, send_discord_bot_message
from src.utils.buffer import send_to_buffer
from src.core.prompt_loader import PromptLoader
from src.core.angle_dedup import filter_duplicate_angles, save_selected_angle
try:
    from tools.generate_diverse_batch_seeds import generate_diverse_seeds
except ImportError:
    def generate_diverse_seeds(count=1, mode="batch"):
        print("[!] Warning: Could not import generate_diverse_seeds, using fallback", file=sys.stderr)
        return []

AVAILABLE_FORMATS = ['Thread', 'Image', 'Single Tweet', 'Poll']
_prompt_loader = PromptLoader()


def load_prompt(name: str) -> str:
    return _prompt_loader.load(name)


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"   {title}")
    print("=" * 60 + "\n")


def generate_topics(keywords: List[str] = None, count: int = 1) -> List[Dict[str, str]]:
    print(f"[*] Selecting {count} evergreen topic(s)...", flush=True)
    topics = generate_diverse_seeds(count=count, mode="batch")
    
    if not topics:
        print("[!] Using fallback topic", file=sys.stderr, flush=True)
        fallback = [
            {"text": "Red flags scam project yang sering diabaikan", "context": "Evergreen security", "pillar": "security", "mode": "batch"},
            {"text": "AI tools untuk riset Web3 hemat waktu", "context": "Evergreen tools", "pillar": "tools", "mode": "batch"},
            {"text": "Burnout prevention untuk Web3 researcher", "context": "Evergreen mindset", "pillar": "mindset", "mode": "batch"},
            {"text": "Framework evaluate campaign effort vs value", "context": "Evergreen evaluation", "pillar": "evaluation", "mode": "batch"},
            {"text": "Onchain reputation building organik", "context": "Evergreen reputation", "pillar": "reputation", "mode": "batch"},
        ]
        topics = random.sample(fallback, min(count, len(fallback)))
    
    return topics


def run_single_pipeline(topic_data: Dict[str, str], index: int = 1) -> Dict[str, object]:
    input_file = PROJECT_ROOT / f"temp_daily_{index}_input.json"
    angle_file = PROJECT_ROOT / f"temp_daily_{index}_angle.json"
    try:
        print(f"\n[Pipeline {index}] [*] Starting: {topic_data['text'][:60]}...", flush=True)
        
        # 1. Create input file
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump([topic_data], f, ensure_ascii=False, indent=2)
        
        print(f"[Pipeline {index}] Step 1/6: Running strategist...", flush=True)
        
        # 2. Run strategist
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "src" / "ai" / "strategist.py"), str(input_file)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=360
        )
        
        if result.returncode != 0:
            error_msg = f"Strategist failed: {result.stderr}"
            print(f"[Pipeline {index}] [X] {error_msg}", flush=True)
            return {"success": False, "index": index, "error": error_msg}
        
        angles_data = json.loads(result.stdout)
        angles = angles_data.get('angles', [])
        
        if not angles:
            error_msg = "No angles generated"
            print(f"[Pipeline {index}] [X] {error_msg}", flush=True)
            return {"success": False, "index": index, "error": error_msg}
        
        angles = filter_duplicate_angles(angles, threshold=0.8, verbose=False)
        if not angles:
            error_msg = "All angles are duplicates"
            print(f"[Pipeline {index}] [!] {error_msg} (skipping)", flush=True)
            return {"success": False, "index": index, "error": error_msg}
        
        # 3. Auto-select first angle (highest score)
        selected_angle = angles[0]
        print(f"[Pipeline {index}] Selected angle: {selected_angle.get('title', 'N/A')[:50]}...", flush=True)
        save_selected_angle(selected_angle)
        
        # 4. Auto-select random format
        content_format = random.choice(AVAILABLE_FORMATS)
        selected_angle['format'] = content_format
        print(f"[Pipeline {index}] Format: {content_format}", flush=True)
        
        angle_file = PROJECT_ROOT / f"temp_daily_{index}_angle.json"
        with open(angle_file, 'w', encoding='utf-8') as f:
            json.dump(selected_angle, f, ensure_ascii=False, indent=2)
        
        # 5. Create session folder
        title = selected_angle.get('title', f'content_{index}')
        title = re.sub(r'\[[\w\s]+\d+\]', '', title)
        title = re.sub(r'^\s*[\w]+\s+\d+\s*[-:]?\s*', '', title)
        safe_title = re.sub(r'[^a-zA-Z0-9\s-]', '', title)[:30].strip().replace(' ', '_')
        safe_title = safe_title if safe_title else f'content_{index}'
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        session_dir = PROJECT_ROOT / "output" / f"{safe_title}_{content_format}_{timestamp}"
        session_dir.mkdir(parents=True, exist_ok=True)
        
        shutil.copy(angle_file, session_dir / "angle.json")
        angle_channel_id = get_angle_channel_id()
        if angle_channel_id:
            message = load_prompt("discord/discord_angle_batch.txt").format(
                angle_title=selected_angle.get('title', 'N/A'),
                angle_hook=str(selected_angle.get('hook', 'N/A'))[:100],
                angle_pillar=selected_angle.get('content_pillar') or selected_angle.get('pillar', 'N/A'),
                content_format=content_format,
            )
            if send_discord_bot_message(angle_channel_id, message, session_dir / "angle.json"):
                print(f"[Pipeline {index}] angle.json sent to Discord Channel A", flush=True)
            else:
                print(f"[Pipeline {index}] Discord angle upload failed", flush=True)
        else:
            reason = get_discord_skip_reason(angle_channel_id, "angle upload")
            if reason:
                print(f"[Pipeline {index}] {reason}", flush=True)
        
        print(f"[Pipeline {index}] Step 2/6: Running writer...", flush=True)
        
        # 6. Run writer
        writer_result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "src" / "ai" / "writer.py"), str(angle_file), 
             "--output-dir", str(session_dir)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=900
        )
        
        if writer_result.returncode != 0:
            error_msg = f"Writer failed: {writer_result.stderr[:200]}"
            print(f"[Pipeline {index}] [X] {error_msg}", flush=True)
            return {"success": False, "index": index, "error": error_msg}
        
        content_file = session_dir / "content.txt"
        if not content_file.exists():
            error_msg = "Content file not generated"
            print(f"[Pipeline {index}] [X] {error_msg}", flush=True)
            return {"success": False, "index": index, "error": error_msg}
        
        print(f"[Pipeline {index}] Step 3-4/6: Running visual & engagement concurrently...", flush=True)
        
        # 7. Check if visual generation is needed
        should_generate_visual = False
        if content_format in ['Thread', 'Image']:
            should_generate_visual = True
            print(f"[Pipeline {index}] Visual generation: 100% (format: {content_format})", flush=True)
        elif content_format in ['Single Tweet', 'Poll']:
            if random.random() < 0.6:
                should_generate_visual = True
                print(f"[Pipeline {index}] Visual generation: Selected (60% probability, format: {content_format})", flush=True)
            else:
                print(f"[Pipeline {index}] Visual generation: Skipped (40% probability, format: {content_format})", flush=True)
        else:
            should_generate_visual = True
            print(f"[Pipeline {index}] Visual generation: 100% (unknown format: {content_format})", flush=True)
        
        # Run visual and engagement in parallel using ThreadPoolExecutor
        def _run_visual():
            if not should_generate_visual:
                return None
            return subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "src" / "ai" / "visual.py"), str(content_file),
                 "--output-dir", str(session_dir)],
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=600
            )

        def _run_engagement():
            return subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "src" / "ai" / "engagement.py"), str(content_file),
                 "--output-dir", str(session_dir)],
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=600
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut_vis = executor.submit(_run_visual)
            fut_eng = executor.submit(_run_engagement)
            visual_result = fut_vis.result()
            engagement_result = fut_eng.result()

        if visual_result and visual_result.returncode != 0:
            print(f"[Pipeline {index}] ⚠️ Visual failed (continuing)", flush=True)

        if engagement_result and engagement_result.returncode != 0:
            print(f"[Pipeline {index}] ⚠️ Engagement failed (continuing)", flush=True)
        
        print(f"[Pipeline {index}] Step 5/6: Running QC...", flush=True)
        
        # 9. Run QC autofix
        qc_result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "src" / "qc" / "autofix.py"), str(content_file),
             "--output-dir", str(session_dir), "--auto", "--min-score", "0.80", "--mode", "batch"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=600
        )
        if qc_result.returncode != 0:
            print(f"[Pipeline {index}] ⚠️ QC issues found (check report)", flush=True)
        
        print(f"[Pipeline {index}] Step 6/6: Creating final package...", flush=True)
        
        # 10. Run package
        package_result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "src" / "package.py"), str(content_file),
             "--output-dir", str(session_dir)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=90
        )
        
        if package_result.returncode != 0:
            print(f"[Pipeline {index}] ⚠️ Package failed (continuing)", flush=True)
        else:
            final_channel_id = get_final_channel_id()
            final_file = session_dir / "FINAL.md"
            if final_channel_id and final_file.exists():
                topic = safe_discord_filename(selected_angle.get('title'), "content")
                fmt = safe_discord_filename(content_format, "format")
                filename = f"{topic}_{fmt}_{timestamp}.md"
                message = load_prompt("discord/discord_final.txt").format(
                    angle_title=selected_angle.get('title', 'N/A'),
                    content_format=content_format,
                    filename=filename,
                )
                if send_discord_bot_message(final_channel_id, message, final_file, filename):
                    print(f"[Pipeline {index}] Final sent to Discord Channel B as {filename}", flush=True)
                else:
                    print(f"[Pipeline {index}] Discord final upload failed", flush=True)
            else:
                reason = get_discord_skip_reason(final_channel_id, "final upload")
                if reason:
                    print(f"[Pipeline {index}] {reason}", flush=True)

            if not send_to_buffer(session_dir, content_format, selected_angle):
                print(f"[Pipeline {index}] Warning: Buffer scheduling failed (content still in session_dir)", flush=True)
        
        print(f"[Pipeline {index}] [OK] COMPLETED: {session_dir}", flush=True)
        
        return {
            "success": True,
            "index": index,
            "title": title,
            "format": content_format,
            "output": str(session_dir),
            "pillar": topic_data.get('pillar', 'N/A')
        }
        
    except subprocess.TimeoutExpired as e:
        error_msg = f"Timeout at step: {e.cmd[1] if len(e.cmd) > 1 else 'unknown'}"
        print(f"[Pipeline {index}] ❌ {error_msg}", flush=True)
        return {"success": False, "index": index, "error": error_msg}
    
    except Exception as e:
        error_msg = str(e)[:200]
        print(f"[Pipeline {index}] ❌ {error_msg}", flush=True)
        return {"success": False, "index": index, "error": error_msg}

    finally:
        # Guarantee cleanup of temporary files
        try:
            input_file.unlink(missing_ok=True)
            angle_file.unlink(missing_ok=True)
        except OSError as e:
            print(f"[Pipeline {index}] [!] Cleanup failed: {e}", flush=True)


def main():
    print_header("DAILY AUTO CONTENT GENERATOR")
    
    count = 1
    if "--count" in sys.argv:
        idx = sys.argv.index("--count")
        if idx + 1 < len(sys.argv):
            try:
                count = int(sys.argv[idx + 1])
            except ValueError:
                count = 1
    
    keywords = []
    if "--keywords" in sys.argv:
        idx = sys.argv.index("--keywords")
        if idx + 1 < len(sys.argv):
            keywords_str = sys.argv[idx + 1]
            keywords = [k.strip() for k in keywords_str.split(",")]
    
    topics = generate_topics(keywords=keywords, count=count)
    if not topics:
        print("[!] Failed to generate topics!", file=sys.stderr)
        return 1
    
    start_time = datetime.now()
    results = []
    
    for i, topic in enumerate(topics, 1):
        print(f"\n[*] Processing ({i}/{len(topics)}): [{topic.get('pillar', 'general')}] {topic.get('text', 'N/A')}")
        res = run_single_pipeline(topic, index=i)
        results.append(res)
    
    duration = (datetime.now() - start_time).total_seconds()
    
    successes = [r for r in results if r.get('success')]
    failures = [r for r in results if not r.get('success')]
    
    print_header("EXECUTION SUMMARY")
    print(f"[*] Total time: {duration/60:.1f} minutes ({duration:.0f} seconds)")
    if failures:
        print(f"[!] Status: Completed with failures ({len(successes)} succeeded, {len(failures)} failed)")
    else:
        print(f"[OK] Status: All completed successfully ({len(successes)}/{len(topics)})")
    
    return 0 if len(successes) > 0 else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[!] Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
