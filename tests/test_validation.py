import unittest

from sportsbro.models import CalendarEvent, Participant
from sportsbro.normalize import dedupe_events, stable_event_id
from sportsbro.semantics import classification_fields, is_malformed_event
from sportsbro.validation import schema_field_names, validate_batch


def _sample_event(event_id: str) -> CalendarEvent:
    away = Participant(name="Away Team", participant_id="away", role="away")
    home = Participant(name="Home Team", participant_id="home", role="home")
    return CalendarEvent(
        event_id=event_id,
        source="test",
        sport="basketball",
        league="NBA",
        season="2025-2026",
        event_type="game",
        title="Away Team at Home Team",
        subtitle="Regular Season",
        start_time_utc="2025-10-21T23:30:00Z",
        start_time_local="2025-10-21T19:30:00-04:00",
        timezone="America/New_York",
        status="scheduled",
        venue="Test Arena",
        city="New York",
        region="New York",
        country="United States",
        participants=[away, home],
        home_participant=home,
        away_participant=away,
        round_or_stage="Regular Season",
        week_label=None,
        calendar_date="2025-10-21",
        end_calendar_date="2025-10-21",
        tags=["test"],
        raw_source_payload={"id": "123"},
        **classification_fields("regular_season"),
    )


class ValidationTests(unittest.TestCase):
    def test_schema_contains_required_fields(self) -> None:
        fields = schema_field_names()
        for field in [
            "event_id",
            "source",
            "sport",
            "league",
            "season",
            "event_type",
            "title",
            "subtitle",
            "start_time_utc",
            "start_time_local",
            "timezone",
            "status",
            "venue",
            "city",
            "region",
            "country",
            "participants",
            "home_participant",
            "away_participant",
            "round_or_stage",
            "week_label",
            "calendar_date",
            "end_calendar_date",
            "competition_phase",
            "is_regular_season",
            "is_postseason",
            "is_exhibition",
            "is_support_event",
            "tags",
            "raw_source_payload",
        ]:
            self.assertIn(field, fields)

    def test_dedupe_events_keeps_one_copy(self) -> None:
        first = _sample_event("same-id")
        second = _sample_event("same-id")
        deduped = dedupe_events([first, second])
        self.assertEqual(len(deduped), 1)

    def test_validate_batch_accepts_valid_event(self) -> None:
        errors = validate_batch([_sample_event(stable_event_id("a", "b"))])
        self.assertEqual(errors, [])

    def test_malformed_event_rejects_case_insensitive_empty_matchup(self) -> None:
        event = _sample_event("empty-matchup")
        event.title = " AT "
        self.assertTrue(is_malformed_event(event))
