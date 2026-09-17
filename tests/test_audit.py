import unittest

from kickoff.audit import summarize_events
from kickoff.models import CalendarEvent, Participant
from kickoff.semantics import classification_fields


def _sample_event(event_id: str, title: str, calendar_date: str) -> CalendarEvent:
    away = Participant(name="Away Team", participant_id="away", role="away")
    home = Participant(name="Home Team", participant_id="home", role="home")
    return CalendarEvent(
        event_id=event_id,
        source="test",
        sport="basketball",
        league="NBA",
        season="2025-2026",
        event_type="game",
        title=title,
        subtitle="NBA Regular Season",
        start_time_utc="2025-10-21T23:30:00Z",
        start_time_local="2025-10-21T19:30:00-04:00",
        timezone="America/New_York",
        status="scheduled",
        venue="Arena",
        city="New York",
        region="New York",
        country="United States",
        participants=[away, home],
        home_participant=home,
        away_participant=away,
        round_or_stage="Regular Season",
        week_label=None,
        calendar_date=calendar_date,
        end_calendar_date=calendar_date,
        tags=["test"],
        raw_source_payload={"id": event_id},
        **classification_fields("regular_season"),
    )


class AuditTests(unittest.TestCase):
    def test_summarize_events_reports_duplicate_candidates(self) -> None:
        events = [
            _sample_event("1", "Away Team at Home Team", "2025-10-21"),
            _sample_event("2", "Away Team at Home Team", "2025-10-21"),
        ]
        summary = summarize_events(events)
        self.assertEqual(summary["total_event_count"], 2)
        self.assertEqual(summary["counts_by_event_type"], {"game": 2})
        self.assertEqual(summary["counts_by_competition_phase"], {"regular_season": 2})
        self.assertEqual(len(summary["duplicate_candidates"]), 1)
