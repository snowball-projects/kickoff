import json
from collections import Counter

import pytest

from kickoff import feeds
from kickoff.semantics import classification_fields
from kickoff.web import _event_payload
from tests.test_feeds import espn_game, serve
from tests.test_reviewed_schedules import ROOT


@pytest.mark.parametrize("status", ["STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_CANCELLED", "STATUS_SUSPENDED"])
@pytest.mark.parametrize("location", ["event", "competition", "both_disagree"])
def test_espn_withholds_unplayable_games_in_both_status_shapes(status, location):
    row = espn_game("1", "2026-11-01T19:00Z", "Home", "Away")
    if location == "event":
        row["status"]["type"]["name"] = status
    else:
        row["competitions"][0]["status"] = {"type": {"name": status}}
        if location == "competition":
            del row["status"]  # Actual NBA team-schedule response shape.
    event = feeds._espn_event(
        row, league="NBA", sport="basketball", zone=feeds.EASTERN, fallback_url="https://www.nba.com/schedule"
    )
    assert event is None


def test_nba_team_schedule_preserves_valid_games_but_not_postponed(monkeypatch):
    valid = espn_game("1", "2026-11-01T19:00Z", "Home", "Away")
    postponed = espn_game("2", "2026-11-02T19:00Z", "Home", "Away")
    for row, status in [(valid, "STATUS_SCHEDULED"), (postponed, "STATUS_POSTPONED")]:
        del row["status"]
        row["competitions"][0]["status"] = {"type": {"name": status}}

    def get_json(url, **_):
        if url.endswith("/teams"):
            return {"sports": [{"leagues": [{"teams": [{"team": {"id": str(i)}} for i in range(30)]}]}]}
        return {"events": [valid, postponed]}

    monkeypatch.setattr(feeds, "get_json", get_json)
    assert [event.event_id for event in feeds.nba_events(2026)] == ["espn-nba-1"]


@pytest.mark.parametrize(
    "name", ["All-Star Race", "NASCAR Cup Series All Star Race", "all star race", "Clash", "Duel #1"]
)
def test_nascar_exhibition_spelling_variants(monkeypatch, name):
    row = {"id": "1", "date": "2026-05-17T23:00Z", "name": name, "competitions": [{}]}
    serve(monkeypatch, {"racing/nascar-premier/scoreboard": {"events": [row]}})
    (event,) = feeds.FEEDS["NASCAR_CUP"][1](2026)
    assert _event_payload(event)["is_exhibition"]
    assert event.competition_phase == "exhibition"


def test_phase_overrides_keep_exact_reviewed_identities_and_evidence():
    payload = json.loads((ROOT / "src/kickoff/config/feed-phases.json").read_text())
    assert payload["schema_version"] == 1
    rows = payload["events"]
    assert len({row["event_id"] for row in rows}) == len(rows) == 13
    reviewed, sources = {}, {}
    for path in (ROOT / "data/reviewed").glob("2026-*.json"):
        registry = json.loads(path.read_text())
        reviewed.update({event["id"]: event for event in registry["events"]})
        sources.update({source["id"]: source for source in registry["sources"]})
    for row in rows:
        original = reviewed[row["reviewed_event_id"]]
        assert original["league"] == row["league"]
        assert original["competition_phase"] == row["competition_phase"] == "postseason"
        assert sources[original["source_id"]]["url"] == row["source_url"]


@pytest.mark.parametrize("override", list(feeds._phase_overrides().values()), ids=lambda row: row["event_id"])
def test_playoff_phase_survives_rescheduling_and_is_exported(monkeypatch, override):
    league = override["league"]
    row = {
        "id": override["event_id"].split("-", 2)[2],
        "name": override["title"],
        "date": "2026-12-01T19:00Z",  # Changed from the reviewed date; identity is unchanged.
        "season": {"year": 2026, "slug": "regular-season"},
        "competitions": [{}],
    }
    serve(monkeypatch, {"/scoreboard": {"events": [row]}})
    (event,) = feeds.FEEDS[league][1](2026)
    assert {key: _event_payload(event)[key] for key in classification_fields("postseason")} == classification_fields(
        "postseason"
    )
    assert feeds.espn_calendar_phase(league, row["id"], "2027", row["name"]) == "regular_season"
    assert feeds.espn_calendar_phase(league, "unreviewed", "2026", row["name"]) == "regular_season"


def test_published_snapshot_retains_playoffs_and_all_star_phase():
    events = json.loads((ROOT / "data/published/2026.json").read_text())["events"]
    nascar = [event for event in events if event["league"] == "NASCAR_CUP"]
    pga = [event for event in events if event["league"] == "PGA_TOUR"]
    assert Counter(event["competition_phase"] for event in nascar) == {
        "regular_season": 26,
        "postseason": 10,
        "exhibition": 4,
    }
    assert sum(event["is_postseason"] for event in pga) == 3
    assert next(event for event in nascar if "All Star" in event["title"])["is_exhibition"]
