# Renders the log of the most recent run of each job cycle
# Includes a staleness check so a wedged or dead daemon shows as down
# Runs in the same service as the sync loop  

import html
import logging
import re
import subprocess
import threading

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from util import read_file, write_file

logger = logging.getLogger(__name__)

COLUMNS = [
    ("journey_calendar", "Journey Calendar"),
    ("mollee_calendar", "Mollee Calendar"),
    ("tasks", "Tasks"),
]
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


def write_heartbeat(label: str, ok: bool, log_text: str) -> None:
    current_heartbeat = read_file(HEARTBEAT_FILE)
    current_heartbeat[label] = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "status": "ok" if ok else "error",
        "log": log_text,
    }
    write_file(HEARTBEAT_FILE, current_heartbeat)


def get_wlan0_ip() -> str:
    result = subprocess.run(
        ["ip", "-4", "-o", "addr", "show", "wlan0"],
        capture_output=True, text=True, check=True
    )
    match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", result.stdout)
    if not match:
        raise RuntimeError("wlan0 has no IPv4 address")
    return match.group(1)


COLUMN = """<section class="column">
<h1>{column} &mdash; last run {timestamp}</h1>
<div class="status {status_class}">{status_text}</div>
<pre>{log}</pre>
</section>
"""


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
  .columns {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 2rem; }}
  .column {{ min-width: 0; }}
</style>
</head>
<body>
<div class="columns">
{columns}</div>
</body>
</html>
"""


def render_page(stale_after: float) -> str:
    data = read_file(HEARTBEAT_FILE)
    formatted_columns = []

    for job_key, name in COLUMNS:
        entry = data.get(job_key)

        if not entry:
            formatted_columns.append(COLUMN.format(
                column=name, timestamp="never", status_class="stale",
                status_text="NO RUNS YET", log=""))
            continue

        timestamp = entry.get("timestamp", "unknown")
        age = None
        try:
            # Stored as a naive UTC timestamp (no offset), so it has to be
            # marked aware again before it can be diffed against now().
            parsed = datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - parsed).total_seconds()
        except ValueError:
            pass

        if age is not None and age > stale_after:
            status_class, status_text = "stale", f"STALE: no run in {int(age)}s"
        elif entry.get("status") == "ok":
            status_class, status_text = "ok", "OK"
        else:
            status_class, status_text = "error", "ERROR"

        formatted_columns.append(COLUMN.format(
            column=name,
            timestamp=html.escape(timestamp),
            status_class=status_class,
            status_text=html.escape(status_text),
            log=html.escape(entry.get("log", ""))))

    return PAGE.format(columns="".join(formatted_columns))


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
