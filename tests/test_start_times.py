import copy
import json
from datetime import date
from pathlib import Path

import pytest

from kickoff import feeds, open_schedules
from kickoff.open_schedules import football_events
from kickoff.start_times import combat_identities, fill_missing_start_times, football_teams
from kickoff.web import _event_payload
from tests.test_reviewed_schedules import fake_open_read


def football(*, day="2026-10-28", clock=None, home="CR Flamengo", away="SE Palmeiras"):
    return football_events(
        {"matches": [{"date": day, "time": clock, "team1": home, "team2": away, "round": "Round 30"}]},
        "br.1",
        "2026",
        "https://github.com/openfootball/football.json/blob/" + "a" * 40 + "/2026/br.1.json",
    )[0]


def espn(*, clock="2026-10-28T23:30Z", valid=True, home="819", away="2029", identity="123"):
    return {
        "id": identity,
        "date": clock,
        "links": [{"href": f"https://www.espn.com/soccer/match/_/gameId/{identity}"}],
        "status": {"type": {"name": "STATUS_SCHEDULED"}},
        "competitions": [
            {
                "date": clock,
                "timeValid": valid,
                "competitors": [
                    {"homeAway": "home", "team": {"id": home}},
                    {"homeAway": "away", "team": {"id": away}},
                ],
            }
        ],
    }


def answer(monkeypatch, rows):
    calls = []
    monkeypatch.setattr(feeds, "get_json", lambda url: calls.append(url) or {"events": rows})
    return calls


def test_brazil_clock_is_refreshed_with_exact_teams_date_timezone_and_attribution(monkeypatch):
    event = football()
    identity, source = event.event_id, event.source_url
    config = football_teams()["BRASILEIRAO"]["teams"]
    row = espn(home=config["CR Flamengo"], away=config["SE Palmeiras"])
    calls = answer(monkeypatch, [row])
    receipts = fill_missing_start_times([event], 2026)
    assert calls == [f"{feeds.ESPN}/soccer/bra.1/scoreboard?dates=2026&limit=1000"]
    assert event.event_id == identity
    assert event.calendar_date == event.end_calendar_date == "2026-10-28"
    assert event.start_time_utc == "2026-10-28T23:30:00Z"
    assert event.start_time_local == "2026-10-28T20:30:00-03:00"
    assert event.timezone == "America/Sao_Paulo"
    assert event.source == "espn" and event.source_url == row["links"][0]["href"]
    assert event.country is None  # A domestic league country is not venue evidence.
    assert _event_payload(event)["source_url"] == event.source_url
    assert receipts[0]["clocks_added"] == [
        {
            "event_id": identity,
            "schedule_source_url": source,
            "time_source_url": event.source_url,
        }
    ]
    assert len(receipts[0]["canonical_json_sha256"]) == 64
    # A subsequent refresh uses the new source clock, with no cached one-off data.
    changed = football()
    row["date"] = row["competitions"][0]["date"] = "2026-10-29T00:00Z"
    fill_missing_start_times([changed], 2026)
    assert changed.start_time_local == "2026-10-28T21:00:00-03:00"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda row: row["competitions"][0].update(timeValid=False),
        lambda row: row["competitions"][0].pop("timeValid"),
        lambda row: row.update(date="2026-10-29T23:30Z"),
        lambda row: row["competitions"][0].update(date="2026-10-28T22:30Z"),
        lambda row: row.update(status={"type": {"name": "STATUS_POSTPONED"}}),
        lambda row: row["competitions"][0].update(status={"type": {"name": "STATUS_CANCELED"}}),
        lambda row: row["competitions"][0].update(status={"type": {"detail": "TBD"}}),
        lambda row: row["competitions"][0]["competitors"].reverse(),
    ],
)
def test_uncertain_clocks_do_not_mutate_source_date_or_identity(monkeypatch, mutation):
    event = football()
    before = event.to_dict()
    config = football_teams()["BRASILEIRAO"]["teams"]
    row = espn(home=config["CR Flamengo"], away=config["SE Palmeiras"])
    mutation(row)
    # Array order is irrelevant, but swapping home and away is not a match.
    if row["competitions"][0]["competitors"][0]["homeAway"] == "away":
        for c in row["competitions"][0]["competitors"]:
            c["homeAway"] = "away" if c["homeAway"] == "home" else "home"
    answer(monkeypatch, [row])
    assert not fill_missing_start_times([event], 2026)[0]["clocks_added"]
    assert event.to_dict() == before


def test_duplicate_or_unreviewed_soccer_identity_does_not_choose_a_clock(monkeypatch):
    row = espn(
        home=football_teams()["BRASILEIRAO"]["teams"]["CR Flamengo"],
        away=football_teams()["BRASILEIRAO"]["teams"]["SE Palmeiras"],
    )
    for rows, event in [([row, copy.deepcopy(row)], football()), ([row], football(home="Flamengo Women"))]:
        before = event.to_dict()
        answer(monkeypatch, rows)
        fill_missing_start_times([event], 2026)
        assert event.to_dict() == before


def test_existing_clocks_multiday_tournaments_and_final_date_markers_do_not_fetch(monkeypatch):
    timed = football(clock="19:00")
    span = football()
    span.end_calendar_date = "2026-10-29"
    final = football()
    final.tags.append("final date only")
    span.event_id += "-span"
    final.event_id += "-final"
    events = [timed, span, final]
    before = [e.to_dict() for e in events]
    calls = answer(monkeypatch, [])
    assert fill_missing_start_times(events, 2026) == []
    assert calls == [] and [e.to_dict() for e in events] == before


@pytest.mark.parametrize("payload", [{}, {"events": None}, {"events": "missing"}])
def test_missing_collection_fails_refresh(monkeypatch, payload):
    monkeypatch.setattr(feeds, "get_json", lambda _: payload)
    with pytest.raises(ValueError):
        fill_missing_start_times([football()], 2026)


def test_missing_timezone_and_possible_truncation_fail_refresh(monkeypatch):
    row = espn(
        clock="2026-10-28T23:30",
        home=football_teams()["BRASILEIRAO"]["teams"]["CR Flamengo"],
        away=football_teams()["BRASILEIRAO"]["teams"]["SE Palmeiras"],
    )
    answer(monkeypatch, [row])
    with pytest.raises(ValueError, match="timezone"):
        fill_missing_start_times([football()], 2026)
    answer(monkeypatch, [row] * 1000)
    with pytest.raises(ValueError, match="truncated"):
        fill_missing_start_times([football()], 2026)


def test_combat_card_uses_reviewed_identity_and_header_block_not_main_bout(monkeypatch):
    event = feeds.make_event(
        source="wikipedia",
        league="PFL",
        sport="combat",
        upstream_id="unused",
        season="2026",
        title="PFL San Diego: McKee vs. Isbulaev",
        utc=None,
        day="2026-06-27",
        event_type="tournament",
        source_url="https://en.wikipedia.org/",
    )
    event.event_id = "pfl-2026-global-08"
    identity = combat_identities()[event.event_id]
    row = espn(identity=identity["espn_id"], clock="2026-06-28T00:00Z")
    main = copy.deepcopy(row["competitions"][0])
    main["date"] = "2026-06-28T03:00Z"
    row["competitions"].append(main)
    answer(monkeypatch, [row])
    fill_missing_start_times([event], 2026)
    assert event.event_id == "pfl-2026-global-08"
    assert event.start_time_utc == "2026-06-28T00:00:00Z"
    assert event.start_time_local == "2026-06-27T17:00:00-07:00"
    assert event.calendar_date == "2026-06-27" and event.source == "espn"


def test_doubleheader_matches_primary_game_number_not_first_matching_pair(monkeypatch):
    game = {
        "gamePk": 824460,
        "gameNumber": 2,
        "gameDate": "2026-04-05T17:10Z",
        "officialDate": "2026-04-05",
        "gameType": "R",
        "season": "2026",
        "status": {"startTimeTBD": True, "detailedState": "Final"},
        "teams": {"home": {"team": {"name": "Cleveland Guardians"}}, "away": {"team": {"name": "Chicago Cubs"}}},
    }
    monkeypatch.setattr(feeds, "get_json", lambda _: {"dates": [{"games": [game]}]})
    event = feeds.mlb_events(2026)[0]
    assert event.raw_source_payload["game_number"] == 2
    rows = []
    for number, clock in [(1, "17:10"), (2, "20:30")]:
        row = espn(clock=f"2026-04-05T{clock}Z", identity=f"game-{number}")
        row["competitions"][0].update(notes=[{"headline": f"Doubleheader - Game {number}"}])
        for c in row["competitions"][0]["competitors"]:
            c["team"]["displayName"] = "Cleveland Guardians" if c["homeAway"] == "home" else "Chicago Cubs"
        rows.append(row)
    calls = answer(monkeypatch, rows)
    fill_missing_start_times([event], 2026)
    assert event.event_id == "mlb-mlb-824460" and event.start_time_utc == "2026-04-05T20:30:00Z"
    assert "dates=20260405&" in calls[0]
    assert event.source_url.endswith("game-2")
    # An unnumbered doubleheader is ambiguous, even if both clocks are valid.
    event.source = "mlb"
    event.start_time_utc = event.start_time_local = None
    event.raw_source_payload = {}
    fill_missing_start_times([event], 2026)
    assert event.start_time_utc is None


def test_export_keeps_both_source_receipts_and_espn_license(monkeypatch, tmp_path):
    monkeypatch.setattr(open_schedules, "read_url", fake_open_read)
    original = open_schedules.football_events

    def missing_brazil(payload, key, season, source_url):
        if key == "br.1":
            payload = {"matches": [{"date": "2026-10-28", "team1": "CR Flamengo", "team2": "SE Palmeiras"}]}
        return original(payload, key, season, source_url)

    monkeypatch.setattr(open_schedules, "football_events", missing_brazil)
    config = football_teams()["BRASILEIRAO"]["teams"]
    answer(monkeypatch, [espn(home=config["CR Flamengo"], away=config["SE Palmeiras"])])
    bundle = json.loads(open_schedules.refresh_open_schedules(2026, tmp_path, enrich_times=True).read_text())
    event = next(e for e in bundle["events"] if e["league"] == "BRASILEIRAO")
    assert event["source"] == "espn" and event["start_time_utc"]
    assert bundle["data_licenses"]["espn"] == feeds.SOURCES["espn"]["license"]
    assert any(n["name"] == "openfootball contributors" for n in bundle["sources"])
    assert any(n["name"] == "ESPN" for n in bundle["sources"])
    assert next(r for r in bundle["input_evidence"] if r.get("clocks_added"))["clocks_added"][0]["schedule_source_url"]
    assert "9 football leagues" in bundle["coverage"]


def test_reviewed_joins_are_unique_and_carry_source_and_check_date():
    for config in football_teams().values():
        date.fromisoformat(config["checked_date"])
        assert config["source_url"].startswith(f"{feeds.ESPN}/soccer/{config['espn_path']}/")
        assert len(config["teams"]) == len(set(config["teams"].values()))
        assert all(identity.isdigit() for identity in config["teams"].values())
    payload = json.loads((Path(__file__).parents[1] / "src/kickoff/config/combat-espn-events.json").read_text())
    date.fromisoformat(payload["checked_date"])
    assert len(payload["events"]) == len(combat_identities())


def test_enrichment_failure_stops_before_writing_bundle(monkeypatch, tmp_path):
    monkeypatch.setattr(open_schedules, "read_url", fake_open_read)

    def fail(*_):
        raise OSError("ESPN clock lookup unavailable")

    monkeypatch.setattr(open_schedules, "fill_missing_start_times", fail)
    with pytest.raises(OSError, match="clock lookup"):
        open_schedules.refresh_open_schedules(2026, tmp_path, enrich_times=True)
    assert not (tmp_path / "2026.json").exists()
