import copy
import json
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError

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
    assert event.source == "openfootball" and event.source_url == source
    assert event.start_time_source == "espn" and event.start_time_source_url == row["links"][0]["href"]
    assert event.country == "Brazil"  # Original domestic-league provenance is retained.
    assert _event_payload(event)["start_time_source_url"] == event.start_time_source_url
    assert receipts[0]["clocks_added"] == [
        {
            "event_id": identity,
            "schedule_source_url": source,
            "time_source_url": event.start_time_source_url,
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


def test_existing_clocks_and_multiday_tournaments_do_not_fetch(monkeypatch):
    timed = football(clock="19:00")
    span = football()
    span.end_calendar_date = "2026-10-29"
    span.event_id += "-span"
    events = [timed, span]
    before = [e.to_dict() for e in events]
    calls = answer(monkeypatch, [])
    assert fill_missing_start_times(events, 2026) == []
    assert calls == [] and [e.to_dict() for e in events] == before


@pytest.mark.parametrize("payload", [{}, {"events": None}, {"events": "missing"}, {"events": [None]}])
def test_malformed_lookup_warns_and_preserves_events(monkeypatch, caplog, payload):
    monkeypatch.setattr(feeds, "get_json", lambda _: payload)
    event = football()
    before = event.to_dict()
    assert fill_missing_start_times([event], 2026) == []
    assert event.to_dict() == before
    assert "ESPN clock lookup failed" in caplog.text
    assert "/soccer/bra.1/scoreboard?dates=2026" in caplog.text


@pytest.mark.parametrize("truncated", [False, True])
def test_missing_timezone_and_possible_truncation_warn_and_preserve_events(monkeypatch, caplog, truncated):
    row = espn(
        clock="2026-10-28T23:30" if not truncated else "2026-10-28T23:30Z",
        home=football_teams()["BRASILEIRAO"]["teams"]["CR Flamengo"],
        away=football_teams()["BRASILEIRAO"]["teams"]["SE Palmeiras"],
    )
    answer(monkeypatch, [row] * (1000 if truncated else 1))
    event = football()
    before = event.to_dict()
    assert fill_missing_start_times([event], 2026) == []
    assert event.to_dict() == before
    assert ("truncated" if truncated else "timezone") in caplog.text


def test_late_malformed_clock_discards_all_changes_from_its_lookup(monkeypatch, caplog):
    # The first event is confirmed before the next event's malformed clock.
    events = [football(), football(day="2026-10-29")]
    before = [event.to_dict() for event in events]
    teams = football_teams()["BRASILEIRAO"]["teams"]
    row = espn(home=teams["CR Flamengo"], away=teams["SE Palmeiras"])
    bad = espn(clock="2026-10-29T23:30Z", home=teams["CR Flamengo"], away=teams["SE Palmeiras"], identity="456")
    bad["competitions"][0]["date"] = "invalid"
    answer(monkeypatch, [row, bad])
    assert fill_missing_start_times(events, 2026) == []
    assert [event.to_dict() for event in events] == before
    assert "ESPN clock lookup failed" in caplog.text


@pytest.mark.parametrize("failed_first", [False, True])
def test_failed_lookup_does_not_discard_other_lookups_or_existing_times(monkeypatch, failed_first):
    missing, timed = football(), football(clock="19:00")
    timed_before = timed.to_dict()
    other = feeds.make_event(
        source="mlb",
        league="MLB",
        sport="baseball",
        upstream_id="123",
        season="2026",
        title="Away at Home",
        utc=None,
        day="2026-10-28",
        home="Home",
        away="Away",
        source_url="https://www.mlb.com/gameday/123",
    )
    row = espn(clock="2026-10-28T20:30Z")
    for competitor in row["competitions"][0]["competitors"]:
        competitor["team"]["displayName"] = "Home" if competitor["homeAway"] == "home" else "Away"

    def get_json(url):
        if "/soccer/" in url:
            raise OSError("ESPN soccer clocks unavailable")
        return {"events": [row]}

    monkeypatch.setattr(feeds, "get_json", get_json)
    events = [missing, other, timed] if failed_first else [other, missing, timed]
    receipts = fill_missing_start_times(events, 2026)
    assert missing.start_time_utc is missing.start_time_local is None
    assert timed.to_dict() == timed_before
    assert other.start_time_utc == "2026-10-28T20:30:00Z"
    assert other.start_time_source_url == row["links"][0]["href"]
    assert len(receipts) == 1 and receipts[0]["clocks_added"][0]["event_id"] == other.event_id


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
    assert event.calendar_date == "2026-06-27" and event.source == "wikipedia"
    assert event.start_time_source == "espn" and event.source_url == "https://en.wikipedia.org/"


def test_doubleheader_matches_primary_game_number_not_first_matching_pair(monkeypatch):
    game = {
        "gamePk": 824460,
        "gameNumber": 2,
        "doubleHeader": "Y",
        "gameDate": "2026-04-05T17:10Z",
        "officialDate": "2026-04-05",
        "gameType": "R",
        "season": "2026",
        "status": {"startTimeTBD": True, "detailedState": "Final"},
        "teams": {"home": {"team": {"name": "Cleveland Guardians"}}, "away": {"team": {"name": "Chicago Cubs"}}},
    }
    monkeypatch.setattr(feeds, "get_json", lambda _: {"dates": [{"games": [game]}]})
    event = feeds.mlb_events(2026)[0]
    assert event.raw_source_payload == {"game_number": 2, "double_header": "Y"}
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
    assert event.start_time_source_url.endswith("game-2")
    assert event.source_url == "https://www.mlb.com/gameday/824460"
    # An unnumbered doubleheader is ambiguous, even if both clocks are valid.
    event.start_time_source = event.start_time_source_url = None
    event.start_time_utc = event.start_time_local = None
    event.raw_source_payload = {}
    fill_missing_start_times([event], 2026)
    assert event.start_time_utc is None


@pytest.mark.parametrize(
    "primary_number,double_header,espn_numbers,sibling_date,expected_utc",
    [
        # A unique same-day match is not enough to identify a doubleheader game.
        (2, "Y", [1], None, None),
        (2, "Y", [1, 2], "2026-04-06", None),
        (2, "Y", [None], None, None),
        (1, "Y", [None], None, None),
        (1, "S", [2], None, None),
        (None, "Y", [1], None, None),
        # A game number alone also identifies a doubleheader, without the flag.
        (2, None, [1], None, None),
        (2, None, [None], None, None),
        # Independent numbering can confirm a sole candidate without its sibling.
        (2, "Y", [2], None, "2026-04-05T20:30:00Z"),
        (1, "Y", [1], None, "2026-04-05T20:30:00Z"),
        # Ordinary single games still use a unique exact team/date match.
        (1, "N", [None], None, "2026-04-05T20:30:00Z"),
    ],
)
def test_doubleheader_identity_is_required_when_sibling_is_missing(
    monkeypatch, primary_number, double_header, espn_numbers, sibling_date, expected_utc
):
    event = feeds.make_event(
        source="mlb",
        league="MLB",
        sport="baseball",
        upstream_id="824460",
        season="2026",
        title="Chicago Cubs at Cleveland Guardians",
        utc=None,
        day="2026-04-05",
        home="Cleveland Guardians",
        away="Chicago Cubs",
        source_url="https://www.mlb.com/gameday/824460",
    )
    event.raw_source_payload = {"game_number": primary_number, "double_header": double_header}
    before = event.to_dict()
    rows = []
    for index, number in enumerate(espn_numbers):
        day = sibling_date if index == 1 else "2026-04-05"
        row = espn(clock=f"{day}T20:30Z", identity=f"candidate-{index}")
        if number is not None:
            row["competitions"][0]["notes"] = [{"headline": f"Doubleheader - Game {number}"}]
        for competitor in row["competitions"][0]["competitors"]:
            competitor["team"]["displayName"] = (
                "Cleveland Guardians" if competitor["homeAway"] == "home" else "Chicago Cubs"
            )
        rows.append(row)
    answer(monkeypatch, rows)
    receipts = fill_missing_start_times([event], 2026)
    assert event.start_time_utc == expected_utc
    if expected_utc is None:
        assert event.to_dict() == before
        assert receipts[0]["clocks_added"] == []
    else:
        assert event.source == "mlb" and event.start_time_source == "espn"
        assert event.source_url == before["source_url"]
        assert event.event_id == before["event_id"] and event.calendar_date == before["calendar_date"]


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
    assert event["source"] == "openfootball" and event["start_time_source"] == "espn" and event["start_time_utc"]
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


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError("ESPN clock lookup timed out"),
        URLError("ESPN clock lookup unavailable"),
        HTTPError("https://example.org", 503, "ESPN unavailable", {}, None),
        json.JSONDecodeError("malformed ESPN clock feed", "", 0),
    ],
)
def test_failed_clock_lookup_still_exports_date_only_events(monkeypatch, tmp_path, caplog, failure):
    monkeypatch.setattr(open_schedules, "read_url", fake_open_read)
    original = open_schedules.football_events

    def missing_brazil(payload, key, season, source_url):
        if key == "br.1":
            payload = {"matches": [{"date": "2026-10-28", "team1": "CR Flamengo", "team2": "SE Palmeiras"}]}
        return original(payload, key, season, source_url)

    monkeypatch.setattr(open_schedules, "football_events", missing_brazil)

    def fail(_):
        raise failure

    monkeypatch.setattr(feeds, "get_json", fail)
    bundle = json.loads(open_schedules.refresh_open_schedules(2026, tmp_path, enrich_times=True).read_text())
    event = next(e for e in bundle["events"] if e["league"] == "BRASILEIRAO")
    assert event["calendar_date"] == event["end_calendar_date"] == "2026-10-28"
    assert event["start_time_utc"] is event["start_time_local"] is None
    assert event["source"] == "openfootball" and event["source_url"]
    assert not event.get("start_time_source") and not event.get("start_time_source_url")
    assert any(e["start_time_utc"] for e in bundle["events"])  # Primary clocks survive.
    assert not any(receipt.get("clocks_added") for receipt in bundle["input_evidence"])
    assert "ESPN clock lookup failed" in caplog.text


def test_primary_espn_schedule_failure_still_aborts_publication(monkeypatch, tmp_path):
    monkeypatch.setattr(open_schedules, "read_url", fake_open_read)

    def fail(_):
        raise OSError("primary ESPN schedule unavailable")

    monkeypatch.setattr(feeds, "get_json", fail)
    with pytest.raises(OSError, match="primary ESPN schedule"):
        open_schedules.refresh_open_schedules(
            2026,
            tmp_path,
            feeds={"UFC": feeds.FEEDS["UFC"]},
            enrich_times=True,
        )
    assert not (tmp_path / "2026.json").exists()


def test_enriched_combat_keeps_wikipedia_component_membership_and_mixed_licenses(monkeypatch, tmp_path):
    import hashlib
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from kickoff.reviewed_schedules import load_reviewed_schedules

    root = Path(__file__).parents[1]
    events, notices, exclusions = load_reviewed_schedules(root / "data/reviewed", 2026)
    origins = {event.event_id: event.to_dict() for event in events if event.source == "wikipedia"}
    identities = combat_identities()
    rows = []
    for event in events:
        if event.event_id not in identities:
            continue
        identity = identities[event.event_id]
        # Synthetic noon clocks exercise export composition, not source research.
        local = datetime.fromisoformat(event.calendar_date + "T12:00").replace(tzinfo=ZoneInfo(identity["timezone"]))
        row = espn(identity=identity["espn_id"], clock=local.isoformat())
        row["links"] = [{"href": f"https://www.espn.com/mma/fightcenter/_/id/{identity['espn_id']}"}]
        rows.append(row)
    assert len(rows) == 18
    monkeypatch.setattr(open_schedules, "read_url", fake_open_read)
    monkeypatch.setattr(open_schedules, "load_reviewed_schedules", lambda *_: (events, notices, exclusions))
    answer(monkeypatch, rows)
    bundle = json.loads(open_schedules.refresh_open_schedules(2026, tmp_path, enrich_times=True).read_text())
    reference = next(item for item in bundle["components"] if "-wikipedia-" in item["path"])
    body = (tmp_path / reference["path"]).read_bytes()
    assert hashlib.sha256(body).hexdigest() == reference["sha256"]
    component = json.loads(body)
    assert {event["event_id"] for event in component["events"]} == set(origins)
    enriched = [event for event in component["events"] if event.get("start_time_source")]
    assert len(enriched) == 18
    for event in enriched:
        origin = origins[event["event_id"]]
        for field in ("source", "source_url", "title", "calendar_date", "end_calendar_date", "venue"):
            assert event[field] == origin[field]
        assert event["source"] == "wikipedia" and event["start_time_source"] == "espn"
        assert event["start_time_utc"] and event["start_time_source_url"].startswith("https://www.espn.com/")
    assert component["license"] == component["data_licenses"]["wikipedia"] == "CC BY-SA 4.0"
    assert component["data_licenses"]["espn"] == bundle["data_licenses"]["espn"] == feeds.SOURCES["espn"]["license"]
    assert {source["kind"] for source in component["sources"]} == {"wikipedia", "espn"}
    assert "Separately attributed start times retain their time source's terms" in component["license_notice"]
