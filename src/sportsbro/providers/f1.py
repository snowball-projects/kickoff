from __future__ import annotations

import json
import re

from sportsbro.http import fetch_text
from sportsbro.models import CalendarEvent, ProviderOptions, ProviderRunResult, RawArtifact
from sportsbro.normalize import stable_event_id
from sportsbro.provider_utils import EventAccumulator
from sportsbro.providers.base import Provider
from sportsbro.semantics import classification_fields
from sportsbro.settings import Settings
from sportsbro.timeutils import isoformat_local, isoformat_z, parse_iso_datetime, utc_to_timezone

F1_REFERENCE = {
    "australia": {
        "venue": "Albert Park Grand Prix Circuit",
        "city": "Melbourne",
        "region": "Victoria",
        "country": "Australia",
        "timezone": "Australia/Melbourne",
    },
    "china": {
        "venue": "Shanghai International Circuit",
        "city": "Shanghai",
        "region": "Shanghai",
        "country": "China",
        "timezone": "Asia/Shanghai",
    },
    "japan": {
        "venue": "Suzuka Circuit",
        "city": "Suzuka",
        "region": "Mie",
        "country": "Japan",
        "timezone": "Asia/Tokyo",
    },
    "miami": {
        "venue": "Miami International Autodrome",
        "city": "Miami Gardens",
        "region": "Florida",
        "country": "United States",
        "timezone": "America/New_York",
    },
    "canada": {
        "venue": "Circuit Gilles Villeneuve",
        "city": "Montreal",
        "region": "Quebec",
        "country": "Canada",
        "timezone": "America/Toronto",
    },
    "monaco": {
        "venue": "Circuit de Monaco",
        "city": "Monaco",
        "region": "Monaco",
        "country": "Monaco",
        "timezone": "Europe/Monaco",
    },
    "barcelona-catalunya": {
        "venue": "Circuit de Barcelona-Catalunya",
        "city": "Montmelo",
        "region": "Catalonia",
        "country": "Spain",
        "timezone": "Europe/Madrid",
    },
    "austria": {
        "venue": "Red Bull Ring",
        "city": "Spielberg",
        "region": "Styria",
        "country": "Austria",
        "timezone": "Europe/Vienna",
    },
    "great-britain": {
        "venue": "Silverstone Circuit",
        "city": "Silverstone",
        "region": "England",
        "country": "United Kingdom",
        "timezone": "Europe/London",
    },
    "belgium": {
        "venue": "Circuit de Spa-Francorchamps",
        "city": "Stavelot",
        "region": "Wallonia",
        "country": "Belgium",
        "timezone": "Europe/Brussels",
    },
    "hungary": {
        "venue": "Hungaroring",
        "city": "Mogyorod",
        "region": "Pest County",
        "country": "Hungary",
        "timezone": "Europe/Budapest",
    },
    "netherlands": {
        "venue": "Circuit Zandvoort",
        "city": "Zandvoort",
        "region": "North Holland",
        "country": "Netherlands",
        "timezone": "Europe/Amsterdam",
    },
    "italy": {
        "venue": "Autodromo Nazionale Monza",
        "city": "Monza",
        "region": "Lombardy",
        "country": "Italy",
        "timezone": "Europe/Rome",
    },
    "spain": {
        "venue": "Madring",
        "city": "Madrid",
        "region": "Community of Madrid",
        "country": "Spain",
        "timezone": "Europe/Madrid",
    },
    "azerbaijan": {
        "venue": "Baku City Circuit",
        "city": "Baku",
        "region": "Baku",
        "country": "Azerbaijan",
        "timezone": "Asia/Baku",
    },
    "singapore": {
        "venue": "Marina Bay Street Circuit",
        "city": "Singapore",
        "region": "Singapore",
        "country": "Singapore",
        "timezone": "Asia/Singapore",
    },
    "united-states": {
        "venue": "Circuit of The Americas",
        "city": "Austin",
        "region": "Texas",
        "country": "United States",
        "timezone": "America/Chicago",
    },
    "mexico": {
        "venue": "Autodromo Hermanos Rodriguez",
        "city": "Mexico City",
        "region": "Mexico City",
        "country": "Mexico",
        "timezone": "America/Mexico_City",
    },
    "brazil": {
        "venue": "Interlagos",
        "city": "Sao Paulo",
        "region": "Sao Paulo",
        "country": "Brazil",
        "timezone": "America/Sao_Paulo",
    },
    "las-vegas": {
        "venue": "Las Vegas Strip Circuit",
        "city": "Las Vegas",
        "region": "Nevada",
        "country": "United States",
        "timezone": "America/Los_Angeles",
    },
    "qatar": {
        "venue": "Lusail International Circuit",
        "city": "Lusail",
        "region": "Al Daayen",
        "country": "Qatar",
        "timezone": "Asia/Qatar",
    },
    "abu-dhabi": {
        "venue": "Yas Marina Circuit",
        "city": "Abu Dhabi",
        "region": "Abu Dhabi",
        "country": "United Arab Emirates",
        "timezone": "Asia/Dubai",
    },
    "united-arab-emirates": {
        "venue": "Yas Marina Circuit",
        "city": "Abu Dhabi",
        "region": "Abu Dhabi",
        "country": "United Arab Emirates",
        "timezone": "Asia/Dubai",
    },
}

SESSION_LABELS = {
    "practice": "Practice",
    "qualifying": "Qualifying",
    "sprint_qualifying": "Sprint Qualifying",
    "sprint": "Sprint",
    "warm_up": "Warm-up",
    "race": "Race",
}

SUPPORT_SERIES_MARKERS = (
    "f1 academy",
    "formula 2",
    "formula 3",
    "porsche supercup",
)


class F1Provider(Provider):
    key = "f1"
    league = "F1"
    sport = "motorsport"

    def fetch(self, season: int, settings: Settings, options: ProviderOptions) -> ProviderRunResult:
        season_url = f"https://www.formula1.com/en/racing/{season}"
        season_html = fetch_text(season_url, settings)
        round_map = self._extract_round_map(season_html, season)
        slugs = [slug for slug, _round in sorted(round_map.items(), key=lambda item: item[1] or 999)]
        for slug in re.findall(rf'href="/en/racing/{season}/([^"/?#]+)', season_html):
            if slug not in slugs:
                slugs.append(slug)

        raw_artifacts = [RawArtifact(relative_path="season.html", content=season_html.encode("utf-8"))]
        accumulator = EventAccumulator(options)
        warnings: list[str] = []
        if options.include_special_events and any(slug.startswith("pre-season-testing") for slug in slugs):
            warnings.append(
                "F1 pre-season testing is listed on the season page but is not yet normalized as a race-weekend session."
            )

        for slug in slugs:
            if slug.startswith("pre-season-testing"):
                continue
            page_url = f"https://www.formula1.com/en/racing/{season}/{slug}"
            html = fetch_text(page_url, settings)
            raw_artifacts.append(RawArtifact(relative_path=f"{slug}.html", content=html.encode("utf-8")))

            sports_payload = self._extract_sports_event_payload(html)
            if not sports_payload:
                warnings.append(f"F1 race page parse incomplete for slug '{slug}'")
                continue

            sessions = [
                (sub_event, session_kind)
                for sub_event in sports_payload.get("subEvent", [])
                if isinstance(sub_event, dict) and (session_kind := self._session_kind(sub_event)) is not None
            ]
            if not any(session_kind == "race" for _sub_event, session_kind in sessions):
                warnings.append(f"F1 race page parse incomplete for slug '{slug}'")
                continue
            if options.motorsport_view == "race_only":
                sessions = [(sub_event, kind) for sub_event, kind in sessions if kind == "race"]

            for sub_event, session_kind in sessions:
                utc_dt = parse_iso_datetime(sub_event.get("startDate"))
                if utc_dt is None:
                    warnings.append(f"F1 {session_kind.replace('_', ' ')} missing startDate for slug '{slug}'")
                    continue

                ref = F1_REFERENCE.get(slug, {})
                timezone_name = ref.get("timezone")
                local_dt = utc_to_timezone(utc_dt, timezone_name)
                session_name = self._session_name(sub_event, session_kind)
                clean_title = " ".join(str(sports_payload.get("name") or slug.replace("-", " ")).split())
                title = clean_title if session_kind == "race" else f"{clean_title}: {session_name}"
                round_number = round_map.get(slug)
                round_label = f"Round {round_number}" if round_number else None
                location = sports_payload.get("location", {}) or {}
                raw_status = str(sub_event.get("eventStatus", "scheduled"))
                status = (
                    "scheduled"
                    if raw_status.lower().endswith("eventscheduled")
                    else raw_status.rsplit("/", 1)[-1].lower()
                )
                event_id = (
                    stable_event_id(self.key, season, slug)
                    if session_kind == "race"
                    else stable_event_id(self.key, season, slug, session_kind, session_name)
                )

                accumulator.add(
                    CalendarEvent(
                        event_id=event_id,
                        source="formula1_official_site",
                        sport=self.sport,
                        league=self.league,
                        season=str(season),
                        event_type=session_kind,
                        title=title,
                        subtitle=" · ".join(value for value in (round_label, session_name) if value),
                        start_time_utc=isoformat_z(utc_dt),
                        start_time_local=isoformat_local(local_dt),
                        timezone=timezone_name,
                        status=status,
                        venue=ref.get("venue"),
                        city=ref.get("city") or location.get("name"),
                        region=ref.get("region"),
                        country=ref.get("country"),
                        participants=[],
                        home_participant=None,
                        away_participant=None,
                        round_or_stage=round_label,
                        week_label=None,
                        calendar_date=(local_dt.date().isoformat() if local_dt else utc_dt.date().isoformat()),
                        end_calendar_date=(local_dt.date().isoformat() if local_dt else utc_dt.date().isoformat()),
                        tags=["f1", session_kind.replace("_", "-"), "grand-prix", "regular-season"],
                        raw_source_payload={
                            "slug": slug,
                            "url": page_url,
                            "round": round_number,
                            "session_event": sub_event,
                        },
                        **classification_fields("regular_season"),
                    )
                )

        return ProviderRunResult(
            provider_key=self.key,
            season=season,
            events=accumulator.events(),
            raw_artifacts=raw_artifacts,
            warnings=warnings,
            metadata={
                "url": season_url,
                "semantics": {
                    "default_behavior": "Race Only emits the main Formula 1 Grand Prix race for each weekend.",
                    "full_weekend_behavior": "Full Weekend emits official main-series practice, qualifying, sprint, warm-up, and race sessions present in the source.",
                    "support_behavior": "Support series remain separate and are not included unless explicitly selected and implemented.",
                    "special_behavior": "Pre-season testing remains outside the race-weekend view.",
                    "dedupe_rule": "season slug + session identity",
                },
                **accumulator.metadata(),
            },
        )

    @staticmethod
    def _extract_sports_event_payload(html: str) -> dict | None:
        script_matches = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, flags=re.DOTALL)
        for raw_script in script_matches:
            try:
                payload = json.loads(raw_script)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("@type") == "SportsEvent" and payload.get("subEvent"):
                return payload
        return None

    @staticmethod
    def _session_kind(sub_event: dict) -> str | None:
        identity = f"{sub_event.get('@id', '')} {sub_event.get('name', '')}".casefold().replace("-", " ")
        if any(marker in identity for marker in SUPPORT_SERIES_MARKERS) or re.search(r"\bf[23]\b", identity):
            return None
        if "sprint qualifying" in identity or "sprint shootout" in identity:
            return "sprint_qualifying"
        if "practice" in identity:
            return "practice"
        if "qualifying" in identity:
            return "qualifying"
        if "warm up" in identity or "warmup" in identity:
            return "warm_up"
        if "sprint" in identity:
            return "sprint"
        event_id = str(sub_event.get("@id", ""))
        name = str(sub_event.get("name", ""))
        if event_id.endswith("#Race") or name.startswith("Race -"):
            return "race"
        return None

    @staticmethod
    def _session_name(sub_event: dict, session_kind: str) -> str:
        name = " ".join(str(sub_event.get("name", "")).split())
        if " - " in name:
            label, _event_name = name.split(" - ", 1)
            if label:
                return label
        return name or SESSION_LABELS[session_kind]

    @staticmethod
    def _extract_round_map(season_html: str, season: int) -> dict[str, int | None]:
        round_map: dict[str, int | None] = {}
        slug_matches = re.finditer(rf'href="/en/racing/{season}/([^"/?#]+)', season_html)
        for match in slug_matches:
            slug = match.group(1)
            window = season_html[match.start() : match.start() + 800]
            round_match = re.search(r"ROUND (\d+)", window)
            if round_match:
                round_number = int(round_match.group(1))
                if slug not in round_map or round_number < (round_map[slug] or 999):
                    round_map[slug] = round_number
            elif slug not in round_map:
                round_map[slug] = None
        return round_map
