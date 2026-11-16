#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QC Format-Specific - Quality Control with Format-Aware Checks
"""

import sys
import re
from pathlib import Path
from typing import TypedDict

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from src.utils.common import setup_console_encoding
else:
    from ..utils.common import setup_console_encoding

setup_console_encoding()

TIME_SENSITIVE_PATTERNS = [
    r'\bbesok\b',
    r'\bminggu depan\b',
    r'\bhari ini\b',
    r'\bmalam ini\b',
    r'\bupdate terbaru\b',
    r'\blive now\b',
    r'\bclaim now\b',
]

FAKE_PERSONAL_PATTERNS = [
    r'\baku pernah\b',
    r'\baku rugi\b',
    r'\baku profit\b',
    r'\baku dulu\b',
    r'\bcara aku\b',
    r'\baku pakai\b',
    r'\baku pake\b',
    r'\bsekarang aku\b',
    r'\bpengalaman aku\b',
    r'\btested\s*&\s*proven\b',
]

NICHE_KEYWORDS = [
    'web3', 'crypto', 'airdrop', 'onchain', 'wallet', 'token', 'tokenomics',
    'defi', 'passport', 'gitcoin', 'attestation', 'scam', 'rug pull', 'gas fee',
    'whitepaper', 'chatgpt', 'claude', 'ai', 'perplexity', 'dao'
]

AI_USEFULNESS_KEYWORDS = [
    'tool', 'tools', 'prompt', 'workflow', 'summary', 'summarize', 'ringkas',
    'whitepaper', 'compare', 'filter', 'research', 'riser', 'riset'
]

AMBIGUOUS_CTA_PATTERNS = [
    r'\bdrop angka\b',
    r'\bdrop di (komen|reply)\b',
    r'\bdrop dong\b',
]


class QCResult(TypedDict):
    format: str
    score: float
    issues: list[str]
    passed: bool


BASE_PASS_SCORE = 0.70
PUBLISH_READY_SCORE = 0.80
THREAD_MIN_TWEETS = 5
THREAD_MAX_TWEETS = 12


def get_qc_status(score: float, passed: bool) -> str:
    """Return human-readable QC status without hiding below-target scores."""
    if not passed:
        return "FAIL"
    if score < PUBLISH_READY_SCORE:
        return "PASS BELOW TARGET"
    return "PASS"


def get_qc_summary_message(score: float, passed: bool) -> str:
    """Return console summary message for QC result."""
    if not passed:
        return "❌ QC FAILED - Improvements needed"
    if score < PUBLISH_READY_SCORE:
        return "⚠️ QC BASE PASS ONLY - Below publish target (80%), improve before publish"
    return "✅ QC PASSED - Content ready to publish!"


def run_global_qc_checks(content: str, mode: str = "batch") -> tuple[list[str], float]:
    issues: list[str] = []
    score_delta = 0.0
    content_lower = content.lower()

    if mode == "batch" and any(re.search(pattern, content_lower) for pattern in TIME_SENSITIVE_PATTERNS):
        issues.append("❌ Time-sensitive wording found (content should stay evergreen)")
        score_delta -= 0.25
    elif mode == "batch":
        issues.append("✅ Evergreen framing looks safe")
    else:
        issues.append("✅ Mode allows timely/source-tied framing")

    if mode != "manual" and any(re.search(pattern, content_lower) for pattern in FAKE_PERSONAL_PATTERNS):
        issues.append("❌ Possible fake personal claim / autobiographical framing found")
        score_delta -= 0.25
    elif mode != "manual":
        issues.append("✅ No obvious fake personal claims")
    else:
        issues.append("✅ Manual mode allows first-person framing")

    if any(re.search(pattern, content_lower) for pattern in AMBIGUOUS_CTA_PATTERNS):
        issues.append("⚠️ CTA looks ambiguous (make requested action more specific)")
        score_delta -= 0.10

    niche_hits = [keyword for keyword in NICHE_KEYWORDS if keyword in content_lower]
    if len(niche_hits) < 2:
        issues.append("⚠️ Weak niche fit (content should clearly feel Web3/Airdrop/AI)")
        score_delta -= 0.15
    else:
        issues.append(f"✅ Niche fit present: {min(len(niche_hits), 5)}+ relevant keywords")

    ai_mentioned = bool(re.search(r'\bai\b', content_lower)) or any(
        tool in content_lower for tool in ('chatgpt', 'claude', 'perplexity', 'notebooklm')
    )
    if ai_mentioned and not any(keyword in content_lower for keyword in AI_USEFULNESS_KEYWORDS):
        issues.append("⚠️ AI mention feels generic (add practical AI workflow/tool use case)")
        score_delta -= 0.10

    return issues, score_delta

def detect_format(content):
    """Detect content format from markers"""
    if '**SINGLE TWEET:**' in content:
        return 'Single Tweet'
    elif '**SHORT THREAD:**' in content:
        return 'Short Thread'
    elif '**THREAD:**' in content:
        return 'Thread'
    elif '**IMAGE:**' in content or '**CAROUSEL' in content or re.search(r'\*\*SLIDE\s+1(?:\s*[-:]\s*|\s+)', content):
        return 'Image'
    elif '**POLL:**' in content:
        return 'Poll'
    else:
        return 'Unknown'

def qc_single_tweet(content: str, mode: str = "batch") -> QCResult:
    """QC checks specific to Single Tweet"""
    issues = []
    score = 1.0
    
    # Remove format marker for length check
    clean_content = content.replace('**SINGLE TWEET:**', '').strip()
    
    # 1. Length check (<280 chars)
    if len(clean_content) > 280:
        issues.append(f"❌ Too long: {len(clean_content)} chars (max 280)")
        score -= 0.3
    elif len(clean_content) > 260:
        issues.append(f"⚠️ Near limit: {len(clean_content)} chars (consider shortening)")
        score -= 0.1
    else:
        issues.append(f"✅ Length OK: {len(clean_content)} chars")
    
    # 2. Hook check (first 50 chars should be strong)
    first_line = clean_content.split('\n')[0]
    if len(first_line) < 20:
        issues.append("⚠️ Hook too short (first line <20 chars)")
        score -= 0.1
    
    # 3. CTA check
    cta_markers = ['?', 'drop', 'reply', 'tag', 'share', 'rt', 'retweet', '👇', '🔥', 'komen', 'comment']
    has_cta = any(marker in clean_content.lower() for marker in cta_markers)
    if not has_cta:
        issues.append("⚠️ No clear CTA (add question or call-to-action)")
        score -= 0.2
    else:
        issues.append("✅ CTA present")
    
    # 4. Hashtags check (2-3 max for single tweet)
    hashtag_count = len(re.findall(r'#\w+', clean_content))
    if hashtag_count > 3:
        issues.append(f"⚠️ Too many hashtags: {hashtag_count} (max 3 for single tweet)")
        score -= 0.1
    elif hashtag_count == 0:
        issues.append("✅ No hashtags (allowed)")
    else:
        issues.append(f"✅ Hashtags OK: {hashtag_count}")
    
    # 5. Surabaya style check
    surabaya_words = ['cok', 'rek', 'ojo', 'piye', 'enak tenan', 'apik', 'aku', 'kamu']
    found_words = [w for w in surabaya_words if w in content.lower()]
    if len(found_words) < 2:
        issues.append(f"⚠️ Weak Surabaya style (only {len(found_words)} slang words)")
        score -= 0.1
    else:
        issues.append(f"✅ Surabaya style: {len(found_words)} slang words")

    global_issues, global_delta = run_global_qc_checks(clean_content, mode=mode)
    issues.extend(global_issues)
    score += global_delta
    
    return {
        'format': 'Single Tweet',
        'score': max(0, score),
        'issues': issues,
        'passed': score >= BASE_PASS_SCORE
    }

def qc_thread(content: str, mode: str = "batch") -> QCResult:
    """QC checks specific to Thread"""
    issues = []
    score = 1.0

    tweet_header_pattern = r'(?im)^\*\*Tweet\s+(\d+)(?:\s*[-:(][^\n]*?)?\*\*'
    
    # 1. Structure check (Tweet markers)
    tweet_markers = re.findall(tweet_header_pattern, content)
    tweet_count = len(tweet_markers)
    
    if tweet_count < THREAD_MIN_TWEETS:
        issues.append(f"⚠️ Too short: {tweet_count} tweets (recommended {THREAD_MIN_TWEETS}-{THREAD_MAX_TWEETS})")
        score -= 0.2
    elif tweet_count > THREAD_MAX_TWEETS:
        issues.append(f"⚠️ Too long: {tweet_count} tweets (recommended {THREAD_MIN_TWEETS}-{THREAD_MAX_TWEETS})")
        score -= 0.1
    else:
        issues.append(f"✅ Thread length OK: {tweet_count} tweets")
    
    # 2. Hook check (Tweet 1)
    tweet_1_match = re.search(r'(?ims)^\*\*Tweet\s+1(?:\s*[-:(][^\n]*?)?\*\*\s*(.+?)(?=^\*\*Tweet\s+2|\Z)', content)
    if tweet_1_match:
        tweet_1 = tweet_1_match.group(1).strip()
        if len(tweet_1) < 50:
            issues.append("⚠️ Tweet 1 hook too short")
            score -= 0.1
        else:
            issues.append("✅ Tweet 1 hook strong")
    
    # 3. CTA check (last tweet)
    if tweet_count > 0:
        last_tweet_pattern = rf'(?ims)^\*\*Tweet\s+{tweet_count}(?:\s*[-:(][^\n]*?)?\*\*\s*(.+?)\Z'
        last_tweet_match = re.search(last_tweet_pattern, content)
        if last_tweet_match:
            last_tweet = last_tweet_match.group(1).strip()
            cta_markers = ['drop', 'reply', 'tag', 'share', 'rt', 'retweet', '?', 'komen', 'comment']
            has_cta = any(marker in last_tweet.lower() for marker in cta_markers)
            if not has_cta:
                issues.append("⚠️ Last tweet missing CTA")
                score -= 0.2
            else:
                issues.append("✅ CTA in last tweet")
    
    # 4. Hashtags check (should be in last tweet)
    hashtags = re.findall(r'#\w+', content)
    if len(hashtags) == 0:
        issues.append("✅ No hashtags (allowed)")
    elif len(hashtags) > 5:
        issues.append(f"⚠️ Too many hashtags: {len(hashtags)} (max 5)")
        score -= 0.1
    else:
        issues.append(f"✅ Hashtags OK: {len(hashtags)}")
    
    # 5. Surabaya style check
    surabaya_words = ['cok', 'rek', 'ojo', 'piye', 'enak tenan', 'apik', 'aku', 'kamu']
    found_words = [w for w in surabaya_words if w in content.lower()]
    if len(found_words) < 3:
        issues.append(f"⚠️ Weak Surabaya style (only {len(found_words)} slang words)")
        score -= 0.1
    else:
        issues.append(f"✅ Surabaya style: {len(found_words)} slang words")

    global_issues, global_delta = run_global_qc_checks(content, mode=mode)
    issues.extend(global_issues)
    score += global_delta
    
    return {
        'format': 'Thread',
        'score': max(0, score),
        'issues': issues,
        'passed': score >= 0.7
    }

def qc_image(content: str, mode: str = "batch") -> QCResult:
    """QC checks specific to Image"""
    issues = []
    score = 1.0
    # Support both formats: ## SLIDE 1: / ## SLIDE 1 - COVER / **Slide 1 - Cover**
    slide_header_pattern = r'(?im)^(?:##\s*SLIDE\s+(\d+)\s*(?:-|:)|\*\*Slide\s+(\d+)\s*[-:])'
    
    # 1. Structure check (Slide markers)
    slide_markers = re.findall(slide_header_pattern, content)
    slide_count = len(slide_markers)
    
    if slide_count < 2:
        issues.append(f"⚠️ Too few slides: {slide_count} (recommended 2-4)")
        score -= 0.2
    elif slide_count > 4:
        issues.append(f"❌ Too many slides: {slide_count} (max 4)")
        score -= 0.3
    else:
        issues.append(f"✅ Slide count OK: {slide_count}")
    
    # 2. Cover slide check (Slide 1)
    if re.search(r'(?im)^(?:##\s*SLIDE\s+1\s*(?:-|:)\s*(?:COVER|TITLE)|\*\*Slide\s+1\s*[-:]\s*(?:Cover|COVER))', content):
        issues.append("✅ Cover slide present")
    else:
        issues.append("⚠️ No cover slide (Slide 1 should be COVER)")
        score -= 0.1
    
    # 3. CTA slide check (last slide)
    if slide_count > 0:
        last_slide_pattern = rf'(?im)^(?:##\s*SLIDE\s+{slide_count}\s*(?:-|:)|\*\*Slide\s+{slide_count}\s*[-:])'
        last_slide_match = list(re.finditer(last_slide_pattern, content, re.IGNORECASE))
        last_slide_start = last_slide_match[-1].start() if last_slide_match else -1
        if last_slide_start >= 0 and 'CTA' in content[last_slide_start:].upper():
            issues.append("✅ CTA slide present")
        else:
            issues.append("⚠️ Last slide should have CTA")
            score -= 0.2
    
    # 4. Visual-ready check (each slide should be concise)
    for i in range(1, min(slide_count + 1, 5)):
        slide_pattern = rf'(?ims)^(?:##\s*SLIDE\s+{i}\s*(?:-|:)|\*\*Slide\s+{i}\s*[-:]).*?\n(.*?)(?=^---\s*$|^(?:##\s*SLIDE\s+\d+\s*(?:-|:)|\*\*Slide\s+\d+\s*[-:])|\Z)'
        slide_match = re.search(slide_pattern, content, re.DOTALL)
        if slide_match:
            slide_content = slide_match.group(1).strip()
            if len(slide_content) > 300:
                issues.append(f"⚠️ Slide {i} too long ({len(slide_content)} chars, max 300)")
                score -= 0.05
    
    # 5. Hashtags check
    hashtags = re.findall(r'#\w+', content)
    if len(hashtags) == 0:
        issues.append("✅ No hashtags (allowed)")
    else:
        issues.append(f"✅ Hashtags OK: {len(hashtags)}")

    global_issues, global_delta = run_global_qc_checks(content, mode=mode)
    issues.extend(global_issues)
    score += global_delta
    
    return {
        'format': 'Image',
        'score': max(0, score),
        'issues': issues,
        'passed': score >= 0.7
    }

def qc_poll(content: str, mode: str = "batch") -> QCResult:
    """QC checks specific to Poll"""
    issues = []
    score = 1.0
    
    # 1. Question check
    lines = content.split('\n')
    question_line = None
    for line in lines:
        if line.strip() and not line.startswith('**POLL:**'):
            question_line = line.strip()
            break
    
    if not question_line:
        issues.append("❌ No question found")
        score -= 0.5
    elif len(question_line) > 280:
        issues.append(f"❌ Question too long: {len(question_line)} chars (max 280)")
        score -= 0.3
    else:
        issues.append(f"✅ Question OK: {len(question_line)} chars")
    
    # 2. Options check (2-4 options)
    option_count = sum(
        1
        for line in lines
        if re.match(r'^\s*(?:\*\*)?(?:Option\s+)?[A-D](?:[\.):]|:\*\*)', line.strip(), re.IGNORECASE)
    )
    
    if option_count < 2:
        issues.append(f"❌ Too few options: {option_count} (need 2-4)")
        score -= 0.5
    elif option_count > 4:
        issues.append(f"⚠️ Too many options: {option_count} (max 4 for Twitter poll)")
        score -= 0.2
    else:
        issues.append(f"✅ Options OK: {option_count}")
    
    # 3. Engagement hook
    if '?' not in content:
        issues.append("⚠️ No question mark (polls need clear question)")
        score -= 0.1

    global_issues, global_delta = run_global_qc_checks(content, mode=mode)
    issues.extend(global_issues)
    score += global_delta
    
    return {
        'format': 'Poll',
        'score': max(0, score),
        'issues': issues,
        'passed': score >= 0.7
    }

def run_format_specific_qc(content_file: str, mode: str = "batch") -> QCResult | None:
    with open(content_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    format_type = detect_format(content)
    
    print("=" * 60)
    print("FORMAT-SPECIFIC QUALITY CONTROL")
    print("=" * 60)
    print(f"\n[*] Detected Format: {format_type}\n")
    
    # Run format-specific checks
    if format_type == 'Single Tweet':
        result = qc_single_tweet(content, mode=mode)
    elif format_type in ['Thread', 'Short Thread']:
        result = qc_thread(content, mode=mode)
    elif format_type == 'Image':
        result = qc_image(content, mode=mode)
    elif format_type == 'Poll':
        result = qc_poll(content, mode=mode)
    else:
        print(f"[!] Unknown format: {format_type}")
        print("[*] Running generic QC...")
        return None
    
    # Display results
    print(f"Format: {result['format']}")
    print(f"Score: {result['score']:.2f}/1.00 ({int(result['score']*100)}%)")
    print(f"\nChecks:")
    for issue in result['issues']:
        print(f"  {issue}")
    
    print(f"\n{'='*60}")
    print(get_qc_summary_message(float(result['score']), bool(result['passed'])))
    print("=" * 60)
    
    return result

def main():
    import argparse
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Format-specific QC checker')
    parser.add_argument('content_file', help='Input content file')
    parser.add_argument('--output-dir', help='Session output directory (optional)')
    parser.add_argument('--mode', choices=['manual', 'twitter', 'batch'], default='batch')
    args = parser.parse_args()
    
    result = run_format_specific_qc(args.content_file, mode=args.mode)
    if result is None:
        print("[!] Could not run QC for unknown format")
        sys.exit(1)
    
    # Save QC report
    from pathlib import Path
    from datetime import datetime
    
    if args.output_dir:
        # Session folder mode: simple filename
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        report_file = output_dir / "qc_report.txt"
    else:
        # Legacy mode: timestamp-based in output/qc/
        output_dir = Path(__file__).parent.parent / 'output' / 'qc'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract topic from content filename
        content_path = Path(args.content_file)
        filename = content_path.stem
        
        # Extract topic from format: topic_content_timestamp or FORMAT__topic_content_timestamp
        if '_content_' in filename:
            topic = filename.split('_content_')[0]
            # Remove format prefix if exists (THREAD__, IMAGE__, etc.)
            if '__' in topic:
                parts = topic.split('__', 1)
                topic = parts[1] if len(parts) > 1 else topic
        else:
            topic = filename
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = output_dir / f"{topic}_qc_report_{timestamp}.txt"
    
    content_path = Path(args.content_file)
    score = float(result.get('score', 0) or 0)
    report = (Path(__file__).resolve().parent.parent.parent / "prompts" / "qc" / "qc_report.txt").read_text(
        encoding="utf-8"
    ).format(
        separator="=" * 60,
        file_name=content_path.name,
        generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        format_name=result.get('format', 'Unknown'),
        score=score,
        score_percent=int(score * 100),
    )
    report += "\n"
    for issue in result.get('issues', []):
        report += f"  {issue}\n"
    
    qc_score = score
    qc_passed = bool(result.get('passed'))
    report += f"\nSTATUS: {get_qc_status(qc_score, qc_passed)}\n"
    if qc_passed and qc_score < PUBLISH_READY_SCORE:
        report += f"TARGET: Improve to at least {int(PUBLISH_READY_SCORE * 100)}% before publish\n"
    report += "="*60 + "\n"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n[*] QC report saved: {report_file}")
    
    # Exit code: 0 if pass, 1 if fail
    sys.exit(0 if result['passed'] else 1)

if __name__ == "__main__":
    main()
