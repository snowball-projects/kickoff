from __future__ import annotations

import re
from html import unescape

TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def strip_html(html: str) -> str:
    text = TAG_RE.sub(" ", html)
    text = unescape(text)
    return WHITESPACE_RE.sub(" ", text).strip()


def collapse_spaces(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value).strip()


def espn_logo_url(value: object) -> str | None:
    """Only source-supplied ESPN team-logo paths; never arbitrary external URLs."""
    if isinstance(value, str) and re.fullmatch(
        r"https://a\.espncdn\.com/(?:i/teamlogos/[A-Za-z0-9_./-]+|guid/[0-9a-f-]{36}/logos/default)\.(?:png|svg)", value
    ):
        return value
    return None
