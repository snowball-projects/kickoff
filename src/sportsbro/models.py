from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(slots=True)
class Participant:
    name: str
    participant_id: str | None = None
    short_name: str | None = None
    role: str | None = None
    entity_type: str = "team"
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CalendarEvent:
    event_id: str
    source: str
    sport: str
    league: str
    season: str
    event_type: str
    title: str
    subtitle: str | None
    start_time_utc: str | None
    start_time_local: str | None
    timezone: str | None
    status: str
    venue: str | None
    city: str | None
    region: str | None
    country: str | None
    participants: list[Participant] = field(default_factory=list)
    home_participant: Participant | None = None
    away_participant: Participant | None = None
    round_or_stage: str | None = None
    week_label: str | None = None
    calendar_date: str | None = None
    end_calendar_date: str | None = None
    source_url: str | None = None
    competition_phase: str = "regular_season"
    is_regular_season: bool = False
    is_postseason: bool = False
    is_exhibition: bool = False
    is_support_event: bool = False
    tags: list[str] = field(default_factory=list)
    raw_source_payload: JsonValue = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["participants"] = [participant.to_dict() for participant in self.participants]
        payload["home_participant"] = self.home_participant.to_dict() if self.home_participant else None
        payload["away_participant"] = self.away_participant.to_dict() if self.away_participant else None
        return payload


@dataclass(slots=True)
class RawArtifact:
    relative_path: str
    content: bytes
    is_binary: bool = False


@dataclass(slots=True)
class ProviderRunResult:
    provider_key: str
    season: int
    events: list[CalendarEvent] = field(default_factory=list)
    raw_artifacts: list[RawArtifact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def manifest_fragment(self) -> dict[str, Any]:
        return {
            "provider": self.provider_key,
            "season": self.season,
            "event_count": len(self.events),
            "raw_artifacts": [artifact.relative_path for artifact in self.raw_artifacts],
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class ProviderOptions:
    event_scope: str = "regular_only"
    include_special_events: bool = False
    include_support_events: bool = False
    motorsport_view: str = "race_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
