from __future__ import annotations

import re
from html import unescape
from urllib.parse import parse_qs, urlencode, urlsplit

TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def strip_html(html: str) -> str:
    text = TAG_RE.sub(" ", html)
    text = unescape(text)
    return WHITESPACE_RE.sub(" ", text).strip()


def collapse_spaces(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value).strip()


def espn_logo_url(value: object) -> str | None:
    """Derive a fixed56px CDN image only from an allowed source-supplied path."""
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme != "https" or parsed.netloc != "a.espncdn.com" or parsed.fragment:
        return None
    path = parsed.path
    if path == "/combiner/i":
        query = parse_qs(parsed.query, keep_blank_values=True)
        if set(query) != {"img", "w", "h"} or query["w"] != ["56"] or query["h"] != ["56"] or len(query["img"]) != 1:
            return None
        path = query["img"][0]
    elif parsed.query:
        return None
    if not re.fullmatch(r"/(?:i/teamlogos/[A-Za-z0-9_./-]+|guid/[0-9a-f-]{36}/logos/default)\.(?:png|svg)", path):
        return None
    if any(segment in {".", ".."} for segment in path.split("/")):
        return None
    canonical = "https://a.espncdn.com/combiner/i?" + urlencode({"img": path, "w": 56, "h": 56})
    return canonical if parsed.path != "/combiner/i" or value == canonical else None
