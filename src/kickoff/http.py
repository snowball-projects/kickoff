from __future__ import annotations

import gzip
from io import BytesIO
from typing import Any

# Bound both wire bytes and expanded bodies.
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
