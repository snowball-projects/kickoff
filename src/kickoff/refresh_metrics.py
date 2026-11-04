"""One refresh summary, counting HTTP attempts without retaining request details."""

from __future__ import annotations

import logging
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock

_LOCK = Lock()
_ACTIVE = None
_INSTALLED = False


@dataclass
class RefreshMetrics:
    requests: int = 0
    plan: object = None
    frozen: int = 0


def _audit(event, args):
    # urllib emits this once per open, including retries and redirects, before
    # transport work. Count failed attempts too, but not file/data URL reads.
    # The hook is installed once and becomes a no-op outside the refresh.
    if event == "urllib.Request" and args[0].startswith(("http://", "https://")):
        with _LOCK:
            if _ACTIVE is not None:
                _ACTIVE.requests += 1


@contextmanager
def refresh_metrics():
    """Count all worker-thread and main-thread HTTP attempts for this run.

    Units reused are unique source units proved reusable, excluding units then
    fetched. Events frozen are all IDs frozen in the resulting state, including
    source IDs outside the public rolling window. On failure they reflect work
    completed before the failure; the command still exits unsuccessfully.
    """
    global _ACTIVE, _INSTALLED
    metrics = RefreshMetrics()
    if not _INSTALLED:
        sys.addaudithook(_audit)
        _INSTALLED = True
    with _LOCK:
        _ACTIVE = metrics
    previous_disabled = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        yield metrics
    finally:
        with _LOCK:
            _ACTIVE = None
        logging.disable(previous_disabled)
        reused = metrics.plan.skipped if metrics.plan is not None else 0
        print(f"requests made: {metrics.requests}, units reused: {reused}, events frozen: {metrics.frozen}")
