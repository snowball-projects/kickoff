from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc
EASTERN_NAME = "America/New_York"


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


def isoformat_local(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.replace(microsecond=0).isoformat()


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized)


def parse_clock_time(raw_value: str) -> tuple[int, int]:
    normalized = raw_value.strip().upper().replace(".", "")
    if normalized == "NOON":
        return 12, 0
    if normalized == "MIDNIGHT":
        return 0, 0

    if " " not in normalized:
        raise ValueError(f"unsupported time value: {raw_value}")
    clock, meridiem = normalized.split(" ", 1)
    meridiem = meridiem.strip()
    if ":" in clock:
        hour_text, minute_text = clock.split(":", 1)
    else:
        hour_text, minute_text = clock, "00"
    hour = int(hour_text)
    minute = int(minute_text)
    if not 1 <= hour <= 12 or not 0 <= minute <= 59:
        raise ValueError(f"unsupported time value: {raw_value}")
    if meridiem == "AM":
        hour = 0 if hour == 12 else hour
    elif meridiem == "PM":
        hour = 12 if hour == 12 else hour + 12
    else:
        raise ValueError(f"unsupported meridiem: {raw_value}")
    return hour, minute


def localize_date_time(day: date, raw_time: str, timezone_name: str) -> datetime:
    hour, minute = parse_clock_time(raw_time)
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=get_zoneinfo(timezone_name))


def eastern_to_utc(day: date, raw_time: str) -> datetime:
    hour, minute = parse_clock_time(raw_time)
    eastern_dt = datetime(day.year, day.month, day.day, hour, minute, tzinfo=get_zoneinfo(EASTERN_NAME))
    return eastern_dt.astimezone(UTC)


def utc_to_timezone(utc_dt: datetime | None, timezone_name: str | None) -> datetime | None:
    if utc_dt is None or not timezone_name:
        return None
    aware = utc_dt.astimezone(UTC) if utc_dt.tzinfo else utc_dt.replace(tzinfo=UTC)
    return aware.astimezone(get_zoneinfo(timezone_name))
