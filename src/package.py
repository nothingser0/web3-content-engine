#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import json
from pathlib import Path
from datetime import datetime
import re

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
else:
    pass


def extract_generation_and_dreamina_prompts(visual_content: str) -> str:
    if not visual_content:
        return ""
    
    lines = []
    in_generation_prompt = False
    in_dreamina_safe_prompt = False
    current_section = []
    
    for line in visual_content.split('\n'):
        # Check for section headers
        if line.startswith('### GENERATION PROMPT'):
            # Save previous dreamina safe prompt section if exists
            if in_dreamina_safe_prompt and current_section:
                lines.extend(current_section)
                lines.append('')
                current_section = []
            
            in_generation_prompt = True
            in_dreamina_safe_prompt = False
            current_section = [line]
        elif line.startswith('### DREAMINA SAFE PROMPT'):
            # Save previous generation prompt section if exists
            if in_generation_prompt and current_section:
                lines.extend(current_section)
                lines.append('')
                current_section = []
            
            in_dreamina_safe_prompt = True
            in_generation_prompt = False
            current_section = [line]
        elif line.startswith('###'):
            # Other section - stop capturing
            if in_generation_prompt and current_section:
                lines.extend(current_section)
                lines.append('')
            if in_dreamina_safe_prompt and current_section:
                lines.extend(current_section)
                lines.append('')
            
            in_generation_prompt = False
            in_dreamina_safe_prompt = False
            current_section = []
        elif in_generation_prompt or in_dreamina_safe_prompt:
            # Continue capturing lines in current section
            current_section.append(line)
    
    # Save final section if exists
    if (in_generation_prompt or in_dreamina_safe_prompt) and current_section:
        lines.extend(current_section)
    
    return '\n'.join(lines).strip()


def find_related_files(content_file: str, output_dir=None):
    """Find visual and engagement files related to content file"""
    content_path = Path(content_file)
    
    if output_dir:
        # Session folder mode: look for simple filenames in output_dir
        session_dir = Path(output_dir)
        visual_file = session_dir / "visual.txt" if (session_dir / "visual.txt").exists() else None
        engagement_file = session_dir / "engagement.txt" if (session_dir / "engagement.txt").exists() else None
        qc_file = session_dir / "qc_report.txt" if (session_dir / "qc_report.txt").exists() else None
        return visual_file, engagement_file, qc_file
    
    # Legacy mode: look for timestamp-based files in separate directories
    base_dir = content_path.parent.parent  # Go up from output/writer/ to output/
    
    # Extract topic and timestamp from content filename
    filename = content_path.stem
    if '_content_' in filename:
        topic = filename.split('_content_')[0]
    else:
        return None, None, None
    
    # Find visual, engagement, and QC files in their respective folders
    visual_dir = base_dir / 'visual'
    engagement_dir = base_dir / 'engagement'
    qc_dir = base_dir / 'qc'
    
    visual_files = list(visual_dir.glob(f"{topic}_visual_*.txt")) if visual_dir.exists() else []
    engagement_files = list(engagement_dir.glob(f"{topic}_engagement_*.txt")) if engagement_dir.exists() else []
    qc_files = list(qc_dir.glob(f"{topic}_qc_report_*.txt")) if qc_dir.exists() else []
    
    # Get most recent
    visual_file = sorted(visual_files, key=lambda x: x.stat().st_mtime, reverse=True)[0] if visual_files else None
    engagement_file = sorted(engagement_files, key=lambda x: x.stat().st_mtime, reverse=True)[0] if engagement_files else None
    qc_file = sorted(qc_files, key=lambda x: x.stat().st_mtime, reverse=True)[0] if qc_files else None
    
    return visual_file, engagement_file, qc_file

def generate_final_package(content_file: str, output_dir=None):
    """Generate FINAL package file with improved structure"""
    content_path = Path(content_file)
    
    # Read content
    with open(content_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find related files
    visual_file, engagement_file, qc_file = find_related_files(content_file, output_dir)
    
    # Read visual brief
    visual_content = ""
    if visual_file and visual_file.exists():
        with open(visual_file, 'r', encoding='utf-8') as f:
            visual_content = f.read()
    
    # Read engagement strategy
    engagement_content = ""
    if engagement_file and engagement_file.exists():
        with open(engagement_file, 'r', encoding='utf-8') as f:
            engagement_content = f.read()
    
    # Read QC report
    qc_content = ""
    if qc_file and qc_file.exists():
        with open(qc_file, 'r', encoding='utf-8') as f:
            qc_content = f.read()
    
    # Extract topic and format from filename or angle.json
    filename = content_path.stem
    topic = "Content"
    content_format = "Unknown"
    angle_title = ""
    
    # Try to read angle.json for better info
    if output_dir:
        angle_json_path = Path(output_dir) / "angle.json"
        if angle_json_path.exists():
            try:
                with open(angle_json_path, 'r', encoding='utf-8') as f:
                    angle_data = json.load(f)
                    angle_title = angle_data.get('title', '')
                    content_format = angle_data.get('format', 'Unknown')
                    topic = angle_title[:50] if angle_title else "Content"
            except (json.JSONDecodeError, OSError) as e:
                print(f"[!] Failed to read angle.json: {e}", file=sys.stderr)
    
    # Fallback: extract from filename
    if '_content_' in filename:
        topic_part = filename.split('_content_')[0]
        if '__' in topic_part:
            parts = topic_part.split('__', 1)
            if len(parts) > 1:
                content_format = parts[0]
                topic = parts[1].replace('_', ' ')
        else:
            topic = topic_part.replace('_', ' ')
    
    # Detect format from content if still unknown
    if content_format == "Unknown":
        if '**SINGLE TWEET:**' in content:
            content_format = 'Single Tweet'
        elif '**THREAD:**' in content or 'Tweet 1:' in content:
            content_format = 'Thread'
        elif '**IMAGE:**' in content:
            content_format = 'Image'
        elif '**POLL:**' in content:
            content_format = 'Poll'
    
    # Extract posting time from engagement
    posting_time = "TBD"
    if engagement_content:
        import re
        time_match = re.search(r'POSTING TIME:\s*(.+?)(?:\n|$)', engagement_content)
        if time_match:
            posting_time = time_match.group(1).strip()
    
    # Parse QC info
    qc_score = "N/A"
    qc_passed = False
    if qc_content:
        import re
        score_match = re.search(r'Score:\s*(\d+\.\d+)', qc_content)
        if score_match:
            qc_score = f"{float(score_match.group(1)):.2f}"
        qc_passed = '✅' in qc_content or 'PASSED' in qc_content
    
    # Build package with clean structure
    lines = [
        "=" * 72,
        "WEB3 CONTENT PIPELINE - FINAL PACKAGE",
        "=" * 72,
        f"Topic:          {topic}",
        f"Angle:          {angle_title if angle_title else topic}",
        f"Format:         {content_format}",
        f"Generated:      {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Scheduled:      {posting_time}",
        "",
        "STATUS: [ ] Draft  [ ] Ready  [ ] Scheduled  [ ] Posted",
        f"QC Score: {qc_score}/1.00  |  QC Passed: {qc_passed}",
        "",
        "=" * 72,
        "1. CONTENT",
        "=" * 72,
        "",
        content.strip(),
        "",
        "=" * 72,
        "2. VISUAL",
        "=" * 72,
        "",
    ]
    
    # Add visual section
    if visual_content:
        # Extract only GENERATION PROMPT and DREAMINA SAFE PROMPT sections
        extracted = extract_generation_and_dreamina_prompts(visual_content)
        if extracted:
            lines.append(extracted)
        else:
            # Fallback to full content if extraction fails
            lines.append(visual_content.strip())
    else:
        if content_format in ["Single Tweet", "Poll"]:
            lines.append("VISUAL: Skipped (probability-based - no image needed)")
        else:
            lines.append("[Visual not generated]")
    
    lines.extend([
        "",
        "=" * 72,
        "3. ENGAGEMENT STRATEGY",
        "=" * 72,
        "PLATFORM: Twitter/X",
        "",
    ])
    
    # Add engagement section
    if engagement_content:
        lines.append(engagement_content.strip())
    else:
        lines.append("[Engagement strategy not generated]")
    
    lines.extend([
        "",
        "=" * 72,
        "4. QC NOTES",
        "=" * 72,
        f"SCORE: {qc_score}/1.00",
        f"PASSED: {qc_passed}",
        "",
    ])
    
    # Add QC details
    if qc_content:
        lines.append(qc_content.strip())
    else:
        lines.append("No QC report available.")
    
    # Add performance tracking section
    lines.extend([
        "",
        "=" * 72,
        "5. PERFORMANCE (isi setelah posting)",
        "=" * 72,
        "Posted At:",
        "Impressions:",
        "Engagements:",
        "Replies:",
        "Saves/Bookmarks:",
        "Best performing element:",
        "Notes for next content:",
        "",
    ])
    
    package = "\n".join(lines)
    
    # Save FINAL package
    if output_dir:
        # Session folder mode: simple filename
        session_dir = Path(output_dir)
        session_dir.mkdir(parents=True, exist_ok=True)
        final_file = session_dir / "FINAL.md"
    else:
        # Legacy mode: timestamp-based in output/final/
        final_dir = Path(__file__).parent.parent / 'output' / 'final'
        final_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        topic_filename = topic.replace(' ', '_')[:30]
        final_file = final_dir / f"{topic_filename}_FINAL_{timestamp}.md"
    
    with open(final_file, 'w', encoding='utf-8') as f:
        _ = f.write(package)
    
    return final_file

def main():
    import argparse
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Package generator - Creates FINAL package')
    parser.add_argument('content_file', help='Input content file')
    parser.add_argument('--output-dir', help='Session output directory (optional)')
    args = parser.parse_args()
    
    if not os.path.exists(args.content_file):
        print(f"[!] File not found: {args.content_file}")
        sys.exit(1)
    
    print("[*] Generating FINAL package...")
    final_file = generate_final_package(args.content_file, args.output_dir)
    print(f"[*] FINAL package saved: {final_file}")
    print(f"\n[OK] All files ready to use!")

if __name__ == "__main__":
    main()
