from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc


def get_zoneinfo(name: str):
    if name == "UTC":
        return UTC
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:  # pragma: no cover - depends on local env
        raise RuntimeError(
            f"timezone '{name}' is unavailable. Install project dependencies to provide tzdata."
        ) from exc


def isoformat_z(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    aware = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    return aware.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
