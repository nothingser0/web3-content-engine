#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Internal Scheduler Daemon for Docker
Runs in background and executes run_daily_auto.py on schedule (Mon-Fri at configured time).
Logs directly to stdout so Docker logs can display live progress.
"""

import os
import sys
import time
import signal
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configuration from environment variables
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "07:00")  # HH:MM in 24-hour format
SCHEDULE_DAYS = os.getenv("SCHEDULE_DAYS", "1,2,3,4,5")  # 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat, 7=Sun
RUN_ON_START = os.getenv("RUN_ON_START", "false").lower() in ("true", "1", "yes")
HEARTBEAT_FILE = Path("/tmp/scheduler_heartbeat")

# Global state for graceful shutdown
running = True
current_process = None

def handle_shutdown(signum, frame):
    """Handle SIGTERM / SIGINT for graceful shutdown in Docker."""
    global running, current_process
    signame = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
    log(f"Received termination signal ({signame}). Gracefully shutting down...")
    running = False
    if current_process and current_process.poll() is None:
        log("Terminating active pipeline process...")
        current_process.terminate()
        try:
            current_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            log("Pipeline process did not exit in time, killing...")
            current_process.kill()
    if HEARTBEAT_FILE.exists():
        HEARTBEAT_FILE.unlink(missing_ok=True)
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

# Parse allowed days
ALLOWED_DAYS = [int(d.strip()) for d in SCHEDULE_DAYS.split(",") if d.strip().isdigit()]


def log(msg: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [Scheduler] {msg}", flush=True)


def update_heartbeat():
    try:
        HEARTBEAT_FILE.write_text(str(time.time()), encoding="utf-8")
    except Exception:
        pass


def run_pipeline():
    global current_process
    log("🚀 Starting scheduled daily content generation...")
    update_heartbeat()
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    try:
        current_process = subprocess.Popen(
            [sys.executable, str(PROJECT_ROOT / "run_daily_auto.py")],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env
        )
        for line in current_process.stdout:
            print(line, end="", flush=True)
            update_heartbeat()
        current_process.wait()
        if current_process.returncode == 0:
            log("✅ Daily content generation completed successfully.")
        else:
            log(f"⚠️ Daily content generation finished with exit code {current_process.returncode}")
    except Exception as e:
        log(f"❌ Error running pipeline: {e}")
    finally:
        current_process = None
        update_heartbeat()


def main():
    log("==================================================")
    log("   WEB3 CONTENT PIPELINE - INTERNAL SCHEDULER    ")
    log("==================================================")
    log(f"Configured Time : {SCHEDULE_TIME} (Format: HH:MM)")
    log(f"Configured Days : {SCHEDULE_DAYS} (1=Monday ... 7=Sunday)")
    log(f"Run On Startup  : {RUN_ON_START}")
    
    # Optional immediate run on container startup
    if RUN_ON_START:
        log("RUN_ON_START is true. Triggering immediate run...")
        run_pipeline()

    last_run_date = None

    log(f"Scheduler is active. Waiting for next trigger ({SCHEDULE_TIME})...")
    update_heartbeat()

    while running:
        update_heartbeat()
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_date = now.strftime("%Y-%m-%d")
        # isoweekday: 1=Mon, 2=Tue, ..., 7=Sun
        current_weekday = now.isoweekday()

        if (
            current_weekday in ALLOWED_DAYS
            and current_time == SCHEDULE_TIME
            and last_run_date != current_date
        ):
            last_run_date = current_date
            log(f"⏰ Schedule matched! (Day: {current_weekday}, Time: {current_time})")
            run_pipeline()
            log("Sleeping until next cycle...")

        # Sleep 30 seconds before next check
        time.sleep(30)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Scheduler stopped by user.")
        sys.exit(0)
