"""Real local HTTP attempts, not logical source-unit or transport-mock counts."""

import logging
import os
import subprocess
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from kickoff import feeds
from kickoff import refresh_metrics as module
from kickoff.refresh_metrics import refresh_metrics
from kickoff.result_loader import ResultsLoader


@pytest.fixture
def http_source():
    attempts = Counter()
    bodies = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            attempts[self.path] += 1
            status, body = 200, bodies.get(self.path, b'{"ok":true}')
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/target")
                self.end_headers()
                return
            if self.path == "/retry" and attempts[self.path] < 3:
                status = 503
            elif self.path == "/missing":
                status = 404
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", attempts, bodies
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def read(url):
    with urlopen(url, timeout=2) as response:
        return response.read()


def test_all_http_attempts_include_retry_redirect_optional_failure_and_threads(http_source, monkeypatch, capsys):
    base, attempts, _ = http_source
    monkeypatch.setattr(feeds.time, "sleep", lambda _: None)
    previous_disabled = logging.root.manager.disable
    with refresh_metrics() as metrics:
        with ThreadPoolExecutor(max_workers=8) as pool:
            assert len(list(pool.map(read, [base + "/parallel"] * 19))) == 19
        assert feeds.get_json(base + "/retry") == {"ok": True}
        assert read(base + "/redirect") == b'{"ok":true}'
        loader = ResultsLoader()
        assert loader._run(lambda: loader._read(base + "/missing")) is None
        # Cached misses do not count a second request. Non-network guards and
        # file/data reads do not become phantom HTTP requests either.
        assert loader._run(lambda: loader._read(base + "/missing")) is None
        assert loader._run(lambda: loader._read("https://iwf.sport/results")) is None
        assert loader._run(lambda: loader._read(base + "/book.pdf")) is None
        with urlopen("data:application/json,%7B%7D") as response:
            assert response.read() == b"{}"
        logging.getLogger("kickoff").warning("An optional source did not respond")
    assert metrics.requests == sum(attempts.values()) == 25
    assert capsys.readouterr() == ("requests made: 25, units reused: 0, events frozen: 0\n", "")
    assert logging.root.manager.disable == previous_disabled
    # The persistent audit hook is inactive outside a refresh, and repeated runs
    # never accumulate hooks or inherit counts from previous HTTP attempts.
    read(base + "/outside")
    with refresh_metrics() as second:
        read(base + "/new-run")
    assert metrics.requests == 25 and second.requests == 1
    assert capsys.readouterr() == ("requests made: 1, units reused: 0, events frozen: 0\n", "")


def test_failed_refresh_still_reports_actual_attempts_and_restores_logging(http_source, capsys):
    base, attempts, _ = http_source
    previous_disabled = logging.root.manager.disable
    with pytest.raises(HTTPError):
        with refresh_metrics():
            read(base + "/missing")
    assert sum(attempts.values()) == 1
    assert capsys.readouterr() == ("requests made: 1, units reused: 0, events frozen: 0\n", "")
    assert logging.root.manager.disable == previous_disabled


def test_only_one_hook_is_installed_across_runs(monkeypatch, capsys):
    installed = []
    monkeypatch.setattr(module, "_INSTALLED", False)
    monkeypatch.setattr(sys, "addaudithook", installed.append)
    for _ in range(3):
        with refresh_metrics():
            pass
    assert installed == [module._audit]
    assert capsys.readouterr().out.count("requests made: 0") == 3


def test_cli_failure_is_nonzero_with_one_summary_and_no_traceback():
    root = Path(__file__).parents[1]
    script = """
import runpy
import sys
from unittest.mock import patch
sys.argv = ["refresh-public.py", "--force-full", "--year", "2026"]
with patch("kickoff.open_schedules.refresh_open_schedules", side_effect=ValueError("bad primary source")):
    runpy.run_path("scripts/refresh-public.py", run_name="__main__")
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert completed.stdout == "requests made: 0, units reused: 0, events frozen: 0\n"
    assert completed.stderr == ""
