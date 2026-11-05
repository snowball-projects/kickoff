"""Optional results use actual fetched provenance without changing schedule identity."""

import json
from copy import deepcopy

import pytest

from kickoff import feeds
from kickoff.results import allocate_weightlifting_medals, attach_result
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
    assert result["source_url"] == calls[0]
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
    result = {"kind": "podium", "rows": [], "_complete": True}
    original_result = deepcopy(result)
    attach_result(event, result)
    assert result == original_result
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


@pytest.mark.parametrize("last_group", ["A", "B"])
def test_weightlifting_medals_need_a_final_a_session_and_can_include_an_earlier_group_winner(last_group):
    other_group = "B" if last_group == "A" else "A"

    def session(id, group, hour):
        return {
            "id": id,
            "league": "IWF_WORLDS",
            "start_date": "2026-11-01",
            "local_time": hour,
            "event_timezone": "Asia/Shanghai",
            "source_url": "https://example.test/timetable",
            "checked_date": "2026-10-28",
            "categories": [{"gender": "women", "weight_class": "59 kg", "group": group}],
        }

    medal = {
        "name": "Bronze from an earlier group",
        "gender": "women",
        "weight_class": "59",
        "group": other_group,
        "rank": 3,
    }
    result = {
        "kind": "weightlifting",
        "athletes": [{"name": "Own group's athlete"}],
        "total_medalists": [medal],
        "snatch_medalists": [medal],
        "clean_and_jerk_medalists": [medal],
    }
    events = [{"event_id": id, "result": deepcopy(result)} for id in ["earlier", "last"]]
    original = deepcopy(events)
    earlier, last = allocate_weightlifting_medals(
        events, [session("earlier", other_group, "09:00"), session("last", last_group, "16:00")]
    )
    assert earlier["result"]["medal_classes"] == []
    assert last["result"]["medal_classes"] == ([{"gender": "women", "weight_class": "59"}] if last_group == "A" else [])
    assert last["result"]["mixed_classes"] is False
    assert last["result"]["allocation_source"] == {
        "source_url": "https://example.test/timetable",
        "checked_date": "2026-10-28",
    }
    assert events == original  # Input result data is not mutated.
    for item in [earlier, last]:
        assert item["result"]["athletes"] == result["athletes"]
        assert item["result"]["total_medalists"] == [medal]  # Keep global source facts, filter only popup presentation.


def test_weightlifting_mixed_session_decides_only_its_finished_class_and_single_groups_need_no_clock():
    def session(id, categories, hour):
        return {
            "id": id,
            "league": "IWF_WORLDS",
            "start_date": "2026-11-01",
            "local_time": hour,
            "event_timezone": "Asia/Shanghai",
            "source_url": "https://example.test/timetable",
            "checked_date": "2026-10-28",
            "categories": categories,
        }

    def category(weight, group):
        return {"gender": "women", "weight_class": weight, "group": group}

    definitions = [
        session("mixed", [category("53", "A"), category("57", "B")], "09:00"),
        session("57-final", [category("57", "A")], "16:00"),
        session("only", [category("+86", None)], None),
    ]
    events = [
        {"event_id": id, "result": {"kind": "weightlifting", "athletes": []}}
        for id in ["mixed", "57-final", "only", "missing"]
    ]
    mixed, final, only, missing = allocate_weightlifting_medals(events, definitions)
    assert mixed["result"]["medal_classes"] == [{"gender": "women", "weight_class": "53"}]
    assert mixed["result"]["mixed_classes"] is True
    assert final["result"]["medal_classes"] == [{"gender": "women", "weight_class": "57"}]
    assert only["result"]["medal_classes"] == [{"gender": "women", "weight_class": "+86"}]
    assert missing["result"]["medal_classes"] == []


@pytest.mark.parametrize("clock", [None, "16:00"])
def test_weightlifting_uncertain_or_simultaneous_sessions_do_not_guess_a_medal_decider(clock):
    definitions = [
        {
            "id": id,
            "league": "IWF_WORLDS",
            "start_date": "2026-11-01",
            "local_time": hour,
            "event_timezone": "Asia/Shanghai",
            "source_url": "https://example.test/timetable",
            "checked_date": "2026-10-28",
            "categories": [{"gender": "men", "weight_class": "60", "group": group}],
        }
        for id, hour, group in [("first", clock, "B"), ("last", "16:00", "A")]
    ]
    events = [{"event_id": row["id"], "result": {"kind": "weightlifting"}} for row in definitions]
    assert all(row["result"]["medal_classes"] == [] for row in allocate_weightlifting_medals(events, definitions))
