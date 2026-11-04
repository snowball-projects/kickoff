"""Count HTTP attempts by source family; print only family lines and the total."""

from __future__ import annotations

import logging
import sys
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import Lock
from urllib.parse import urlsplit

_LOCK = Lock()
_ACTIVE = None
_INSTALLED = False
_FAMILY = ContextVar("request_family", default=None)
FAMILIES = (
    "college football",
    "men's college basketball",
    "women's college basketball",
    "NBA",
    "NHL",
    "NFL",
    "Champions League",
    "other ESPN",
    "F1",
    "openfootball",
    "MLB",
    "results pages",
    "other",
)


def source_family(url):
    if _FAMILY.get() is not None:
        return _FAMILY.get()
    host, path = urlsplit(url).hostname or "", urlsplit(url).path
    for marker, family in (
        ("/football/college-football/", "college football"),
        ("/basketball/mens-college-basketball/", "men's college basketball"),
        ("/basketball/womens-college-basketball/", "women's college basketball"),
        ("/basketball/nba/", "NBA"),
        ("/football/nfl/", "NFL"),
        ("/soccer/uefa.champions/", "Champions League"),
        ("/hockey/nhl/", "NHL"),
    ):
        if marker in path:
            return family
    if host.endswith("espn.com"):
        return "other ESPN"
    if host == "api-web.nhle.com":
        return "NHL"
    if host == "statsapi.mlb.com":
        return "MLB"
    if "/f1db/f1db/" in path:
        return "F1"
    if "/openfootball/" in path:
        return "openfootball"
    return "other"


@dataclass
class RefreshMetrics:
    families: Counter = field(default_factory=Counter)

    @property
    def requests(self):
        return sum(self.families.values())


def _audit(event, args):
    if event == "urllib.Request" and args[0].startswith(("http://", "https://")):
        with _LOCK:
            if _ACTIVE is not None:
                _ACTIVE.families[source_family(args[0])] += 1


@contextmanager
def request_family(family):
    token = _FAMILY.set(family)
    try:
        yield
    finally:
        _FAMILY.reset(token)


@contextmanager
def refresh_metrics():
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
        for family in FAMILIES:
            print(f"{family}: requests made: {metrics.families[family]}")
        print(f"requests made: {metrics.requests}")
