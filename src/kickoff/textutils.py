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
