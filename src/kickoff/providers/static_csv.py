from __future__ import annotations

import csv
from dataclasses import dataclass

from kickoff.models import CalendarEvent, Participant, ProviderOptions, ProviderRunResult, RawArtifact
from kickoff.normalize import stable_event_id
from kickoff.provider_utils import EventAccumulator
from kickoff.providers.base import Provider
from kickoff.semantics import classification_fields
from kickoff.settings import Settings
from kickoff.timeutils import isoformat_local, parse_iso_datetime, utc_to_timezone


@dataclass(slots=True)
class StaticScheduleProvider(Provider):
    key: str
    league: str
    sport: str
    source_name: str
    season_mode_label: str | None = None

    def season_label(self, season: int) -> str:
        return self.season_mode_label or str(season)

    def fetch(self, season: int, settings: Settings, options: ProviderOptions) -> ProviderRunResult:
        path = settings.data_dir / "reference" / self.key / f"{season}.csv"
        if not path.exists():
            return ProviderRunResult(
                provider_key=self.key,
                season=season,
                events=[],
                warnings=[f"reference schedule not found: {path}"],
                metadata={},
            )

        rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
        accumulator = EventAccumulator(options)
        for row in rows:
            accumulator.add(self._event_from_row(row, season))

        return ProviderRunResult(
            provider_key=self.key,
            season=season,
            events=accumulator.events(),
            raw_artifacts=[RawArtifact(relative_path=f"{season}.csv", content=path.read_bytes())],
            metadata={
                "source_path": str(path.relative_to(settings.repo_root)),
                "semantics": {
                    "default_behavior": "Loads a checked-in canonical reference CSV instead of scraping at runtime.",
                    "dedupe_rule": "event_id or stable fallback id",
                },
                **accumulator.metadata(),
            },
        )

    def _event_from_row(self, row: dict[str, str], season: int) -> CalendarEvent:
        timezone_name = row.get("timezone") or None
        start_time_utc = row.get("start_time_utc") or None
        start_time_local = row.get("start_time_local") or None
        if start_time_local is None and start_time_utc and timezone_name:
            start_time_local = isoformat_local(utc_to_timezone(parse_iso_datetime(start_time_utc), timezone_name))

        home_name = row.get("home_name") or None
        away_name = row.get("away_name") or None
        home = Participant(name=home_name, participant_id=home_name, role="home") if home_name else None
        away = Participant(name=away_name, participant_id=away_name, role="away") if away_name else None
        participants = [participant for participant in [away, home] if participant is not None]
        competition_phase = row.get("competition_phase") or "regular_season"

        return CalendarEvent(
            event_id=row.get("event_id")
            or stable_event_id(self.key, season, row.get("calendar_date"), row.get("title")),
            source=self.source_name,
            sport=row.get("sport") or self.sport,
            league=row.get("league") or self.league,
            season=row.get("season_label") or self.season_label(season),
            event_type=row.get("event_type") or "event",
            title=row.get("title") or "",
            subtitle=row.get("subtitle") or None,
            start_time_utc=start_time_utc,
            start_time_local=start_time_local,
            timezone=timezone_name,
            status=row.get("status") or "scheduled",
            venue=row.get("venue") or None,
            city=row.get("city") or None,
            region=row.get("region") or None,
            country=row.get("country") or None,
            participants=participants,
            home_participant=home,
            away_participant=away,
            round_or_stage=row.get("round_or_stage") or None,
            week_label=None,
            calendar_date=row.get("calendar_date") or None,
            end_calendar_date=row.get("end_calendar_date") or row.get("calendar_date") or None,
            tags=[item for item in (row.get("tags") or "").split("|") if item],
            raw_source_payload=row,
            **classification_fields(competition_phase),
        )
