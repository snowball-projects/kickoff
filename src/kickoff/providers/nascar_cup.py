from __future__ import annotations

import re
from datetime import date

from kickoff.http import fetch_bytes, fetch_text
from kickoff.models import CalendarEvent, ProviderOptions, ProviderRunResult, RawArtifact
from kickoff.normalize import stable_event_id
from kickoff.pdf import extract_pdf_lines
from kickoff.provider_utils import EventAccumulator
from kickoff.providers.base import Provider
from kickoff.semantics import classification_fields
from kickoff.settings import Settings
from kickoff.timeutils import EASTERN_NAME, eastern_to_utc, get_zoneinfo, isoformat_local, isoformat_z

NASCAR_TRACKS = {
    "CLASH (BOWMAN GRAY)": {
        "title": "Cook Out Clash",
        "venue": "Bowman Gray Stadium",
        "city": "Winston-Salem",
        "region": "North Carolina",
        "country": "United States",
    },
    "DUELS (DAYTONA)": {
        "title": "Daytona Duels",
        "venue": "Daytona International Speedway",
        "city": "Daytona Beach",
        "region": "Florida",
        "country": "United States",
    },
    "DAYTONA 500": {
        "title": "Daytona 500",
        "venue": "Daytona International Speedway",
        "city": "Daytona Beach",
        "region": "Florida",
        "country": "United States",
    },
    "ECHOPARK (ATLANTA)": {
        "title": "EchoPark Speedway",
        "venue": "EchoPark Speedway",
        "city": "Hampton",
        "region": "Georgia",
        "country": "United States",
    },
    "COTA (AUSTIN)": {
        "title": "Circuit of The Americas",
        "venue": "Circuit of The Americas",
        "city": "Austin",
        "region": "Texas",
        "country": "United States",
    },
    "PHOENIX": {
        "title": "Phoenix Raceway",
        "venue": "Phoenix Raceway",
        "city": "Avondale",
        "region": "Arizona",
        "country": "United States",
    },
    "LAS VEGAS": {
        "title": "Las Vegas Motor Speedway",
        "venue": "Las Vegas Motor Speedway",
        "city": "Las Vegas",
        "region": "Nevada",
        "country": "United States",
    },
    "DARLINGTON": {
        "title": "Darlington Raceway",
        "venue": "Darlington Raceway",
        "city": "Darlington",
        "region": "South Carolina",
        "country": "United States",
    },
    "MARTINSVILLE": {
        "title": "Martinsville Speedway",
        "venue": "Martinsville Speedway",
        "city": "Martinsville",
        "region": "Virginia",
        "country": "United States",
    },
    "BRISTOL": {
        "title": "Bristol Motor Speedway",
        "venue": "Bristol Motor Speedway",
        "city": "Bristol",
        "region": "Tennessee",
        "country": "United States",
    },
    "KANSAS": {
        "title": "Kansas Speedway",
        "venue": "Kansas Speedway",
        "city": "Kansas City",
        "region": "Kansas",
        "country": "United States",
    },
    "TALLADEGA": {
        "title": "Talladega Superspeedway",
        "venue": "Talladega Superspeedway",
        "city": "Talladega",
        "region": "Alabama",
        "country": "United States",
    },
    "TEXAS": {
        "title": "Texas Motor Speedway",
        "venue": "Texas Motor Speedway",
        "city": "Fort Worth",
        "region": "Texas",
        "country": "United States",
    },
    "WATKINS GLEN": {
        "title": "Watkins Glen International",
        "venue": "Watkins Glen International",
        "city": "Watkins Glen",
        "region": "New York",
        "country": "United States",
    },
    "ALL-STAR DOVER": {
        "title": "All-Star Race",
        "venue": "Dover Motor Speedway",
        "city": "Dover",
        "region": "Delaware",
        "country": "United States",
    },
    "CHARLOTTE": {
        "title": "Charlotte Motor Speedway",
        "venue": "Charlotte Motor Speedway",
        "city": "Concord",
        "region": "North Carolina",
        "country": "United States",
    },
    "NASHVILLE": {
        "title": "Nashville Superspeedway",
        "venue": "Nashville Superspeedway",
        "city": "Lebanon",
        "region": "Tennessee",
        "country": "United States",
    },
    "MICHIGAN": {
        "title": "Michigan International Speedway",
        "venue": "Michigan International Speedway",
        "city": "Brooklyn",
        "region": "Michigan",
        "country": "United States",
    },
    "POCONO": {
        "title": "Pocono Raceway",
        "venue": "Pocono Raceway",
        "city": "Long Pond",
        "region": "Pennsylvania",
        "country": "United States",
    },
    "SAN DIEGO": {
        "title": "San Diego",
        "venue": "Naval Base Coronado",
        "city": "San Diego",
        "region": "California",
        "country": "United States",
    },
    "SONOMA": {
        "title": "Sonoma Raceway",
        "venue": "Sonoma Raceway",
        "city": "Sonoma",
        "region": "California",
        "country": "United States",
    },
    "CHICAGOLAND": {
        "title": "Chicagoland Speedway",
        "venue": "Chicagoland Speedway",
        "city": "Joliet",
        "region": "Illinois",
        "country": "United States",
    },
    "NORTH WILKESBORO": {
        "title": "North Wilkesboro Speedway",
        "venue": "North Wilkesboro Speedway",
        "city": "North Wilkesboro",
        "region": "North Carolina",
        "country": "United States",
    },
    "INDIANAPOLIS": {
        "title": "Brickyard 400",
        "venue": "Indianapolis Motor Speedway",
        "city": "Indianapolis",
        "region": "Indiana",
        "country": "United States",
    },
    "IOWA": {
        "title": "Iowa Speedway",
        "venue": "Iowa Speedway",
        "city": "Newton",
        "region": "Iowa",
        "country": "United States",
    },
    "RICHMOND": {
        "title": "Richmond Raceway",
        "venue": "Richmond Raceway",
        "city": "Richmond",
        "region": "Virginia",
        "country": "United States",
    },
    "NEW HAMPSHIRE": {
        "title": "New Hampshire Motor Speedway",
        "venue": "New Hampshire Motor Speedway",
        "city": "Loudon",
        "region": "New Hampshire",
        "country": "United States",
    },
    "DAYTONA": {
        "title": "Daytona",
        "venue": "Daytona International Speedway",
        "city": "Daytona Beach",
        "region": "Florida",
        "country": "United States",
    },
    "WWTR (ST. LOUIS)": {
        "title": "World Wide Technology Raceway",
        "venue": "World Wide Technology Raceway",
        "city": "Madison",
        "region": "Illinois",
        "country": "United States",
    },
    "HOMESTEAD-MIAMI": {
        "title": "NASCAR Championship",
        "venue": "Homestead-Miami Speedway",
        "city": "Homestead",
        "region": "Florida",
        "country": "United States",
    },
}

MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def _competition_phase(label: str, points_race_number: int | None) -> tuple[str, str]:
    if label.startswith("CLASH") or label.startswith("ALL-STAR"):
        return "exhibition", "Exhibition"
    if label.startswith("DUELS"):
        return "qualifying", "Qualifying"
    if points_race_number is None:
        return "special", "Special Event"
    if points_race_number <= 26:
        return "regular_season", "Regular Season"
    if points_race_number <= 29:
        return "postseason", "Round of 16"
    if points_race_number <= 32:
        return "postseason", "Round of 12"
    if points_race_number <= 35:
        return "postseason", "Round of 8"
    return "postseason", "Championship 4"


def _subtitle_for_phase(competition_phase: str) -> str:
    if competition_phase == "postseason":
        return "NASCAR Cup Playoffs"
    if competition_phase == "exhibition":
        return "NASCAR Cup Exhibition"
    if competition_phase == "qualifying":
        return "NASCAR Cup Qualifying"
    return "NASCAR Cup Series"


class NascarCupProvider(Provider):
    key = "nascar_cup"
    league = "NASCAR_CUP"
    sport = "motorsport"

    def fetch(self, season: int, settings: Settings, options: ProviderOptions) -> ProviderRunResult:
        schedule_url = f"https://www.nascar.com/nascar-cup-series/{season}/schedule/"
        html = fetch_text(schedule_url, settings)
        pdf_match = re.search(
            r"(https://www\.nascar\.com/wp-content/uploads/[^\"']+National-Series-Schedules-Times\.pdf)",
            html,
        )
        if not pdf_match:
            return ProviderRunResult(
                provider_key=self.key,
                season=season,
                events=[],
                raw_artifacts=[RawArtifact(relative_path="schedule.html", content=html.encode("utf-8"))],
                warnings=["Could not locate the official NASCAR printable schedule PDF."],
                metadata={"url": schedule_url},
            )

        pdf_url = pdf_match.group(1)
        pdf_bytes = fetch_bytes(pdf_url, settings)
        lines = extract_pdf_lines(pdf_bytes)
        events, metadata = self._parse_pdf_lines(lines, season, options)
        warnings: list[str] = []
        if options.motorsport_view == "full_weekend":
            warnings.append(
                "The official NASCAR source used here contributes races and the Daytona Duels; it does not provide general practice or qualifying sessions."
            )
        if options.include_support_events:
            warnings.append("NASCAR support series are not modeled in this adapter.")
        return ProviderRunResult(
            provider_key=self.key,
            season=season,
            events=events,
            raw_artifacts=[
                RawArtifact(relative_path="schedule.html", content=html.encode("utf-8")),
                RawArtifact(relative_path="schedule_times.pdf", content=pdf_bytes, is_binary=True),
            ],
            warnings=warnings,
            metadata={
                "url": pdf_url,
                "semantics": {
                    "default_behavior": "Main NASCAR Cup points-paying race schedule only.",
                    "full_weekend_behavior": "Adds the Daytona Duels qualifying event present in the current source; no missing practice or qualifying sessions are fabricated.",
                    "special_behavior": "Clash, Daytona Duels, and All-Star are excluded by default and included only when include_special_events is enabled.",
                    "all_published_behavior": "Keeps the full 36-race Cup championship, including playoff races.",
                    "dedupe_rule": "track label + calendar date",
                },
                **metadata,
            },
        )

    def _parse_pdf_lines(
        self,
        lines: list[str],
        season: int,
        options: ProviderOptions,
    ) -> tuple[list[CalendarEvent], dict[str, object]]:
        accumulator = EventAccumulator(options)
        started = False
        points_race_number = 0
        source_phase_counts: dict[str, int] = {}
        for line in lines:
            if not started and line.startswith("CLASH (BOWMAN GRAY) SUN |"):
                started = True
            if not started:
                continue
            if line.startswith("DAYTONA SAT | FEB 14 | 5 PM | CW"):
                break
            if " | " not in line or line.startswith("OFF WEEK"):
                continue

            parts = [part.strip() for part in line.split("|")]
            if len(parts) < 4:
                continue

            label_segment, date_segment, time_segment = parts[0], parts[1], parts[2]
            if time_segment == "*":
                continue

            label, _weekday = label_segment.rsplit(" ", 1)
            month_text, day_text = date_segment.split(" ", 1)
            race_day = date(season, MONTHS[month_text.upper()], int(day_text))
            utc_dt = eastern_to_utc(race_day, time_segment)
            et_dt = utc_dt.astimezone(get_zoneinfo(EASTERN_NAME))
            ref = NASCAR_TRACKS.get(label, {})
            if label.startswith("CLASH") or label.startswith("ALL-STAR"):
                competition_phase, round_or_stage = _competition_phase(label, None)
            elif label.startswith("DUELS"):
                competition_phase, round_or_stage = _competition_phase(label, None)
            else:
                points_race_number += 1
                competition_phase, round_or_stage = _competition_phase(label, points_race_number)
            source_phase_counts[competition_phase] = source_phase_counts.get(competition_phase, 0) + 1

            if competition_phase == "qualifying" and options.motorsport_view == "race_only":
                continue

            tags = ["nascar-cup", competition_phase.replace("_", "-")]
            if competition_phase != "qualifying":
                tags.append("race")
            if competition_phase == "qualifying":
                tags.append("qualifying")

            accumulator.add(
                CalendarEvent(
                    event_id=stable_event_id(self.key, season, label, race_day.isoformat()),
                    source="nascar_official_schedule_pdf",
                    sport=self.sport,
                    league=self.league,
                    season=str(season),
                    event_type="qualifying" if competition_phase == "qualifying" else "race",
                    title=ref.get("title", label.title()),
                    subtitle=_subtitle_for_phase(competition_phase),
                    start_time_utc=isoformat_z(utc_dt),
                    start_time_local=isoformat_local(et_dt),
                    timezone="America/New_York",
                    status="scheduled",
                    venue=ref.get("venue", label),
                    city=ref.get("city"),
                    region=ref.get("region"),
                    country=ref.get("country"),
                    participants=[],
                    home_participant=None,
                    away_participant=None,
                    round_or_stage=round_or_stage,
                    week_label=None,
                    calendar_date=race_day.isoformat(),
                    end_calendar_date=race_day.isoformat(),
                    tags=tags,
                    raw_source_payload={"line": line},
                    **classification_fields(competition_phase),
                )
            )
        return accumulator.events(), {
            "source_phase_counts": source_phase_counts,
            "points_race_count": points_race_number,
            **accumulator.metadata(),
        }
