from __future__ import annotations

import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

from src.utils.discord import get_final_channel_id, send_discord_bot_message


_ = load_dotenv()


_FORMAT_ALIASES = {
    "single tweet": "single tweet",
    "singletweet": "single tweet",
    "tweet": "single tweet",
    "thread": "thread",
    "poll": "poll",
    "image": "image",
}


def _normalize_format(format: str) -> str:
    key = re.sub(r"[^a-z]", "", format.lower())
    if key not in _FORMAT_ALIASES:
        raise ValueError(f"Unsupported format: {format}")
    return _FORMAT_ALIASES[key]


def _read_text(content_file: Path) -> str:
    if not content_file.exists() or not content_file.is_file():
        raise ValueError(f"Content file not found: {content_file}")
    return content_file.read_text(encoding="utf-8")


def _clean_block(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    while lines and not lines[0]:
        _ = lines.pop(0)
    while lines and not lines[-1]:
        _ = lines.pop()
    return "\n".join(lines).strip()


def _strip_trailing_noise(text: str) -> str:
    text = re.split(r"\n-{3,}\n|\n\*\*[^\n]+:\*\*\s*$", text, maxsplit=1)[0]
    return _clean_block(text)


def parse_content_for_buffer(content_file: Path, format: str) -> dict[str, object]:
    """Parse `content.txt` for Buffer queue payload.

    Examples:
        >>> parse_content_for_buffer(Path("content.txt"), "Single Tweet")
        {'text': '...', 'mode': 'addToQueue'}
        >>> parse_content_for_buffer(Path("content.txt"), "Thread")
        {'thread': ['...'], 'mode': 'addToQueue'}
    """
    text = _read_text(content_file)
    kind = _normalize_format(format)

    if kind == "single tweet":
        match = re.search(r"\*\*SINGLE TWEET:\*\*\s*(.*)", text, re.S | re.I)
        if not match:
            raise ValueError("Unparseable single tweet content")
        body = _strip_trailing_noise(match.group(1))
        if not body:
            raise ValueError("Unparseable single tweet content")
        return {"text": body, "mode": "addToQueue"}

    if kind == "thread":
        tweets = [
            _clean_block(m.group(1))
            for m in re.finditer(r"\*\*Tweet \d+:\*\*\s*(.*?)(?=\n\*\*Tweet \d+:\*\*|\Z)", text, re.S | re.I)
        ]
        tweets = [tweet for tweet in tweets if tweet]
        if not tweets:
            raise ValueError("Unparseable thread content")
        return {"thread": tweets, "mode": "addToQueue"}

    if kind == "poll":
        match = re.search(r"\*\*POLL:\*\*\s*(.*?)\s*Poll question:", text, re.S | re.I)
        if not match:
            raise ValueError("Unparseable poll content")
        body = _clean_block(match.group(1))
        if not body:
            raise ValueError("Unparseable poll content")
        return {"text": body, "mode": "addToQueue"}

    match = re.search(r"\*\*Tweet text:\*\*\s*(.*?)(?:\n---\n|\Z)", text, re.S | re.I)
    if not match:
        raise ValueError("Unparseable image content")
    body = _clean_block(match.group(1))
    if not body:
        raise ValueError("Unparseable image content")
    return {"text": body, "mode": "addToQueue"}


def get_buffer_config() -> tuple[str, str]:
    return (
        os.getenv("BUFFER_ACCESS_TOKEN", "").strip(),
        os.getenv("BUFFER_PROFILE_ID", "").strip(),
    )


def _build_buffer_input(payload: dict[str, object], profile_id: str) -> dict[str, object]:
    text = str(payload.get("text", "")).strip()
    if "thread" in payload:
        thread_items = payload.get("thread")
        thread = [str(item).strip() for item in thread_items] if isinstance(thread_items, list) else []
        thread = [item for item in thread if item]
        if not text and thread:
            text = thread[0]
        return {
            "text": text,
            "channelId": profile_id,
            "mode": "addToQueue",
            "schedulingType": "automatic",
            "metadata": {"twitter": {"thread": [{"text": item} for item in thread]}},
        }
    return {
        "text": text,
        "channelId": profile_id,
        "mode": "addToQueue",
        "schedulingType": "automatic",
    }


def _notify_buffer_failure(session_dir: Path, content_format: str, failure: str, detail: str) -> None:
    if os.getenv("BUFFER_DISCORD_NOTIFY", "").strip().lower() != "true":
        return

    channel_id = str(get_final_channel_id() or "").strip()
    if not channel_id:
        return

    content_file = session_dir / "content.txt"
    message = (
        f"Buffer failed: {failure}\n"
        f"Session: {session_dir}\n"
        f"Content: {content_file.name}\n"
        f"Format: {content_format}\n"
        f"Detail: {detail}"
    )
    _ = send_discord_bot_message(channel_id, message)


def _buffer_fail(session_dir: Path, content_format: str, failure: str, detail: str, print_message: str) -> bool:
    print(print_message)
    _notify_buffer_failure(session_dir, content_format, failure, detail)
    return False


def _is_dry_run() -> bool:
    val = os.getenv("DRY_RUN", "").strip().lower()
    return val in {"1", "true", "yes", "on"}


def _buffer_enabled() -> bool:
    val = os.getenv("BUFFER_ENABLED", "true").strip().lower()
    return val not in {"0", "false", "no", "off"}


def send_to_buffer(session_dir: Path, content_format: str, angle_data: dict[str, object]) -> bool:
    if not _buffer_enabled():
        print("Buffer: disabled, skipping")
        return True

    dry_run = _is_dry_run()
    token, profile_id = get_buffer_config()
    
    if dry_run:
        if not profile_id:
            profile_id = "dry-run-placeholder-profile"
        content_file = session_dir / "content.txt"
        try:
            payload = parse_content_for_buffer(content_file, content_format)
            input_data = _build_buffer_input(payload, profile_id)
            title = str(angle_data.get("title", "")).strip()
            print(f"Buffer: DRY RUN - would queue {title or 'content'} (no API call)")
            return True
        except Exception as e:
            print(f"Buffer: DRY RUN failed - parse/build error: {e}")
            return False
    
    if not token:
        return _buffer_fail(session_dir, content_format, "missing token", "BUFFER_ACCESS_TOKEN missing", "Buffer: Access token missing, skipping")
    if not profile_id:
        return _buffer_fail(session_dir, content_format, "missing profile", "BUFFER_PROFILE_ID missing", "Buffer: Profile ID not configured, skipping")

    content_file = session_dir / "content.txt"
    try:
        payload = parse_content_for_buffer(content_file, content_format)
        input_data = _build_buffer_input(payload, profile_id)
        title = str(angle_data.get("title", "")).strip()
        response = requests.post(
            "https://api.buffer.com",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "query": (
                    "mutation CreatePost($input: CreatePostInput!) { "
                    "createPost(input: $input) { ... on PostActionSuccess { post { id text } } "
                    "... on MutationError { message } } }"
                ),
                "variables": {"input": input_data},
            },
            timeout=30,
        )
    except Exception as e:
        return _buffer_fail(session_dir, content_format, "request failed", str(e), f"Buffer: request failed: {e}")

    if response.status_code in {401, 403}:
        return _buffer_fail(session_dir, content_format, "auth failed", f"status={response.status_code}", f"Buffer: auth failed ({response.status_code}), skipping")

    try:
        data = response.json()
    except Exception:
        return _buffer_fail(session_dir, content_format, "invalid response", f"status={response.status_code}", f"Buffer: invalid response ({response.status_code})")

    if not isinstance(data, dict):
        return _buffer_fail(session_dir, content_format, "invalid response", f"status={response.status_code}", f"Buffer: invalid response ({response.status_code})")

    if response.status_code != 200 or data.get("errors"):
        return _buffer_fail(session_dir, content_format, "GraphQL error", f"status={response.status_code}", "Buffer: GraphQL error, skipping")

    data_block = data.get("data")
    if not isinstance(data_block, dict):
        return _buffer_fail(session_dir, content_format, "GraphQL error", "missing data block", "Buffer: GraphQL error, skipping")

    result = data_block.get("createPost")
    if not isinstance(result, dict):
        return _buffer_fail(session_dir, content_format, "GraphQL error", "missing createPost", "Buffer: GraphQL error, skipping")

    if result.get("message"):
        return _buffer_fail(session_dir, content_format, "mutation error", str(result.get("message", "")), "Buffer: GraphQL mutation error, skipping")

    post = result.get("post")
    if not isinstance(post, dict):
        return _buffer_fail(session_dir, content_format, "GraphQL error", "missing post", "Buffer: GraphQL error, skipping")

    if title:
        print(f"Buffer: queued {title}")
    if post.get("id"):
        return True
    return _buffer_fail(session_dir, content_format, "missing post id", "post.id missing", "Buffer: missing post id, skipping")
