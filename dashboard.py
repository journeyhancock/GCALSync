"""In-process web dashboard.

Renders the log of the most recent poll cycle as a fake terminal, plus a
staleness check so a wedged or dead daemon shows as down instead of quietly
serving a stale "OK". Runs in the same process/service as the sync loop on
purpose - a separate watchdog service was considered and skipped, so an
unreachable dashboard doubles as the down signal.
"""

import html
import logging
import re
import subprocess
import threading

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from util import read_file, write_file

logger = logging.getLogger(__name__)

HEARTBEAT_FILE = "last_run"


class LogBuffer(logging.Handler):
    """Captures formatted log lines for the current poll cycle only."""

    def __init__(self):
        super().__init__()
        self.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        self._lines = []
        self._lock = threading.Lock()

    def emit(self, record):
        with self._lock:
            self._lines.append(self.format(record))

    def drain(self) -> str:
        with self._lock:
            lines, self._lines = self._lines, []
        return "\n".join(lines)


def write_heartbeat(ok: bool, log_text: str) -> None:
    write_file(HEARTBEAT_FILE, {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if ok else "error",
        "log": log_text,
    })


def get_wlan0_ip() -> str:
    result = subprocess.run(
        ["ip", "-4", "-o", "addr", "show", "wlan0"],
        capture_output=True, text=True, check=True
    )
    match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", result.stdout)
    if not match:
        raise RuntimeError("wlan0 has no IPv4 address")
    return match.group(1)


PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="30">
<title>GCALSync</title>
<style>
  body {{ background: #0d0d0d; color: #c9c9c9; font-family: Consolas, Menlo, monospace;
         margin: 0; padding: 2rem; }}
  h1 {{ font-size: 1rem; font-weight: normal; color: #888; margin: 0 0 1rem; }}
  .status {{ font-weight: bold; }}
  .ok {{ color: #4caf50; }}
  .error {{ color: #f44336; }}
  .stale {{ color: #ff9800; }}
  pre {{ white-space: pre-wrap; word-break: break-word; margin-top: 1.5rem;
        border-top: 1px solid #333; padding-top: 1rem; }}
</style>
</head>
<body>
<h1>GCALSync &mdash; last run {timestamp}</h1>
<div class="status {status_class}">{status_text}</div>
<pre>{log}</pre>
</body>
</html>
"""


def render_page(stale_after: float) -> str:
    data = read_file(HEARTBEAT_FILE)

    if not data:
        return PAGE.format(timestamp="never", status_class="stale",
                            status_text="NO RUNS YET", log="")

    timestamp = data.get("timestamp", "unknown")
    age = None
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(timestamp)).total_seconds()
    except ValueError:
        pass

    if age is not None and age > stale_after:
        status_class, status_text = "stale", f"STALE — no run in {int(age)}s"
    elif data.get("status") == "ok":
        status_class, status_text = "ok", "OK"
    else:
        status_class, status_text = "error", "ERROR"

    return PAGE.format(
        timestamp=html.escape(timestamp),
        status_class=status_class,
        status_text=html.escape(status_text),
        log=html.escape(data.get("log", "")))


def make_handler(stale_after: float):
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = render_page(stale_after).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass  # keep HTTP access noise out of the run transcript/journal

    return DashboardHandler


def start(host: str, port: int, stale_after: float) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), make_handler(stale_after))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info(f"Dashboard listening on http://{host}:{port}")
    return server
