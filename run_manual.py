#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Manual Input Pipeline - Option 1
Replaces start.bat with proper error handling and validation
"""

import sys
import json
import subprocess
import random
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Any
import re

from src.utils.discord import get_angle_channel_id, get_discord_skip_reason, get_final_channel_id, safe_discord_filename, send_discord_bot_message
from src.utils.buffer import send_to_buffer
from src.core.prompt_loader import PromptLoader
from src.core.angle_dedup import filter_duplicate_angles, save_selected_angle

PROJECT_ROOT = Path(__file__).resolve().parent
TEMP_DIR = Path(tempfile.mkdtemp(prefix="web3_manual_"))
TEMP_INPUT_FILE = TEMP_DIR / "input.json"
TEMP_ANGLE_FILE = TEMP_DIR / "selected_angle.json"

_prompt_loader = PromptLoader()


def load_prompt(name: str) -> str:
    return _prompt_loader.load(name)


def print_header(title: str):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"   {title}")
    print("=" * 60 + "\n")


def get_user_input() -> dict[str, Any]:
    print_header("INPUT MANUAL - Masukkin Ide Kamu")
    
    topic = input("Topic/Judul: ").strip()
    if not topic:
        print("[!] Topic tidak boleh kosong!")
        sys.exit(1)
    
    context = input("\nContext/Detail (optional, tekan Enter kalo skip): ").strip()
    
    # Mode for manual input - always "manual"
    # strategist.py will auto-detect first-person and apply appropriate overlays
    mode = "manual"
        
    # Don't hardcode pillar - let strategist AI determine from topic
    return {
        "text": topic,  # strategist.py expects 'text' field, not 'topic'
        "context": context,
        "mode": mode
    }


def run_strategist(input_data: dict[str, Any]) -> list[dict[str, Any]]:
    print_header("STEP 1: AI STRATEGIST - Generate 10 Angles")
    print("[*] Generating content angles...\n")
    
    # Create temp input file
    input_file = TEMP_INPUT_FILE
    with open(input_file, 'w', encoding='utf-8') as f:
        json.dump([input_data], f, ensure_ascii=False, indent=2)
    
    print(f"[*] Input file created: {input_file}")
    
    # Run strategist
    try:
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "src" / "ai" / "strategist.py"), str(input_file)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=360  # 6 minutes max - increased for stability
        )
        
        if result.returncode != 0:
            print(f"[!] Strategist failed with exit code {result.returncode}")
            print(f"[!] stderr: {result.stderr}")
            sys.exit(1)
        
        # Parse strategist output (JSON on stdout)
        angles_data = json.loads(result.stdout)
        angles = angles_data.get('angles', [])
        
        if not angles:
            print("[!] No angles generated!")
            sys.exit(1)
        
        print(f"[*] Generated {len(angles)} angles successfully\n")
        return angles
        
    except subprocess.TimeoutExpired:
        print("[!] Strategist timeout after 6 minutes")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[!] Failed to parse strategist output: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[!] Strategist error: {e}")
        sys.exit(1)


def select_angle(angles: list[dict[str, Any]]) -> dict[str, Any]:
    print("=" * 60)
    
    # Display all angles (up to 10)
    display_count = min(len(angles), 10)
    for i, angle in enumerate(angles[:display_count], 1):
        print(f"\n[{i}] {angle.get('title', 'Untitled')}")
        print(f"    Hook: {angle.get('hook', 'No hook')[:80]}...")
        print(f"    Pillar: {angle.get('content_pillar', 'N/A')}")
        print(f"    Scores: Viral={angle.get('viral_score', 0)}")
        
        # Display suggested formats
        suggested_formats = angle.get('suggested_formats', [])
        if suggested_formats:
            formats_str = ', '.join(suggested_formats)
            print(f"    Recommended: {formats_str}")
    
    print("\n" + "=" * 60)
    
    # Get user choice
    choice = input(f"\nPilih angle nomor berapa? (1-{display_count}, atau Enter untuk top score): ").strip()
    
    if not choice:
        selected = angles[0]
        print(f"[*] Auto-selected top angle: {selected.get('title')}")
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(angles):
                selected = angles[idx]
                print(f"[*] Selected angle #{choice}: {selected.get('title')}")
            else:
                print(f"[!] Invalid choice, using angle #1")
                selected = angles[0]
        except ValueError:
            print(f"[!] Invalid input, using angle #1")
            selected = angles[0]
    
    # Save selected angle
    angle_file = TEMP_ANGLE_FILE
    with open(angle_file, 'w', encoding='utf-8') as f:
        json.dump(selected, f, ensure_ascii=False, indent=2)
    
    return selected


def select_format(angle: dict[str, Any]) -> str:
    """Let user select format - shows ALL formats with recommended first"""
    print_header("PILIH FORMAT CONTENT")
    
    # Get recommended formats from angle
    recommended = angle.get('suggested_formats', [])
    
    # All available formats in the system
    all_formats = [
        'Thread', 'Image', 'Single Tweet', 'Poll'
    ]
    
    # Build format list: recommended first, then others
    formats_list = []
    
    # Add recommended formats first (with ⭐ marker)
    for fmt in recommended:
        if fmt in all_formats:
            formats_list.append((fmt, True))  # True = recommended
    
    # Add remaining formats
    for fmt in all_formats:
        if fmt not in recommended:
            formats_list.append((fmt, False))  # False = not recommended
    
    # Display formats
    for i, (fmt, is_recommended) in enumerate(formats_list, 1):
        marker = "⭐" if is_recommended else "  "
        print(f"{marker} [{i}] {fmt}")
    
    print()
    choice = input(f"Pilih format (1-{len(formats_list)}, atau Enter untuk recommended pertama): ").strip()
    
    if not choice:
        selected_format = formats_list[0][0]  # First format (most recommended)
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(formats_list):
                selected_format = formats_list[idx][0]
            else:
                print(f"[!] Invalid choice, using recommended format")
                selected_format = formats_list[0][0]
        except ValueError:
            print(f"[!] Invalid input, using recommended format")
            selected_format = formats_list[0][0]
    
    print(f"[*] Format dipilih: {selected_format}\n")
    
    # Update angle with format
    angle['format'] = selected_format
    with open(TEMP_ANGLE_FILE, 'w', encoding='utf-8') as f:
        json.dump(angle, f, ensure_ascii=False, indent=2)
    
    return selected_format


def create_session_folder(angle: dict[str, Any], content_format: str) -> Path:
    """Create session folder for organized output"""
    print("[*] Creating session folder...")
    
    title = angle.get('title', 'content')
    
    # Clean title for folder name
    title = re.sub(r'\[[\w\s]+\d+\]', '', title)  # Remove tags
    title = re.sub(r'^\s*[\w]+\s+\d+\s*[-:]?\s*', '', title)  # Remove leading numbers
    safe_title = re.sub(r'[^a-zA-Z0-9\s-]', '', title)[:40].strip().replace(' ', '_')
    safe_title = safe_title if safe_title else 'content'
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    session_dir = PROJECT_ROOT / "output" / f"{safe_title}_{content_format}_{timestamp}"
    
    session_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy angle to session folder
    import shutil
    shutil.copy(TEMP_ANGLE_FILE, session_dir / "angle.json")
    
    print(f"[*] Session: {session_dir}\n")
    return session_dir


def run_writer(session_dir: Path) -> bool:
    print_header("STEP 2: AI WRITER - Generate Full Content")
    print("[*] Generating content...\n")
    
    try:
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "src" / "ai" / "writer.py"), str(TEMP_ANGLE_FILE), 
             "--output-dir", str(session_dir)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=900  # 15 minutes max - increased for slow models
        )
        
        if result.returncode != 0:
            print(f"[!] Writer failed with exit code {result.returncode}")
            print(f"[!] Output: {result.stdout}")
            print(f"[!] Errors: {result.stderr}")
            return False
        
        print("[*] Writer completed successfully")
        return True
        
    except subprocess.TimeoutExpired:
        print("[!] Writer timeout after 15 minutes")
        return False
    except Exception as e:
        print(f"[!] Writer error: {e}")
        return False


def validate_writer_output(session_dir: Path) -> bool:
    content_file = session_dir / "content.txt"
    
    if not content_file.exists():
        print(f"[!] Content file not found: {content_file}")
        return False
    
    # Check file is not empty
    if content_file.stat().st_size == 0:
        print(f"[!] Content file is empty")
        return False
    
    print(f"[*] Content file validated: {content_file}")
    return True


def run_visual(session_dir: Path, content_format: str) -> bool:
    print_header("STEP 3: VISUAL DESIGNER - Generate Visual Brief")
    
    content_file = session_dir / "content.txt"
    
    try:
        # visual_ai.py needs content_file and output-dir for proper file placement
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "src" / "ai" / "visual.py"), str(content_file), 
             "--output-dir", str(session_dir)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=600  # 10 minutes - increased for slow/thinking models
        )
        
        if result.returncode != 0:
            print(f"[!] Visual AI failed: {result.stderr}")
            return False
        
        print("[*] Visual brief generated")
        return True
        
    except Exception as e:
        print(f"[!] Visual AI error: {e}")
        return False


def run_engagement(session_dir: Path) -> bool:
    print_header("STEP 4: ENGAGEMENT PLANNER - Generate Posting Strategy")
    
    content_file = session_dir / "content.txt"
    
    try:
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "src" / "ai" / "engagement.py"), str(content_file),
             "--output-dir", str(session_dir)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=600  # 10 minutes - increased for slow/thinking models
        )
        
        if result.returncode != 0:
            print(f"[!] Engagement AI failed: {result.stderr}")
            return False
        
        print("[*] Engagement plan generated")
        return True
        
    except Exception as e:
        print(f"[!] Engagement AI error: {e}")
        return False


def run_qc(session_dir: Path) -> bool:
    print_header("STEP 5: QUALITY CONTROL - Auto-check & Fix")
    
    content_file = session_dir / "content.txt"
    
    try:
        # qc_autofix.py needs --auto flag to run without prompts
        print("[*] Running QC checks...")
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "src" / "qc" / "autofix.py"), str(content_file),
             "--output-dir", str(session_dir), "--auto", "--min-score", "0.80", "--mode", "manual"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=600  # 10 minutes - increased for slow/thinking models
        )
        
        if result.returncode != 0:
            print(f"[!] QC check failed: {result.stderr}")
            return False
        
        # Show full QC output
        print(result.stdout)
        
        # Parse and display QC summary report
        stdout_lines = result.stdout.split('\n')
        
        # Extract key information from stdout
        qc_triggered = True  # Always triggered in our pipeline
        format_detected = "Unknown"
        initial_score = 0.0
        final_score = 0.0
        passed = False
        issues = []
        
        for line in stdout_lines:
            if line.startswith("[*] Format:"):
                format_detected = line.split("Format:")[1].strip()
            elif line.startswith("[*] Score:") or line.startswith("[*] New Score:"):
                # Extract score (e.g., "0.85/1.00 (85%)")
                score_text = line.split(":")[1].strip()
                if "/" in score_text:
                    score_value = float(score_text.split("/")[0].strip())
                    if "New Score:" in line:
                        final_score = score_value
                    elif initial_score == 0.0:
                        initial_score = score_value
            elif line.startswith("  - ") and not line.startswith("  - ["):
                # Issue line
                issues.append(line.strip()[2:])
            elif "✅ QC" in line or "PASSED" in line:
                passed = True
        
        # If no final score, use initial score
        if final_score == 0.0:
            final_score = initial_score
        
        # Display QC Report Summary
        print("\n" + "=" * 60)
        print("   QC REPORT SUMMARY")
        print("=" * 60)
        print(f"QC Triggered:    {'✅ YES' if qc_triggered else '❌ NO'}")
        print(f"Format Detected: {format_detected}")
        print(f"Initial Score:   {initial_score:.2f}/1.00 ({int(initial_score * 100)}%)")
        if final_score != initial_score:
            print(f"Final Score:     {final_score:.2f}/1.00 ({int(final_score * 100)}%)")
            print(f"Improvement:     +{int((final_score - initial_score) * 100)}%")
        print(f"Status:          {'✅ PASSED' if passed else '❌ NEEDS WORK'}")
        
        if issues:
            print(f"\nIssues Found ({len(issues)}):")
            for issue in issues[:5]:  # Show first 5 issues
                print(f"  • {issue}")
            if len(issues) > 5:
                print(f"  ... and {len(issues) - 5} more")
        else:
            print("\nIssues Found:    None ✅")
        
        print("=" * 60 + "\n")
        
        print("[*] QC checks completed")
        return True
        
    except Exception as e:
        print(f"[!] QC error: {e}")
        return False


def run_package(session_dir: Path) -> bool:
    print_header("STEP 6: FINAL PACKAGE - Combine All Outputs")
    
    content_file = session_dir / "content.txt"
    
    try:
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "src" / "package.py"), str(content_file),
             "--output-dir", str(session_dir)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=90  # 1.5 minutes - increased for stability
        )
        
        if result.returncode != 0:
            print(f"[!] Package failed: {result.stderr}")
            return False
        
        print("[*] Final package created")
        return True
        
    except Exception as e:
        print(f"[!] Package error: {e}")
        return False


def main():
    """Main pipeline orchestrator"""
    print("=" * 60)
    print("   WEB3 CONTENT PIPELINE - MANUAL INPUT")
    print("=" * 60)
    
    # Step 1: Get input
    input_data = get_user_input()
    
    # Step 2: Run strategist with retry to ensure unique angles
    TARGET_ANGLES = 8      # Target number of angles (more realistic)
    MINIMUM_ANGLES = 4     # Minimum acceptable angles (flexible for partial success)
    MAX_ATTEMPTS = 5       # Maximum retry attempts (increased for better success rate)
    angles = []
    angles_seen_titles = set()  # Track titles to avoid intra-batch duplicates
    attempt = 0
    stalled_attempts = 0
    
    print_header("STEP 2: ANGLE GENERATION WITH DEDUP")
    
    while len(angles) < TARGET_ANGLES and attempt < MAX_ATTEMPTS:
        # Generate new angles
        print(f"[*] Attempt {attempt + 1}: Generating angles...\n")
        new_angles = run_strategist(input_data)
        
        # Filter duplicates against history
        new_unique = filter_duplicate_angles(new_angles, threshold=0.8, verbose=(attempt == 0))
        
        # Add to collection, avoiding intra-batch duplicates
        added_this_attempt = 0
        for angle in new_unique:
            title = angle.get('title', '')
            if title and title not in angles_seen_titles:
                angles.append(angle)
                angles_seen_titles.add(title)
                added_this_attempt += 1
        stalled_attempts = stalled_attempts + 1 if added_this_attempt == 0 else 0
        if stalled_attempts >= 2:
            print("\n[!] No new unique angles after 2 attempts. Using current set.\n")
            break
        
        if len(angles) < TARGET_ANGLES and attempt < MAX_ATTEMPTS - 1:
            needed = TARGET_ANGLES - len(angles)
            print(f"\n[*] Current: {len(angles)} unique angles. Need {needed} more. Regenerating...\n")
        
        attempt += 1
    
    # Cap at target count
    angles = angles[:TARGET_ANGLES]
    
    # Validate we have minimum viable angles
    if len(angles) < MINIMUM_ANGLES:
        print(f"[!] Could not generate minimum {MINIMUM_ANGLES} unique angles after {MAX_ATTEMPTS} attempts!")
        print(f"[!] Only got {len(angles)} angle(s). Try a different topic or reset angle history.")
        sys.exit(1)
    
    print(f"\n[*] ✅ Final: {len(angles)} unique angles ready for selection (minimum {MINIMUM_ANGLES} needed)\n")
    
    # Step 3: Select angle
    selected_angle = select_angle(angles)
    
    # Step 3.5: Track selected angle for deduplication
    save_selected_angle(selected_angle)
    
    # Step 4: Select format
    content_format = select_format(selected_angle)
    
    # Step 5: Create session folder
    session_dir = create_session_folder(selected_angle, content_format)
    angle_channel_id = get_angle_channel_id()
    if angle_channel_id:
        message = load_prompt("discord/discord_angle_manual.txt").format(
            angle_title=selected_angle.get('title', 'N/A'),
            angle_hook=str(selected_angle.get('hook', 'N/A'))[:100],
            angle_pillar=selected_angle.get('content_pillar') or selected_angle.get('pillar', 'N/A'),
            content_format=content_format,
        )

        if send_discord_bot_message(angle_channel_id, message, session_dir / "angle.json"):
            print("[*] angle.json sent to Discord Channel A")
        else:
            print("[!] Failed to send angle.json to Discord")
    else:
        reason = get_discord_skip_reason(angle_channel_id, "angle upload")
        if reason:
            print(reason)
    
    # Step 6: Run writer
    if not run_writer(session_dir):
        print("\n[!] Pipeline failed at writer stage")
        sys.exit(1)
    
    # Step 7: Validate writer output
    if not validate_writer_output(session_dir):
        print("\n[!] Pipeline failed: writer output validation failed")
        sys.exit(1)
    
    # Step 8: Run visual (format-dependent probability)
    should_generate_visual = False
    
    if content_format in ['Thread', 'Image']:
        # 100% probability - always generate for these formats
        should_generate_visual = True
        print(f"[*] Visual generation: 100% (format: {content_format})")
    elif content_format in ['Single Tweet', 'Poll']:
        # 60% probability for these formats
        if random.random() < 0.6:
            should_generate_visual = True
            print(f"[*] Visual generation: Selected (60% probability, format: {content_format})")
        else:
            print(f"[*] Visual generation: Skipped (40% probability, format: {content_format})")
    else:
        # Unknown format - default to always generate
        should_generate_visual = True
        print(f"[*] Visual generation: 100% (unknown format: {content_format})")
    
    if should_generate_visual:
        if not run_visual(session_dir, content_format):
            print("\n[!] Warning: Visual generation failed, but continuing pipeline")
    
    # Step 9: Run engagement
    if not run_engagement(session_dir):
        print("\n[!] Warning: Engagement planning failed, but continuing pipeline")
    
    # Step 10: Run QC
    if not run_qc(session_dir):
        print("\n[!] Warning: QC checks failed, but continuing pipeline")
    
    # Step 11: Run package
    if not run_package(session_dir):
        print("\n[!] Warning: Final packaging failed")
        print(f"[*] Content still available in: {session_dir}")
    else:
        if not send_to_buffer(session_dir, content_format, selected_angle):
            print("[!] Warning: Buffer scheduling failed (content still in session_dir)")

        final_channel_id = get_final_channel_id()
        if final_channel_id:
            final_file = session_dir / "FINAL.md"
            if final_file.exists():
                topic = safe_discord_filename(selected_angle.get('title'), "content")
                fmt = safe_discord_filename(content_format, "format")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{topic}_{fmt}_{timestamp}.md"
                message = load_prompt("discord/discord_final.txt").format(
                    angle_title=selected_angle.get('title', 'N/A'),
                    content_format=content_format,
                    filename=filename,
                )

                if send_discord_bot_message(final_channel_id, message, final_file, filename):
                    print(f"[*] Final package sent to Discord Channel B as {filename}")
                else:
                    print("[!] Failed to send final package to Discord")
        else:
            reason = get_discord_skip_reason(final_channel_id, "final upload")
            if reason:
                print(reason)
    
    print("\n" + "=" * 60)
    print(f"[OK] Pipeline completed successfully!")
    print(f"[OK] Output: {session_dir}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[!] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
