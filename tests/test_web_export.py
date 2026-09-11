import json
import tempfile
import unittest
from pathlib import Path

from sportsbro.models import CalendarEvent, Participant
from sportsbro.settings import Settings
from sportsbro.web import export_web_bundle


class WebExportTests(unittest.TestCase):
    def test_export_is_deterministic_and_excludes_private_source_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            season_root = root / "data" / "normalized" / "2026"
            season_root.mkdir(parents=True)
            event = CalendarEvent(
                event_id="nba-2026-example",
                source="official_schedule",
                sport="basketball",
                league="NBA",
                season="2026",
                event_type="game",
                title="Visitors at Hosts",
                subtitle=None,
                start_time_utc="2026-01-02T01:00:00Z",
                start_time_local="2026-01-01T19:00:00-06:00",
                timezone="America/Chicago",
                status="scheduled",
                venue="Example Arena",
                city="Chicago",
                region="Illinois",
                country="United States",
                participants=[Participant(name="Visitors", metadata={"private": "participant source"})],
                home_participant=Participant(name="Hosts", role="home"),
                away_participant=Participant(name="Visitors", role="away"),
                calendar_date="2026-01-01",
                end_calendar_date="2026-01-03",
                competition_phase="regular_season",
                is_regular_season=True,
                tags=["nba"],
                raw_source_payload={"private": "provider payload"},
            )
            (season_root / "all_events.json").write_text(
                json.dumps([event.to_dict()]),
                encoding="utf-8",
            )
            (season_root / "manifest.json").write_text(
                json.dumps(
                    {
                        "season": 2026,
                        "providers": [
                            {
                                "provider": "nba",
                                "season": 2026,
                                "event_count": 1,
                                "warnings": [],
                                "raw_artifacts": ["private-source.json"],
                                "metadata": {"semantics": {"default_behavior": "Regular season"}},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            settings = Settings.load(root)
            output_dir = root / "public"

            bundle_path = export_web_bundle(settings, 2026, output_dir)
            first_export = bundle_path.read_text(encoding="utf-8")
            export_web_bundle(settings, 2026, output_dir)

            self.assertEqual(first_export, bundle_path.read_text(encoding="utf-8"))
            self.assertNotIn("raw_source_payload", first_export)
            self.assertNotIn("participant source", first_export)
            self.assertNotIn("private-source.json", first_export)
            payload = json.loads(first_export)
            self.assertEqual(payload["schema_version"], "1")
            self.assertEqual(payload["events"][0]["end_calendar_date"], "2026-01-03")
            self.assertEqual(payload["events"][0]["home_participant"]["name"], "Hosts")
