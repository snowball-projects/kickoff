from __future__ import annotations

import gzip
import json
from io import BytesIO
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from kickoff.settings import Settings

# Bound both wire bytes and expanded bodies, including legacy local adapters.
MAX_BYTES = 80_000_000


def read_bounded_response(response: Any, *, max_bytes: int = MAX_BYTES) -> bytes:
    payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError("Source exceeds compressed/transfer size limit")
    if response.headers.get("Content-Encoding", "").strip().lower() == "gzip" or payload[:2] == b"\x1f\x8b":
        with gzip.GzipFile(fileobj=BytesIO(payload)) as stream:
            payload = stream.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise ValueError("Source exceeds expanded size limit")
    return payload


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
            return read_bounded_response(response)
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
