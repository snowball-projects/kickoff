"""Optional results use actual fetched provenance without changing schedule identity."""

import hashlib
import json
from copy import deepcopy

import pytest

from kickoff import feeds
from kickoff.results import attach_result
from kickoff.web import _event_payload
from tests.test_espn_results import final, race, status, tennis


class Response:
    headers = {}

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _):
        return self.body


def serve_bytes(monkeypatch, payload):
    body = json.dumps(payload, indent=2).encode()
    calls = []

    def urlopen(request, **_):
        calls.append(request.full_url)
        return Response(body)

    monkeypatch.setattr(feeds, "urlopen", urlopen)
    return body, calls


def scheduled(row, identity="event"):
    return {
        **row,
        "id": identity,
        "date": "2026-05-01T15:00Z",
        "endDate": "2026-05-08T15:00Z",
        "name": "Source competition",
        "season": {"year": 2026},
    }


def test_receipt_hashes_actual_decoded_bytes_not_a_json_reserialization(monkeypatch):
    body, calls = serve_bytes(monkeypatch, {"events": []})
    receipt = {}
    assert feeds.get_json("https://example.test/source", receipt=receipt) == {"events": []}
    assert calls == ["https://example.test/source"]
    assert receipt["sha256"] == hashlib.sha256(body).hexdigest()
    assert receipt["sha256"] != hashlib.sha256(b'{"events":[]}').hexdigest()
    assert receipt["hash_scope"] == "decoded source response bytes"
    assert len(receipt["checked_date"]) == 10


def test_annual_racing_attaches_confirmed_podium_and_public_provenance_once(monkeypatch):
    row = scheduled(race(), "race")
    body, calls = serve_bytes(monkeypatch, {"events": [row]})
    (event,) = feeds.espn_season_feed(
        "racing/nascar-premier", "NASCAR_CUP", "motorsport", "race", "https://www.nascar.com/"
    )(2026)
    result = _event_payload(event)["result"]
    assert len(calls) == 1
    assert event.event_id == "espn-nascar_cup-race"
    assert event.start_time_utc == "2026-05-01T15:00:00Z"
    assert event.title == "Source competition"
    assert event.status == "finished" and event.result_complete
    assert [p["name"] for p in result["rows"]] == ["Winning Driver", "Second Driver", "Third Driver"]
    assert result["sha256"] == hashlib.sha256(body).hexdigest()
    assert result["source_url"] == calls[0]
    assert result["hash_scope"] == "decoded source response bytes"
    assert not any(key.startswith("_") for key in result)


@pytest.mark.parametrize("partial", [False, True])
def test_actual_tennis_final_controls_completion_while_partial_score_remains_refreshable(monkeypatch, partial):
    row = scheduled(tennis())
    row["status"] = status("STATUS_SCHEDULED", completed=False, state="pre")
    if partial:
        final(row)["competitors"][0]["linescores"] = [{"value": "unparseable"}]
    serve_bytes(monkeypatch, {"events": [row]})
    (event,) = feeds.espn_season_feed(
        "tennis/atp", "ATP", "tennis", "tournament", "https://www.atptour.com/", span=True
    )(2026)
    result = _event_payload(event)["result"]
    assert event.status == "finished"
    assert event.result_complete is not partial
    assert event.event_id == "espn-atp-event"
    assert (event.calendar_date, event.end_calendar_date) == ("2026-05-01", "2026-05-08")
    assert result["winner"]["name"] == "Champion"
    assert ("score" not in result) is partial
    assert "_complete" not in result


def test_unconfirmed_result_and_other_leagues_do_not_fabricate_result_facts(monkeypatch):
    row = scheduled(race(), "race")
    row["competitions"][0]["competitors"][2]["order"] = None
    serve_bytes(monkeypatch, {"events": [row]})
    (event,) = feeds.espn_season_feed("racing/irl", "INDYCAR", "motorsport", "race", "https://www.indycar.com/")(2026)
    assert event.result is None and "result" not in _event_payload(event)
    row = scheduled(race(), "race")
    serve_bytes(monkeypatch, {"events": [row]})
    (golf,) = feeds.espn_season_feed(
        "golf/pga", "PGA_TOUR", "golf", "tournament", "https://www.pgatour.com/", span=True
    )(2026)
    assert golf.result is None and "result" not in _event_payload(golf)


def test_attachment_keeps_original_source_object_and_omits_internal_completion_evidence():
    event = feeds.make_event(
        source="f1db",
        league="F1",
        sport="motorsport",
        upstream_id="1",
        season="2026",
        title="Source race",
        utc=None,
        day="2026-05-01",
        status="past schedule",
    )
    before = deepcopy(event.to_dict())
    attach_result(event, None)
    assert event.to_dict() == before
    result = {"kind": "podium", "rows": [], "_complete": True, "_completion_evidence": "official_podium"}
    proof = deepcopy(result)
    attach_result(event, result)
    assert result == proof
    assert event.status == "finished" and event.result_complete
    assert _event_payload(event)["result"] == {"kind": "podium", "rows": [], "complete": True}


def test_weightlifting_replaces_start_list_and_keeps_medals_without_duplicate_attempts():
    from kickoff.models import Participant

    event = feeds.make_event(
        source="weightlifting",
        league="WEIGHTLIFTING_ASIA",
        sport="weightlifting",
        upstream_id="1",
        season="2026",
        title="Source session",
        utc=None,
        day="2026-05-01",
    )
    event.participants = [Participant(name="Old entry", entity_type="athlete")]
    made = {"weight_kg": 100, "status": "made"}
    athlete = {
        "lot": "1",
        "name": "Source bronze",
        "nation": "les",
        "gender": "women",
        "weight_class": "48",
        "group": "B",
        "guest": False,
        "total_rank": 3,
        "total_kg": 200,
        "snatch": [made] * 3,
        "clean_and_jerk": [made] * 3,
    }
    unknown = {**athlete, "lot": "2", "name": "Source refugee", "nation": "WRT", "total_rank": None}
    raw = {
        "kind": "weightlifting",
        "complete": True,
        "athletes": [athlete, unknown],
        "total_medalists": [athlete],
        "source_url": "https://example.test/results.pdf",
        "checked_date": "2026-11-04",
        "sha256": "a" * 64,
        "hash_scope": "raw PDF bytes",
        "source_sessions": [{"local_time": "15:00"}],
        "join_methods": ["Reviewed category"],
    }
    before = deepcopy(raw)
    attach_result(event, raw)
    payload = _event_payload(event)
    result = payload["result"]
    assert raw == before
    assert payload["participants"] == []
    assert result["total_medalists"][0]["lot"] == "1"  # Global bronze can come from group B.
    assert "medalists" not in result and result["complete"] is True
    assert "join_methods" not in result and "source_sessions" not in result
    assert result["athletes"][0]["country_code"] == "LS"
    assert result["athletes"][0]["nation"] == "les"
    assert "country_code" not in result["athletes"][1]
    assert event.result_complete and event.status == "finished"


@pytest.mark.parametrize("finished", [False, True])
def test_team_outcomes_keep_only_source_supplied_finished_facts(finished):
    event = feeds.make_event(
        source="espn",
        sport="soccer",
        league="COPA_SUDAMERICANA",
        upstream_id="leg",
        season="2026",
        title="Source title",
        utc=None,
        day="2026-01-01",
        home="Home",
        away="Away",
        status="finished" if finished else "scheduled",
    )
    competitors = [
        {
            "homeAway": "home",
            "team": {"id": "1"},
            "score": "2",
            "winner": False,
            "advance": False,
            "aggregateScore": "3",
            "shootoutScore": 1,
        },
        {
            "homeAway": "away",
            "team": {"id": "2"},
            "score": "1",
            "winner": True,
            "advance": True,
            "aggregateScore": "3",
            "shootoutScore": 2,
        },
    ]
    feeds._espn_participants(
        event,
        competitors,
        finished,
        "https://site.api.espn.com/apis/site/v2/sports/soccer/conmebol.sudamericana/scoreboard",
    )
    rows = {p["role"]: p for p in _event_payload(event)["participants"]}
    if finished:
        assert rows["away"]["result_winner"] is True
        assert rows["away"]["result_advance"] is True
        assert rows["away"]["aggregate_score"] == 3
        assert rows["away"]["shootout_score"] == 2
        assert rows["home"]["result_winner"] is False
    else:
        assert not {"result_winner", "result_advance", "aggregate_score", "shootout_score"} & rows["away"].keys()


def test_team_outcomes_do_not_infer_missing_or_malformed_source_flags():
    event = feeds.make_event(
        source="espn",
        sport="soccer",
        league="EPL",
        upstream_id="game",
        season="2026",
        title="Source",
        utc=None,
        day="2026-01-01",
        home="Home",
        away="Away",
        status="finished",
    )
    feeds._espn_participants(
        event,
        [
            {"homeAway": "home", "team": {}, "score": "1", "winner": "false", "aggregateScore": "x"},
            {"homeAway": "away", "team": {}, "score": "1"},
        ],
        True,
        "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard",
    )
    assert all("result_winner" not in p and "aggregate_score" not in p for p in _event_payload(event)["participants"])


def test_public_result_coverage_is_explicit_so_partial_facts_remain_refreshable():
    event = feeds.make_event(
        source="f1db",
        sport="motorsport",
        league="F1",
        upstream_id="race",
        season="2026",
        title="Race",
        utc=None,
        day="2026-01-01",
        event_type="race",
    )
    attach_result(event, {"kind": "podium", "rows": [], "_complete": False})
    assert event.result_complete is False
    assert _event_payload(event)["result"]["complete"] is False
    assert "_complete" not in _event_payload(event)["result"]


def test_result_scope_does_not_reuse_changed_category_or_source_page():
    from kickoff.results import same_result_scope

    event = feeds.make_event(
        source="world_climbing",
        sport="climbing",
        league="IFSC_WORLD_CUP",
        upstream_id="block",
        season="2026",
        title="Women's Boulder Final",
        utc=None,
        day="2026-01-01",
        event_type="session",
    )
    event.tags = ["women", "boulder"]
    previous = _event_payload(event)
    assert same_result_scope(event, previous)
    event.tags = ["boulder", "women"]
    assert same_result_scope(event, previous)
    event.tags = ["men", "boulder"]
    assert not same_result_scope(event, previous)
    event.tags = previous["tags"]
    event.source_url = "https://www.worldclimbing.com/another-event"
    assert not same_result_scope(event, previous)


@pytest.mark.parametrize("complete", [True, False])
def test_reviewed_weightlifting_result_survives_loader_skip_or_optional_failure(complete):
    from datetime import datetime, timezone
    from pathlib import Path

    from kickoff.incremental import RefreshPlan
    from kickoff.open_schedules import _reviewed_observations
    from kickoff.refresh_state import Baseline
    from kickoff.result_loader import ResultsLoader
    from kickoff.reviewed_schedules import load_reviewed_schedules
    from kickoff.weightlifting_wikipedia import api_url, classes_for_session, parse_classes
    from tests.test_weightlifting_wikipedia import TITLE, infobox, payload, table

    # Use the real reviewed appointment and its source observation. The small
    # invented result table is the same offline fixture used by the pure parser.
    directory = Path(__file__).resolve().parents[1] / "data/reviewed"
    reviewed, notices, _ = load_reviewed_schedules(directory, 2026)
    fresh = next(e for e in reviewed if e.event_id == "iwf-worlds-2026-men-s-60-kg-group-a")
    assert fresh.status == "past schedule"
    definitions = json.loads((directory / "2026-weightlifting.json").read_text())["events"]
    session = next(row for row in definitions if row["id"] == fresh.event_id)
    body = payload(infobox() + table(first_attempt="70" if complete else ""))
    classes = parse_classes(body, input_url=api_url(TITLE), checked_date="2026-11-03")
    prior = deepcopy(fresh)
    selected = classes_for_session(classes, session, reviewed_sessions=definitions)
    attach_result(prior, ResultsLoader()._combine(selected, session))
    previous = _event_payload(prior)
    assert previous["result"]["complete"] is complete
    baseline = Baseline(
        manifest={"available_seasons": [2026]},
        bundles={"2026-weightlifting-iwf-worlds.json": {"season": 2026, "events": [previous]}},
    )
    moment = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
    plan = RefreshPlan(baseline, moment)
    _reviewed_observations(plan, [fresh], [n for n in notices if n["url"] == fresh.source_url], 2026)
    assert any(unit.unresolved.get(fresh.event_id) == "missing_confirmed_result" for unit in plan.current.values())
    calls = []

    def read(url):
        calls.append(url)
        if complete:
            pytest.fail("An already complete weightlifting result needs no HTTP request")
        raise OSError("Optional Wikipedia result source failed")

    loader = ResultsLoader(read)
    assert loader.enrich([fresh], 2026, directory, baseline_events=baseline.events, now=moment) == ([], [])
    assert len(calls) == (0 if complete else 1)
    incoming = _event_payload(fresh)
    assert incoming["status"] == "past schedule" and "result" not in incoming
    (merged,) = plan.public_events([incoming], 2026)
    assert merged["status"] == "finished"
    assert merged["result"] == previous["result"]
    assert merged["result"]["checked_date"] == "2026-11-03"
    assert plan.confirmed_results == ({fresh.event_id} if complete else set())
    assert incoming["status"] == "past schedule" and "result" not in incoming
    assert baseline.events[fresh.event_id] == previous


def test_confirmed_medal_only_result_replaces_the_finished_sessions_start_list():
    from kickoff.models import Participant

    event = feeds.make_event(
        source="weightlifting",
        sport="weightlifting",
        league="WEIGHTLIFTING_AFRICA",
        upstream_id="session",
        season="2026",
        title="Session",
        utc=None,
        day="2026-01-01",
        event_type="session",
    )
    event.participants = [Participant("Old start-list entry", entity_type="athlete")]
    attach_result(
        event,
        {
            "kind": "weightlifting",
            "athletes": [],
            "total_medalists": [],
            "snatch_medalists": [],
            "clean_and_jerk_medalists": [],
            "_complete": False,
        },
    )
    assert event.status == "finished" and event.participants == []
    assert event.result["complete"] is False
