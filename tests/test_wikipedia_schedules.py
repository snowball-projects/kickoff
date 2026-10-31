import copy
import json
from collections import Counter
from pathlib import Path

import pytest

from kickoff.reviewed_schedules import reviewed_events

ROOT = Path(__file__).resolve().parents[1]


def registry(year):
    return json.loads((ROOT / f"data/reviewed/{year}-wikipedia-schedules.json").read_text())


@pytest.mark.parametrize(
    ("year", "expected"),
    [
        (
            2026,
            {
                "MOTOGP": 22,
                "WEC": 9,
                "TOUR_DE_FRANCE": 21,
                "GIRO_D_ITALIA": 21,
                "VUELTA_A_ESPANA": 20,
                "UCI_WORLD_TOUR": 21,
                "DIAMOND_LEAGUE": 15,
                "IPL": 74,
            },
        ),
        (
            2027,
            {
                "MOTOGP": 22,
                "WEC": 10,
                "TOUR_DE_FRANCE": 21,
                "GIRO_D_ITALIA": 1,
                "VUELTA_A_ESPANA": 1,
                "UCI_WORLD_TOUR": 21,
                "WORLD_ATHLETICS_CHAMPIONSHIPS": 1,
                "CRICKET_WORLD_CUP": 57,
                "FIFA_WOMENS_WORLD_CUP": 64,
            },
        ),
    ],
)
def test_complete_pinned_schedules_and_every_fact_has_its_checked_source(year, expected):
    payload = registry(year)
    events, notices = reviewed_events(payload, year)
    assert Counter(event.league for event in events) == expected
    assert len(notices) == len(payload["sources"])
    assert all(
        event.facts_checked_date == "2026-10-31" and event.facts_source_url == event.source_url for event in events
    )
    assert all(source["license"] == "CC BY-SA 4.0" and source["revision"] in source["input_url"] for source in notices)


def test_only_source_explicit_wikipedia_clocks_become_instants():
    current, _ = reviewed_events(registry(2026), 2026)
    future, _ = reviewed_events(registry(2027), 2027)
    ipl = [event for event in current if event.league == "IPL"]
    cricket = [event for event in future if event.league == "CRICKET_WORLD_CUP"]
    assert len(ipl) == 74 and all(event.timezone == "Asia/Kolkata" for event in ipl)
    assert ipl[0].start_time_utc == "2026-03-28T14:00:00Z"
    assert {p.name for p in ipl[0].participants} == {"Sunrisers Hyderabad", "Royal Challengers Bengaluru"}
    assert len(cricket) == 57 and all(event.timezone == "Etc/GMT-2" for event in cricket)
    assert cricket[0].start_time_utc == "2027-10-02T08:00:00Z"
    assert all(
        event.start_time_source == "wikipedia" and event.start_time_source_url == event.source_url
        for event in ipl + cricket
    )
    assert all(
        event.start_time_utc is None for event in current + future if event.league not in {"IPL", "CRICKET_WORLD_CUP"}
    )


@pytest.mark.parametrize("change", ["clock_evidence", "clock_timezone", "checked_date", "different_zone", "span"])
def test_a_wikipedia_clock_cannot_be_inferred_without_its_source_evidence(change):
    payload = copy.deepcopy(registry(2026))
    event = next(row for row in payload["events"] if row["league"] == "IPL")
    source = next(row for row in payload["sources"] if row["id"] == event["source_id"])
    if change in {"clock_evidence", "clock_timezone"}:
        source.pop(change)
    elif change == "checked_date":
        event.pop("checked_date")
    elif change == "different_zone":
        event["event_timezone"] = "Europe/London"
    else:
        event["end_date"] = "2026-03-29"
    with pytest.raises((ValueError, KeyError)):
        reviewed_events(payload, 2026)


def test_cancelled_events_and_unpublished_stages_have_explicit_exclusions():
    current = registry(2026)
    assert any(
        "Stage 3" in item.get("title", "") and item["league"] == "VUELTA_A_ESPANA" for item in current["exclusions"]
    )
    assert {item["title"] for item in current["exclusions"] if item["league"] == "WEC"} == {
        "Qatar 1812 km",
        "8 Hours of Bahrain",
    }
    assert all(
        row.get("round_or_stage") != "Stage 3" for row in current["events"] if row["league"] == "VUELTA_A_ESPANA"
    )
    future = registry(2027)
    assert {item["league"] for item in future["exclusions"]} == {"GIRO_D_ITALIA", "VUELTA_A_ESPANA", "IPL"}
    assert all(
        item["source_url"].startswith("https://") and item["checked_date"] == "2026-10-31"
        for item in current["exclusions"] + future["exclusions"]
    )


def test_wec_published_prologues_and_overnight_le_mans_keep_their_dates():
    for year, expected in [(2026, ("2026-06-13", "2026-06-14")), (2027, ("2027-06-12", "2027-06-13"))]:
        events, _ = reviewed_events(registry(year), year)
        race = next(event for event in events if event.title == "24 Hours of Le Mans")
        assert (race.calendar_date, race.end_calendar_date) == expected
        prologue = next(event for event in events if event.title == "Prologue")
        assert prologue.event_type == "practice" and prologue.competition_phase == "testing"


def test_world_cup_slots_do_not_invent_team_assignments_or_kickoff_times():
    events, _ = reviewed_events(registry(2027), 2027)
    women = [event for event in events if event.league == "FIFA_WOMENS_WORLD_CUP"]
    assert len(women) == 64
    assert Counter(event.round_or_stage for event in women)["Group A"] == 6
    assert all(not event.participants and event.start_time_utc is None for event in women)
    assert all("TBA" not in event.title and "Winner" not in event.title for event in women)
    assert {event.country for event in women} == {"BR"}
    # Only calendar spans are published for these 2027 competitions.
    for league in ["GIRO_D_ITALIA", "VUELTA_A_ESPANA", "WORLD_ATHLETICS_CHAMPIONSHIPS"]:
        selected = [event for event in events if event.league == league]
        assert len(selected) == 1 and selected[0].event_type == "tournament"
