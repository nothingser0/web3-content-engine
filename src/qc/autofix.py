#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import requests
from pathlib import Path
from datetime import datetime
from typing import TypedDict, cast


class AutofixQCResult(TypedDict):
    format: str
    score: float
    issues: list[str]
    passed: bool

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from src.utils.common import setup_console_encoding
    from src.qc.format_specific import PUBLISH_READY_SCORE, get_qc_status, run_format_specific_qc
    from src.core.prompt_loader import PromptLoader
else:
    from ..utils.common import setup_console_encoding
    from .format_specific import PUBLISH_READY_SCORE, get_qc_status, run_format_specific_qc
    from ..core.prompt_loader import PromptLoader

setup_console_encoding()

_prompt_loader = PromptLoader()


def _load_prompt(name: str) -> str:
    return _prompt_loader.load(name)


def _resolve_existing_file(path: str) -> Path:
    content_path = Path(path).expanduser().resolve()
    if not content_path.is_file():
        raise FileNotFoundError(f"File not found: {content_path}")
    return content_path


class FileLock:
    def __init__(self, path: Path):
        self.path = path
        self.fd: int | None = None

    def __enter__(self):
        try:
            self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as e:
            raise RuntimeError(f"Lock exists: {self.path}") from e
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def _write_text_atomic(path: Path, content: str) -> None:
    temp_path = path.with_name(f".{path.name}.tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, path)


def write_qc_report(content_file: str, output_dir, qc_result: AutofixQCResult, score: float) -> None:
    """Write QC report file"""
    if output_dir is None:
        return  # Skip if no output dir specified
    
    content_path = Path(content_file)
    
    # Simple filename: qc_report.txt (no timestamp)
    report_file = output_dir / "qc_report.txt"
    
    # Load and format report template
    report_template_path = Path(__file__).resolve().parent.parent.parent / "prompts" / "qc" / "qc_report.txt"
    report = report_template_path.read_text(encoding="utf-8").format(
        separator="=" * 60,
        file_name=content_path.name,
        generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        format_name=qc_result.get('format', 'Unknown'),
        score=score,
        score_percent=int(score * 100),
    )
    
    report += "\n"
    for issue in qc_result.get('issues', []):
        report += f"  {issue}\n"
    
    qc_passed = bool(qc_result.get('passed'))
    report += f"\nSTATUS: {get_qc_status(score, qc_passed)}\n"
    if qc_passed and score < PUBLISH_READY_SCORE:
        report += f"TARGET: Improve to at least {int(PUBLISH_READY_SCORE * 100)}% before publish\n"
    report += "="*60 + "\n"
    
    _write_text_atomic(report_file, report)
    
    print(f"\n[*] QC report saved: {report_file}")


def run_qc_check(content_file, mode: str = "batch"):
    result = run_format_specific_qc(content_file, mode=mode)
    if result is None:
        return cast(AutofixQCResult, cast(object, {
            'format': 'Unknown',
            'score': 0.0,
            'issues': ['Unknown format - no QC rules matched'],
            'passed': False
        }))

    # Keep all checks (including ✅) with emojis for report
    return cast(AutofixQCResult, cast(object, {
        'format': result['format'],
        'score': result['score'],
        'issues': result['issues'],  # Keep all checks with emojis
        'passed': result['passed']
    }))

def call_ai_to_fix(content, format_type, issues, mode: str = "batch"):
    from src.utils.config import load_api_config, WEB3_CONTENT_MODEL_OVERRIDE
    from src.core.model_router import ModelRouter
    
    api_url, api_key = load_api_config()
    
    use_router = True
    router = None
    model = None
    
    if WEB3_CONTENT_MODEL_OVERRIDE:
        print(f"[*] Using override model: {WEB3_CONTENT_MODEL_OVERRIDE}")
        model = WEB3_CONTENT_MODEL_OVERRIDE
        use_router = False
    else:
        router = ModelRouter(api_url, api_key)
    
    issues_text = "\n".join([f"- {issue}" for issue in issues])
    mode_context = f"Pipeline mode: {mode}."
    
    current_date = datetime.now().strftime("%B %d, %Y")
    current_month = datetime.now().strftime("%B %Y")
    current_year = str(datetime.now().year)
    format_specific_rules = ""

    if format_type == 'Single Tweet':
        format_specific_rules = _load_prompt("qc/qc_autofix_single_tweet.txt")
    elif format_type == 'Thread':
        format_specific_rules = _load_prompt("qc/qc_autofix_thread.txt")
    elif format_type == 'Image':
        format_specific_rules = _load_prompt("qc/qc_autofix_image.txt")
    elif format_type == 'Poll':
        format_specific_rules = _load_prompt("qc/qc_autofix_poll.txt")

    prompt = _load_prompt("qc/qc_autofix_base.txt").format(
        format_type=format_type,
        format_type_upper=format_type.upper(),
        current_date=current_date,
        current_month=current_month,
        current_year=current_year,
        content=content,
        issues_text=f"{mode_context}\n{issues_text}",
        format_specific_rules=format_specific_rules,
    )
    
    messages = [{"role": "user", "content": prompt}]
    
    if use_router and router:
        print(f"[*] Using router (Kategori G - QC/Review)...")
        print(f"    API: {api_url}")
        
        print(f"    Task: AI-powered content auto-fix", file=sys.stderr)
        print(f"    Checks: Format compliance, Surabaya style, engagement, technical", file=sys.stderr)
        print(f"    Expected: Fixed content or recommendations", file=sys.stderr)
        print(f"    Time estimate: 45-90 seconds (analyzing + fixing)", file=sys.stderr)
        print(f"", file=sys.stderr)
        
        fixed_content = router.call_with_fallback(
            role="qc",
            messages=messages,
            max_tokens=2048,
            temperature=0.7
        )
        return fixed_content if fixed_content else None
    elif model:
        print(f"[*] Using override model: {model}...")
        print(f"    API: {api_url}")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 2048,
            "temperature": 0.7
        }
        
        try:
            response = requests.post(
                f"{api_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=600
            )
            
            if response.status_code == 200:
                result = response.json()
                fixed_content = result['choices'][0]['message']['content'].strip()
                return fixed_content
            else:
                print(f"[!] API Error: {response.status_code}")
                return None
        except Exception as e:
            print(f"[!] Error calling AI: {e}")
            return None
    else:
        print("[!] No router or model available")
        return None

def main():
    if len(sys.argv) < 2:
        print("[!] Usage: python qc_autofix.py <content_file> [--auto] [--min-score 0.80] [--mode manual|twitter|batch]")
        print("    --auto: Skip prompt and auto-fix immediately")
        sys.exit(1)
    
    content_file = sys.argv[1]
    auto_mode = '--auto' in sys.argv or '--yes' in sys.argv
    min_score = 0.7
    output_dir = None
    mode = "batch"
    
    if '--min-score' in sys.argv:
        score_index = sys.argv.index('--min-score')
        if score_index + 1 >= len(sys.argv):
            print("[!] Missing value after --min-score")
            sys.exit(1)
        min_score = float(sys.argv[score_index + 1])
    
    if '--output-dir' in sys.argv:
        dir_index = sys.argv.index('--output-dir')
        if dir_index + 1 >= len(sys.argv):
            print("[!] Missing value after --output-dir")
            sys.exit(1)
        output_dir = Path(sys.argv[dir_index + 1]).expanduser().resolve()
        if not output_dir.is_dir():
            print(f"[!] Output directory not found: {output_dir}")
            sys.exit(1)
    if '--mode' in sys.argv:
        mode_index = sys.argv.index('--mode')
        if mode_index + 1 >= len(sys.argv):
            print("[!] Missing value after --mode")
            sys.exit(1)
        mode = sys.argv[mode_index + 1].lower()
        if mode not in {"manual", "twitter", "batch"}:
            print(f"[!] Invalid mode: {mode}")
            sys.exit(1)
    
    try:
        content_path = _resolve_existing_file(content_file)
    except FileNotFoundError as e:
        print(f"[!] {e}")
        sys.exit(1)
    content_file = str(content_path)
    
    print("=" * 60)
    print("QC AUTO-FIX")
    print("=" * 60)
    print()
    
    # Step 1: Run QC check
    print("[*] Step 1: Running QC check...")
    qc_result = run_qc_check(content_file, mode=mode)
    
    print(f"[*] Format: {qc_result['format']}")
    initial_score = float(qc_result['score'])
    print(f"[*] Score: {initial_score:.2f}/1.00 ({int(initial_score * 100)}%)")
    print()
    
    target_score = max(min_score, PUBLISH_READY_SCORE)

    if qc_result['passed'] and initial_score >= min_score:
        print(f"✅ QC {get_qc_status(initial_score, True)} - No fixes needed!")
        write_qc_report(content_file, output_dir, qc_result, initial_score)
        return
    elif qc_result['passed']:
        print(f"[*] QC {get_qc_status(initial_score, True)} - score {initial_score:.2f} below target {min_score:.2f} - forcing fix")
    
    # Step 2: Show issues
    print("❌ QC NEEDS FIX - Issues found:")
    for issue in qc_result['issues']:
        print(f"  - {issue}")
    print()
    
    # Step 3: Ask user (or auto if --auto flag)
    if auto_mode:
        print("[*] Auto-fix mode enabled")
        response = 'y'
    else:
        response = input("Auto-fix with AI? (y/n): ").strip().lower()
    
    if response != 'y':
        print("[*] Skipping auto-fix")
        write_qc_report(content_file, output_dir, qc_result, initial_score)
        return
    
    # Step 4: Read original content
    with open(content_file, 'r', encoding='utf-8') as f:
        original_content = f.read()
    
    # Step 5: Call AI to fix
    print()
    print("[*] Step 2: Calling AI to fix issues...")
    fixed_content = call_ai_to_fix(original_content, qc_result['format'], qc_result['issues'], mode=mode)
    
    if not fixed_content:
        print("[!] AI fix failed")
        sys.exit(1)
    
    # Step 6: Save fixed version
    print("[*] Step 3: Saving fixed version...")
    
    # Create backup
    backup_file = content_path.with_name(f"{content_path.stem}_backup{content_path.suffix}")
    lock_file = content_path.with_name(f".{content_path.name}.lock")

    try:
        with FileLock(lock_file):
            _write_text_atomic(backup_file, original_content)
            _write_text_atomic(content_path, fixed_content)
    except RuntimeError as e:
        print(f"[!] File locked: {e}")
        sys.exit(1)
    print(f"[*] Backup saved: {backup_file}")
    print(f"[*] Fixed version saved: {content_file}")
    
    # Step 7: Re-run QC
    print()
    print("[*] Step 4: Re-running QC check...")
    qc_result_after = run_qc_check(content_file, mode=mode)
    
    new_score = float(qc_result_after['score'])
    print(f"[*] New Score: {new_score:.2f}/1.00 ({int(new_score * 100)}%)")
    print()
    
    if qc_result_after['passed'] and new_score >= min_score:
        print("=" * 60)
        print(f"✅ QC {get_qc_status(new_score, True)} - Content fixed successfully!")
        print("=" * 60)
        print()
        print("Before:", f"{int(initial_score * 100)}%")
        print("After:", f"{int(new_score * 100)}%")
        print(f"Improvement: +{int((new_score - initial_score) * 100)}%")
        write_qc_report(content_file, output_dir, qc_result_after, new_score)
    else:
        print("=" * 60)
        print(f"⚠️ QC STILL BELOW TARGET - Need at least {int(target_score * 100)}%. Some issues remain")
        print("=" * 60)
        print()
        print("Remaining issues:")
        for issue in qc_result_after['issues']:
            print(f"  - {issue}")
        print()
        print("You may need to fix manually or run auto-fix again.")
        write_qc_report(content_file, output_dir, qc_result_after, new_score)
        sys.exit(1)

if __name__ == "__main__":
    main()
