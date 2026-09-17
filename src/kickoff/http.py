from __future__ import annotations

import gzip
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from kickoff.settings import Settings


class FetchError(RuntimeError):
    """Raised when a provider cannot fetch a remote resource."""


def _request(url: str, settings: Settings) -> Request:
    return Request(
        url,
        headers={
            "User-Agent": settings.user_agent,
            "Accept": "*/*",
        },
    )


def fetch_bytes(url: str, settings: Settings) -> bytes:
    try:
        with urlopen(_request(url, settings), timeout=settings.timeout_seconds) as response:
            payload = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip" or payload[:2] == b"\x1f\x8b":
                return gzip.decompress(payload)
            return payload
    except (HTTPError, URLError, TimeoutError) as exc:
        raise FetchError(f"failed to fetch {url}: {exc}") from exc


def fetch_text(url: str, settings: Settings, encoding: str = "utf-8") -> str:
    return fetch_bytes(url, settings).decode(encoding, errors="replace")


def fetch_json(url: str, settings: Settings) -> dict[str, Any] | list[Any]:
    return json.loads(fetch_text(url, settings))


def filename_from_url(url: str, default: str) -> str:
    parsed = urlparse(url)
    name = parsed.path.rsplit("/", 1)[-1]
    return name or default
