import json
import os
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def safe_discord_filename(value: object, fallback: str = "content") -> str:
    name = str(value or fallback)
    for old, new in [("/", "_"), ("\\", "_"), (" ", "_")]:
        name = name.replace(old, new)
    return "".join(ch for ch in name if ch.isalnum() or ch in "._-")[:60] or fallback


def send_discord_bot_message(
    channel_id: str,
    content: str,
    file_path: Optional[Path] = None,
    filename: Optional[str] = None,
) -> bool:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    channel_id = channel_id.strip()
    if not token or not channel_id:
        return False
    if token.lower().startswith("bot "):
        token = token[4:].strip()

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {token}"}

    try:
        if file_path and file_path.exists():
            payload = {"content": content}
            with open(file_path, "rb") as f:
                files = {
                    "payload_json": (None, json.dumps(payload), "application/json"),
                    "files[0]": (filename or file_path.name, f),
                }
                response = requests.post(url, headers=headers, files=files, timeout=20)
        else:
            response = requests.post(url, headers=headers, json={"content": content}, timeout=20)

        if response.status_code in {200, 201}:
            return True

        print(f"[!] Discord bot error {response.status_code}: {response.text[:300]}")
        return False
    except Exception as e:
        print(f"[!] Discord bot error: {e}")
        return False


def get_discord_skip_reason(channel_id: str, target: str) -> str | None:
    if not os.getenv("DISCORD_TOKEN", "").strip():
        return f"[!] Discord {target} skipped: DISCORD_TOKEN missing"
    if not channel_id.strip():
        return f"[!] Discord {target} skipped: channel ID missing"
    return None


def get_angle_channel_id() -> str:
    return os.getenv("DISCORD_CHANNEL_A_ID") or os.getenv("X_LOGS_CHANNEL_ID", "")


def get_final_channel_id() -> str:
    return os.getenv("DISCORD_CHANNEL_B_ID") or os.getenv("X_ANALYTICS_CHANNEL_ID", "")
