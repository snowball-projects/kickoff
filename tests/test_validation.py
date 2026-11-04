import unittest
from dataclasses import replace

import pytest

from kickoff.models import CalendarEvent, Participant
from kickoff.normalize import stable_event_id
from kickoff.semantics import classification_fields, is_malformed_event
from kickoff.validation import schema_field_names, validate_batch


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

    def test_validate_batch_accepts_valid_event(self) -> None:
        errors = validate_batch([_sample_event(stable_event_id("a", "b"))])
        self.assertEqual(errors, [])

    def test_malformed_event_rejects_case_insensitive_empty_matchup(self) -> None:
        event = _sample_event("empty-matchup")
        event.title = " AT "
        self.assertTrue(is_malformed_event(event))


@pytest.mark.parametrize("role", ["home", "away"])
def test_duplicate_canonical_roles_are_rejected(role):
    event = _sample_event("duplicate-role")
    event.participants.append(replace(getattr(event, f"{role}_participant")))
    assert any(f"duplicate {role} participant role" in error for error in validate_batch([event]))


@pytest.mark.parametrize("role", ["home", "away"])
def test_known_source_side_cannot_disappear_from_participants(role):
    event = _sample_event("missing-known-role")
    event.participants = [p for p in event.participants if p.role != role]
    assert any(f"known {role} participant must match" in error for error in validate_batch([event]))


@pytest.mark.parametrize(
    "change", [{"record": "2-1"}, {"final_score": 3}, {"metadata": {"logo_source_url": "https://example.com/team"}}]
)
def test_canonical_participants_cannot_lose_known_side_facts(change):
    event = _sample_event("different-team-facts")
    event.participants = [replace(p, **change) if p.role == "home" else p for p in event.participants]
    assert any("known home participant must match" in error for error in validate_batch([event]))


@pytest.mark.parametrize("shape", ["empty", "home-only", "away-only", "unassigned"])
def test_source_appointments_and_unassigned_matches_keep_their_roles(shape):
    event = _sample_event("source-exception")
    if shape == "empty":
        event.participants = []
        event.home_participant = event.away_participant = None
    elif shape == "home-only":
        event.participants = [event.home_participant]
        event.away_participant = None
    elif shape == "away-only":
        event.participants = [event.away_participant]
        event.home_participant = None
    else:
        event.sport, event.league, event.event_type = "cricket", "IPL", "match"
        event.participants = [replace(p, role=None) for p in event.participants]
        event.home_participant = event.away_participant = None
    before = event.to_dict()
    assert validate_batch([event]) == []
    assert event.to_dict() == before
