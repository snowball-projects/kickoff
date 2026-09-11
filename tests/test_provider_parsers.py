import json
import tempfile
import unittest
from datetime import timezone
from pathlib import Path
from unittest.mock import patch

from sportsbro.models import ProviderOptions
from sportsbro.providers.f1 import F1Provider
from sportsbro.providers.nascar_cup import NascarCupProvider
from sportsbro.providers.nba import NBAProvider
from sportsbro.providers.static_csv import StaticScheduleProvider
from sportsbro.settings import Settings


class ProviderParserTests(unittest.TestCase):
    def test_f1_session_classification_supports_full_weekend_without_support_series(self) -> None:
        sessions = {
            "Practice 1 - Australian Grand Prix": "practice",
            "Qualifying - Australian Grand Prix": "qualifying",
            "Sprint Shootout - Australian Grand Prix": "sprint_qualifying",
            "Sprint - Australian Grand Prix": "sprint",
            "Warm-up - Australian Grand Prix": "warm_up",
            "Race - Australian Grand Prix": "race",
            "Porsche Supercup - Australian Grand Prix": None,
            "Formula 2 Sprint - Australian Grand Prix": None,
        }
        for name, expected in sessions.items():
            with self.subTest(name=name):
                self.assertEqual(F1Provider._session_kind({"name": name}), expected)

    def test_f1_race_only_and_full_weekend_are_distinct_views(self) -> None:
        season_html = '<a href="/en/racing/2026/australia">ROUND 1</a>'
        payload = {
            "@type": "SportsEvent",
            "name": "Australian Grand Prix",
            "location": {"name": "Melbourne"},
            "subEvent": [
                {
                    "@id": "weekend#Practice1",
                    "name": "Practice 1 - Australian Grand Prix",
                    "startDate": "2026-03-06T01:30:00Z",
                },
                {
                    "@id": "weekend#Qualifying",
                    "name": "Qualifying - Australian Grand Prix",
                    "startDate": "2026-03-07T05:00:00Z",
                },
                {
                    "@id": "weekend#Support",
                    "name": "Porsche Supercup - Australian Grand Prix",
                    "startDate": "2026-03-07T07:00:00Z",
                },
                {
                    "@id": "weekend#Race",
                    "name": "Race - Australian Grand Prix",
                    "startDate": "2026-03-08T04:00:00Z",
                },
            ],
        }
        page_html = f'<script type="application/ld+json">{json.dumps(payload)}</script>'
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings.load(Path(temp_dir))
            provider = F1Provider()
            with patch("sportsbro.providers.f1.fetch_text", side_effect=[season_html, page_html]):
                race_only = provider.fetch(2026, settings, ProviderOptions(motorsport_view="race_only"))
            with patch("sportsbro.providers.f1.fetch_text", side_effect=[season_html, page_html]):
                full_weekend = provider.fetch(2026, settings, ProviderOptions(motorsport_view="full_weekend"))

        self.assertEqual([event.event_type for event in race_only.events], ["race"])
        self.assertEqual(
            [event.event_type for event in full_weekend.events],
            ["practice", "qualifying", "race"],
        )
        self.assertTrue(all(not event.is_support_event for event in full_weekend.events))

    def test_nba_pdf_parser_reads_basic_line(self) -> None:
        provider = NBAProvider()
        line = "Tue. 10/21/25 Houston at Oklahoma City 6:30 PM 7:30 PM NBC/Peacock R"
        with (
            patch("sportsbro.timeutils.get_zoneinfo", return_value=timezone.utc),
            patch("sportsbro.providers.nba.get_zoneinfo", return_value=timezone.utc),
        ):
            events = provider._parse_pdf_lines([line], 2026)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.title, "Houston Rockets at Oklahoma City Thunder")
        self.assertEqual(event.timezone, "America/Chicago")
        self.assertEqual(event.calendar_date, "2025-10-21")

    def test_nascar_pdf_parser_reads_basic_line(self) -> None:
        provider = NascarCupProvider()
        lines = [
            "CLASH (BOWMAN GRAY) SUN | FEB 1 | 8 PM | FOX",
            "DAYTONA 500 SUN | FEB 15 | 2:30 PM | FOX",
            "DAYTONA SAT | FEB 14 | 5 PM | CW",
        ]
        with (
            patch("sportsbro.timeutils.get_zoneinfo", return_value=timezone.utc),
            patch("sportsbro.providers.nascar_cup.get_zoneinfo", return_value=timezone.utc),
        ):
            events, _metadata = provider._parse_pdf_lines(
                lines,
                2026,
                ProviderOptions(event_scope="all_published", include_special_events=True),
            )
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].title, "Cook Out Clash")
        self.assertEqual(events[1].title, "Daytona 500")

    def test_nascar_motorsport_view_controls_qualifying(self) -> None:
        provider = NascarCupProvider()
        lines = [
            "CLASH (BOWMAN GRAY) SUN | FEB 1 | 8 PM | FOX",
            "DUELS (DAYTONA) THU | FEB 12 | 7 PM | FS1",
            "DAYTONA 500 SUN | FEB 15 | 2:30 PM | FOX",
            "DAYTONA SAT | FEB 14 | 5 PM | CW",
        ]
        with (
            patch("sportsbro.timeutils.get_zoneinfo", return_value=timezone.utc),
            patch("sportsbro.providers.nascar_cup.get_zoneinfo", return_value=timezone.utc),
        ):
            race_only, _metadata = provider._parse_pdf_lines(
                lines,
                2026,
                ProviderOptions(include_special_events=True, motorsport_view="race_only"),
            )
            full_weekend, _metadata = provider._parse_pdf_lines(
                lines,
                2026,
                ProviderOptions(motorsport_view="full_weekend"),
            )

        self.assertEqual([event.event_type for event in race_only], ["race", "race"])
        self.assertEqual([event.event_type for event in full_weekend], ["qualifying", "race"])

    def test_static_schedule_provider_builds_match_event(self) -> None:
        provider = StaticScheduleProvider(
            key="test",
            league="FIFA_WORLD_CUP",
            sport="soccer",
            source_name="reference_csv",
        )
        event = provider._event_from_row(
            {
                "event_id": "fifa-001",
                "title": "Mexico vs South Africa",
                "subtitle": "FIFA World Cup",
                "event_type": "match",
                "season_label": "2026",
                "calendar_date": "2026-06-11",
                "end_calendar_date": "2026-06-11",
                "start_time_utc": "2026-06-11T19:00:00Z",
                "timezone": "UTC",
                "status": "scheduled",
                "venue": "Mexico City Stadium",
                "city": "Mexico City",
                "region": "Mexico City",
                "country": "Mexico",
                "home_name": "Mexico",
                "away_name": "South Africa",
                "round_or_stage": "Group A",
                "competition_phase": "group_stage",
                "tags": "fifa-world-cup|soccer|group-stage",
            },
            2026,
        )
        self.assertEqual(event.league, "FIFA_WORLD_CUP")
        self.assertEqual(event.home_participant.name, "Mexico")
        self.assertEqual(event.away_participant.name, "South Africa")
        self.assertEqual(event.competition_phase, "group_stage")
