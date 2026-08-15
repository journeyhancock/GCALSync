"""Long-lived sync loop for headless hosts.

Everything runs on one thread on purpose. A calendar sync and a task sync can
never overlap, so they cannot race each other's mapping files or double-write
the Sync To calendar - which a separate cron process alongside this one would.
"""

import logging
import os
import signal
import threading
import time

os.chdir(os.path.dirname(os.path.abspath(__file__)))

import dashboard
from gcloud_storage import get_client
from main import journey, mollee
from tokens.get_tokens import Creds, ReauthRequired, get_credentials

# Sync tokens keep each poll cheap, so a short interval costs very little.
CALENDAR_INTERVAL = int(os.getenv("CALENDAR_INTERVAL", "300"))

# Tasks has no push API and changes rarely, so it gets the slow lane.
TASKS_INTERVAL = int(os.getenv("TASKS_INTERVAL", "300"))

# How long to nap between checking whether either job is due.
TICK = 5

DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "2727"))

# A poll tick that's this overdue means the daemon is wedged or dead, not
# just mid-cycle.
STALE_AFTER = max(CALENDAR_INTERVAL, TASKS_INTERVAL) + 120

log_buffer = dashboard.LogBuffer()
logging.getLogger().addHandler(log_buffer)

logger = logging.getLogger(__name__)
shutdown = threading.Event()

def calendar_cycle(creds: Creds):
    journey(creds, events=True, tasks=False)
    mollee(creds)

def tasks_cycle(creds: Creds):
    journey(creds, events=False, tasks=True)

JOBS = {
    "calendar": (CALENDAR_INTERVAL, calendar_cycle),
    "tasks": (TASKS_INTERVAL, tasks_cycle)
}

def run_cycle(label: str, creds: Creds) -> bool:
    _, cycle = JOBS[label]

    logger.info(f"Starting {label} cycle")
    started = time.monotonic()

    try:
        cycle(creds)
    except Exception:
        # One bad cycle must not take the daemon down. The sync functions
        # already persist partial progress before bailing out.
        logger.exception(f"{label} cycle failed; continuing")
        return False

    logger.info(f"Finished {label} cycle in {time.monotonic() - started:.1f}s")
    return True

def stop(signum, _frame):
    # A cycle in flight is left to finish so state stays consistent; give
    # systemd a generous TimeoutStopSec.
    logger.info(f"Received signal {signum}; stopping after the current cycle")
    shutdown.set()

def run() -> int:
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    # Only used for credential refresh/recovery (tokens/get_tokens.py) - state
    # files are never synced here. Hand state to/from the bucket with
    # sync_control.py's pause/resume instead of doing it on every cycle.
    client = get_client()

    # Bound to the LAN-facing interface only; if this fails to bind, the whole
    # daemon fails to start (and systemd restarts it) rather than running with
    # a dashboard silently absent - an unreachable dashboard is meant to read
    # as "service down", so the two must fail together.
    dashboard.start(dashboard.get_wlan0_ip(), DASHBOARD_PORT, STALE_AFTER)

    logger.info(f"Polling calendars every {CALENDAR_INTERVAL}s, tasks every {TASKS_INTERVAL}s")
    next_run = {label: time.monotonic() for label in JOBS}

    while not shutdown.is_set():
        now = time.monotonic()
        due = [label for label in JOBS if now >= next_run[label]]

        if not due:
            shutdown.wait(TICK)
            continue

        # Reloaded each time round so a token refreshed by another host, or a
        # rotated refresh token, gets picked up without a restart.
        try:
            creds = get_credentials(client=client)
        except ReauthRequired as e:
            logger.error(str(e))
            return 1

        results = []
        for label in due:
            results.append(run_cycle(label, creds))
            next_run[label] = time.monotonic() + JOBS[label][0]

        dashboard.write_heartbeat(all(results), log_buffer.drain())
        shutdown.wait(TICK)

    return 0

if __name__ == "__main__":
    raise SystemExit(run())
