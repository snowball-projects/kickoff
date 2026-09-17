from __future__ import annotations

import re
from datetime import date
from html import unescape

from kickoff.http import fetch_text
from kickoff.models import CalendarEvent, ProviderOptions, ProviderRunResult, RawArtifact
from kickoff.normalize import stable_event_id
from kickoff.provider_utils import EventAccumulator
from kickoff.providers.base import Provider
from kickoff.semantics import classification_fields
from kickoff.settings import Settings
from kickoff.timeutils import EASTERN_NAME, eastern_to_utc, get_zoneinfo, isoformat_local, isoformat_z

MONTH_LOOKUP = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


class IndyCarProvider(Provider):
    key = "indycar"
    league = "INDYCAR"
    sport = "motorsport"

    def fetch(self, season: int, settings: Settings, options: ProviderOptions) -> ProviderRunResult:
        url = "https://www.indycar.com/Schedule"
        html = fetch_text(url, settings)
        cards = self._parse_cards(html, season)
        accumulator = EventAccumulator(options)
        for round_number, values in enumerate(cards, start=1):
            accumulator.add(self._build_event(values, season, round_number, url))

        warnings: list[str] = []
        if options.motorsport_view == "full_weekend":
            warnings.append(
                "The official IndyCar source used here exposes top-level race cards; Full Weekend currently adds no practice or qualifying sessions."
            )
        if options.include_support_events:
            warnings.append(
                "IndyCar support events are not modeled yet; this adapter currently emits only the unique top-level schedule cards on the official page."
            )

        return ProviderRunResult(
            provider_key=self.key,
            season=season,
            events=accumulator.events(),
            raw_artifacts=[RawArtifact(relative_path="schedule.html", content=html.encode("utf-8"))],
            warnings=warnings,
            metadata={
                "url": url,
                "semantics": {
                    "default_behavior": "Official IndyCar schedule cards, treated as main-series race events.",
                    "full_weekend_behavior": "The current official source contains race cards only; no sessions are fabricated.",
                    "special_behavior": "Support-series cards are intentionally excluded unless a dedicated parser is added.",
                    "dedupe_rule": "title + calendar date",
                },
                **accumulator.metadata(),
            },
        )

    def _parse_cards(self, html: str, season: int) -> list[dict[str, object]]:
        date_re = re.compile(r'event-card-header-date">([^<]+)<')
        time_re = re.compile(r'event-card-header-time">([^<]+)<')
        title_re = re.compile(r'event-card-title">([^<]+)<')
        track_re = re.compile(r'event-card-track-name">([^<]+)<')
        location_re = re.compile(r'event-card-track-location">([^<]+)<')
        cards: dict[str, dict[str, object]] = {}
        current: dict[str, str] = {}
        for raw_line in html.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            date_match = date_re.search(line)
            if date_match:
                current = {"date_text": unescape(date_match.group(1)).strip()}
                continue

            if not current:
                continue

            time_match = time_re.search(line)
            if time_match and "time_text" not in current:
                current["time_text"] = unescape(time_match.group(1)).strip()
                continue

            title_match = title_re.search(line)
            if title_match and "title" not in current:
                current["title"] = unescape(title_match.group(1)).strip()
                continue

            track_match = track_re.search(line)
            if track_match and "venue" not in current:
                current["venue"] = unescape(track_match.group(1)).strip()
                continue

            location_match = location_re.search(line)
            if location_match and {"date_text", "time_text", "title", "venue"} <= current.keys():
                current["location"] = unescape(location_match.group(1)).strip()
                race_day = self._parse_race_day(current["date_text"], season)
                event_id = stable_event_id(self.key, season, current["title"], race_day.isoformat())
                cards.setdefault(
                    event_id,
                    {
                        **current,
                        "event_id": event_id,
                        "race_day": race_day,
                    },
                )
                current = {}

        return sorted(
            cards.values(),
            key=lambda item: (
                item["race_day"].isoformat(),
                str(item["title"]),
            ),
        )

    @staticmethod
    def _parse_race_day(date_text: str, season: int) -> date:
        month_text, day_text = date_text.split(" ", 1)
        return date(season, MONTH_LOOKUP[month_text], int(day_text))

    def _build_event(
        self,
        values: dict[str, object],
        season: int,
        round_number: int,
        source_url: str,
    ) -> CalendarEvent:
        race_day = values["race_day"]
        title = str(values["title"])
        event_id = str(values["event_id"])
        location_text = str(values["location"])
        city, region = [part.strip() for part in location_text.split(",", 1)]
        time_text = str(values["time_text"])
        utc_dt = eastern_to_utc(race_day, time_text.replace(" ET", "")) if time_text != "TBD" else None
        et_dt = utc_dt.astimezone(get_zoneinfo(EASTERN_NAME)) if utc_dt else None
        country = "Canada" if region == "Ontario" else "United States"
        round_label = f"Round {round_number}"
        competition_phase = "regular_season"

        return CalendarEvent(
            event_id=event_id,
            source="indycar_official_schedule_page",
            sport=self.sport,
            league=self.league,
            season=str(season),
            event_type="race",
            title=title,
            subtitle="IndyCar Series",
            start_time_utc=isoformat_z(utc_dt),
            start_time_local=isoformat_local(et_dt),
            timezone="America/New_York" if time_text != "TBD" else None,
            status="scheduled" if time_text != "TBD" else "tbd",
            venue=str(values["venue"]),
            city=city,
            region=region,
            country=country,
            participants=[],
            home_participant=None,
            away_participant=None,
            round_or_stage=round_label,
            week_label=None,
            calendar_date=race_day.isoformat(),
            end_calendar_date=race_day.isoformat(),
            tags=["indycar", "race", "regular-season"],
            raw_source_payload={"time_text": time_text, "source_url": source_url},
            **classification_fields(competition_phase),
        )
