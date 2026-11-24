"""Structured optional ingestion, real deadlines, immutable source-date caches."""

import gzip
import json
import signal
import zlib
from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from time import monotonic, sleep
from urllib.error import HTTPError

import pytest

from kickoff import result_loader as module
from kickoff import weightlifting_wikipedia as wiki
from kickoff.models import CalendarEvent
from kickoff.reviewed_schedules import load_reviewed_schedules
from tests.test_climbing_results import URL, category, page
from tests.test_f1_results import PATH, RACE, REVISION, classification
from tests.test_f1_results import sources as f1_sources

NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


def event(identity="final", **changes):
    return CalendarEvent(
        **{
            "event_id": identity,
            "source": "world_climbing",
            "sport": "climbing",
            "league": "IFSC_WORLD_CUP",
            "season": "2026",
            "event_type": "session",
            "title": "Fixture Men's Boulder Final",
            "subtitle": None,
            "start_time_utc": None,
            "start_time_local": None,
            "timezone": None,
            "status": "scheduled",
            "venue": None,
            "city": None,
            "region": None,
            "country": None,
            "calendar_date": "2026-10-31",
            "end_calendar_date": "2026-10-31",
            "source_url": URL,
            "round_or_stage": "final",
            "tags": ["Men", "Boulder"],
            **changes,
        }
    )


def enrich(loader, events, directory, **kwargs):
    return loader.enrich(events, 2026, directory, now=NOW, **kwargs)


def test_zero_budget_old_existing_result_and_future_today_sources_are_not_read(tmp_path):
    calls = []
    loader = module.ResultsLoader(lambda url: calls.append(url), budget=0)
    assert enrich(loader, [event()], tmp_path) == []
    loader = module.ResultsLoader(lambda url: calls.append(url))
    current = event(source="weightlifting", sport="weightlifting", league="WEIGHTLIFTING_EUROPE")
    current.result = {"kind": "podium", "rows": [], "complete": True}
    current.result_complete = True
    old = event("old", calendar_date="2026-10-01", end_calendar_date="2026-10-01")
    today, future = (
        event("today", calendar_date="2026-11-04", end_calendar_date="2026-11-04"),
        event("future", end_calendar_date="2027-01-01"),
    )
    assert enrich(loader, [current, old, today, future], tmp_path) == []
    assert calls == []


def test_climbing_url_read_parse_once_dates_do_not_freshen_and_attachment_has_no_alarm(monkeypatch, tmp_path):
    body = page([category(), category(7, "women")])
    calls = []
    parses = []
    attachments = []
    real_parse, real_attach = module.parse_climbing_podiums, module.attach_result

    def parse(*args, **kwargs):
        parses.append(kwargs["source_url"])
        return real_parse(*args, **kwargs)

    def attach(item, result):
        attachments.append(signal.getitimer(signal.ITIMER_REAL)[0])
        real_attach(item, result)

    monkeypatch.setattr(module, "parse_climbing_podiums", parse)
    monkeypatch.setattr(module, "attach_result", attach)
    loader = module.ResultsLoader(lambda url: calls.append(url) or body)
    one = event(source_url=URL.replace("www.", "") + "/")
    two = event("women", tags=["Women", "Boulder"])
    enrich(loader, [one, two], tmp_path)
    checked = one.result["checked_date"]
    third = event("another")
    loader.enrich([third], 2027, tmp_path, now=NOW)
    assert calls == parses == [URL] and attachments == [0, 0, 0]
    assert one.result_complete and two.result_complete and third.result["checked_date"] == checked
    assert one.calendar_date == "2026-10-31"
    assert "infosheet" not in " ".join(calls)


def test_reviewed_climbing_allocation_keeps_partial_result_refreshable(monkeypatch, tmp_path):
    item = event(tags=["Boulder"], title="Reviewed combined final")
    receipt = {
        "event_id": item.event_id,
        "event_title": item.title,
        "event_source_url": URL,
        "calendar_date": item.calendar_date,
        "scope_tags": ["Boulder"],
        "categories": [
            {"category_id": "3", "category": "men", "discipline": "boulder"},
            {"category_id": "7", "category": "women", "discipline": "boulder"},
        ],
        "expected_category_count": 2,
        "allocation_complete": True,
        "allocation_source": {
            "source_url": "https://ifsc.results.info/events/42/infosheet",
            "checked_date": "2026-11-03",
        },
    }
    (tmp_path / "receipts").mkdir()
    (tmp_path / "receipts/climbing-result-blocks.json").write_text(json.dumps({"blocks": [receipt]}))
    calls = []
    loader = module.ResultsLoader(lambda url: calls.append(url) or page([category()]))
    enrich(loader, [item], tmp_path)
    assert item.result is not None and not item.result_complete
    assert calls == [URL] and item.result["allocation_source"] == receipt["allocation_source"]


@pytest.mark.parametrize("mode", ["success", "404", "drip"])
def test_slow_reads_have_true_total_deadline_even_when_socket_stays_active(monkeypatch, tmp_path, mode):
    body = page([category()])
    calls = []

    class Response(BytesIO):
        headers = {}

        def read(self, size=-1):
            if mode == "drip":
                for _ in range(100):
                    sleep(0.003)
            return super().read(size)

    def read(request, timeout):
        calls.append((request.full_url, timeout))
        if mode != "drip":
            sleep(0.07)
        if mode == "404":
            raise HTTPError(request.full_url, 404, "absent", {}, None)
        return Response(body)

    monkeypatch.setattr(module, "urlopen", read)
    loader = module.ResultsLoader(budget=0.015, timeout=5)
    item = event()
    original = deepcopy(item.to_dict())
    start = monotonic()
    assert enrich(loader, [item, event("later")], tmp_path) == []
    assert monotonic() - start < 0.15 and item.to_dict() == original and loader.remaining == 0
    assert len(calls) == 1 and 0 < calls[0][1] <= 0.015
    assert signal.getitimer(signal.ITIMER_REAL)[0] == 0


def test_cpu_parse_timeout_escapes_parser_exception_handler_without_partial_mutation(monkeypatch, tmp_path):
    def parse(*args, **kwargs):
        try:
            while True:
                pass
        except Exception:
            pytest.fail("Deadline must not be swallowed as an ordinary parser failure")

    monkeypatch.setattr(module, "parse_climbing_podiums", parse)
    loader = module.ResultsLoader(lambda _: page([category()]), budget=0.015)
    item = event()
    original = deepcopy(item.to_dict())
    start = monotonic()
    enrich(loader, [item], tmp_path)
    assert monotonic() - start < 0.15 and item.to_dict() == original and loader.remaining == 0


def test_completed_results_survive_later_timeout_and_budget_spans_calls(tmp_path):
    other = URL + "-later"
    calls = []

    def read(url):
        calls.append(url)
        if url == other:
            sleep(0.07)
        return page([category()], url=url)

    loader = module.ResultsLoader(read, budget=0.025)
    one, two = event(), event("later", source_url=other)
    enrich(loader, [one, two], tmp_path)
    assert one.result is not None and two.result is None and loader.remaining == 0
    assert loader.enrich([event("next-year")], 2027, tmp_path, now=NOW) == []
    assert calls == [URL, other]


def test_prior_alarm_handler_and_timer_are_restored(tmp_path):
    previous = signal.getsignal(signal.SIGALRM)
    timer = signal.getitimer(signal.ITIMER_REAL)

    def handler(*_):
        pass

    try:
        signal.signal(signal.SIGALRM, handler)
        signal.setitimer(signal.ITIMER_REAL, 1)
        assert module.ResultsLoader(budget=0.1)._run(lambda: 42) == 42
        assert signal.getsignal(signal.SIGALRM) is handler and 0.5 < signal.getitimer(signal.ITIMER_REAL)[0] <= 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        if timer[0]:
            signal.setitimer(signal.ITIMER_REAL, *timer)


@pytest.mark.parametrize("body", [b"broken", b"%PDF forbidden", gzip.compress(b"a" * 100)])
def test_failures_bad_structures_and_expanded_limits_are_cached(monkeypatch, tmp_path, body):
    monkeypatch.setattr(module, "MAX_BYTES", 50)
    calls = []
    loader = module.ResultsLoader(lambda url: calls.append(url) or body)
    for identity in ["one", "two"]:
        enrich(loader, [event(identity)], tmp_path)
    assert calls == [URL]


def test_no_iwf_or_pdf_transport_is_ever_called():
    calls = []
    loader = module.ResultsLoader(lambda url: calls.append(url))
    for url in ["https://iwf.sport/results/", "https://www.iwf.sport/api", "https://example.org/book.PDF"]:
        assert loader._run(lambda url=url: loader._read(url)) is None
    assert calls == []


def test_f1_uses_pinned_already_read_race_body_and_shared_driver_cache(tmp_path):
    bodies = f1_sources()
    calls = []
    second_path = "src/data/seasons/2027/races/06-miami"
    second_url = f"{module.RAW}/{REVISION}/{second_path}/race-results.yml"
    bodies[second_url] = classification()
    loader = module.ResultsLoader(lambda url: calls.append(url) or bodies.get(url))
    race = event("f1db-1200-race", source="f1db", sport="motorsport", league="F1", event_type="race")
    sprint = event("f1db-1200-sprintRace", source="f1db", sport="motorsport", league="F1", event_type="sprint")
    context = {"race_path": PATH, "race_body": RACE, "revision": REVISION}
    enrich(loader, [race, sprint], tmp_path, f1_contexts={race.event_id: context, sprint.event_id: context})
    later = event(
        "f1db-1201-race",
        source="f1db",
        sport="motorsport",
        league="F1",
        event_type="race",
        calendar_date="2027-05-01",
        end_calendar_date="2027-05-01",
    )
    loader.enrich(
        [later],
        2027,
        tmp_path,
        now=datetime(2027, 5, 4, tzinfo=timezone.utc),
        f1_contexts={
            later.event_id: {
                "race_path": second_path,
                "race_body": b"id: 1201\ndate: 2027-05-03\n",
                "revision": REVISION,
            }
        },
    )
    assert race.result_complete and sprint.result_complete and later.result_complete
    assert len(calls) == 6 and len([u for u in calls if "/drivers/" in u]) == 3
    assert not any(u.endswith("race.yml") for u in calls)
    assert race.result["checked_date"] == loader.checked[f"{module.RAW}/{REVISION}/{PATH}/race-results.yml"]


def test_old_junior_sessions_are_not_looked_up_or_changed():
    events, _, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2026)
    events = [e for e in events if e.league == "IWF_JUNIOR_WORLDS"]
    before = deepcopy([e.to_dict() for e in events])

    def no_requests(_):
        pytest.fail("Old sessions need no result requests")

    assert enrich(module.ResultsLoader(no_requests), events, ROOT / "data/reviewed") == []
    assert [e.to_dict() for e in events] == before


def test_corrupt_junior_snapshot_is_omitted_atomically_without_network(tmp_path):
    (tmp_path / "receipts").mkdir()
    (tmp_path / "receipts/2026-junior-results.json").write_text("{broken")
    item = event("junior", source="weightlifting", sport="weightlifting", league="IWF_JUNIOR_WORLDS")
    (tmp_path / "2026-weightlifting.json").write_text(json.dumps({"events": [{"id": "junior", "categories": []}]}))
    original = deepcopy(item.to_dict())
    calls = []
    assert enrich(module.ResultsLoader(lambda u: calls.append(u)), [item], tmp_path) == []
    assert item.to_dict() == original and calls == []


@pytest.mark.parametrize("complete", [True, False])
def test_wikipedia_only_missing_eligible_classes_are_read_with_actual_revision_and_license(
    monkeypatch, tmp_path, complete
):
    league = "IWF_WORLDS"
    main = wiki.api_url("2026 World Weightlifting Championships")
    class_urls = {
        weight: wiki.api_url(f"2026 World Weightlifting Championships – Men's {weight} kg")
        for weight in ["60", "65", "71"]
    }
    calls = []

    def parse(body, *, input_url, checked_date):
        assert body in {b"main", b"class60"}
        attempts = [{"weight_kg": 100 + i, "status": "made"} for i in range(3)]
        athletes = [
            {
                "name": f"Source Athlete {i}",
                "nation": "GER",
                "gender": "men",
                "weight_class": "60",
                "group": group,
                "snatch": deepcopy(attempts),
                "clean_and_jerk": deepcopy(attempts),
                "total_kg": 204,
                "total_rank": i,
            }
            for i, group in [(1, "A"), (2, "A"), (3, "B")]
        ]
        medals = [
            {
                "name": a["name"],
                "nation": "GER",
                "rank": a["total_rank"],
                "gender": "men",
                "weight_class": "60",
                "weight_kg": 204,
            }
            for a in athletes
        ]
        return [
            {
                "kind": "weightlifting",
                "league": league,
                "year": 2026,
                "gender": "men",
                "weight_class": "60",
                "athletes": athletes if body == b"class60" else [],
                **{key: deepcopy(medals) for key in module.MEDALS},
                "_complete": complete if body == b"class60" else False,
                "source_url": "https://en.wikipedia.org/w/index.php?title=Fixture&oldid=42",
                "input_url": input_url,
                "checked_date": checked_date,
                "revision": "42",
            }
        ]

    def requests(*_, **__):
        return [{"gender": "men", "weight_class": weight, "input_url": url} for weight, url in class_urls.items()]

    monkeypatch.setattr(wiki, "parse_classes", parse)
    monkeypatch.setattr(wiki, "class_requests", requests)
    registry = [
        {
            "id": identity,
            "league": league,
            "start_date": "2026-05-01",
            "categories": [{"gender": "men", "weight_class": weight + " kg", "group": group}],
        }
        for identity, weight, group in [
            ("a", "60", "A"),
            ("b", "60", "B"),
            ("old", "65", "A"),
            ("existing", "71", "A"),
        ]
    ]
    (tmp_path / "2026-weightlifting.json").write_text(json.dumps({"events": registry}))

    def read(url):
        calls.append(url)
        return {main: b"main", class_urls["60"]: b"class60"}[url]

    loader = module.ResultsLoader(read)
    events = [event(row["id"], source="weightlifting", sport="weightlifting", league=league) for row in registry]
    events[2].calendar_date = events[2].end_calendar_date = "2026-10-01"
    events[3].result = {"kind": "weightlifting", "athletes": [], "complete": True}
    sources = enrich(loader, events, tmp_path)
    assert calls == [main, class_urls["60"]]
    assert all(events[i].result_complete is complete for i in [0, 1])
    assert [len(events[i].result["athletes"]) for i in [0, 1]] == [2, 1]
    assert all("lot" not in a for e in events[:2] for a in e.result["athletes"])
    assert all(len(events[i].result[field]) == 3 for i in [0, 1] for field in module.MEDALS)
    assert events[2].result is None and events[3].result is not None
    assert (
        sources[0]["kind"] == "wikipedia" and sources[0]["license"] == "CC BY-SA 4.0" and sources[0]["revision"] == "42"
    )
    assert sources[0]["license_url"] == "https://creativecommons.org/licenses/by-sa/4.0/"
    assert events[0].result["sources"][0]["gender"] == "men"


@pytest.mark.parametrize("error", [OSError("unavailable"), EOFError("truncated gzip"), zlib.error("corrupt gzip")])
def test_raised_source_failures_are_cached_and_never_abort_schedules(tmp_path, error):
    calls = []

    def read(url):
        calls.append(url)
        raise error

    loader = module.ResultsLoader(read)
    one, two = event("one"), event("two")
    assert enrich(loader, [one, two], tmp_path) == []
    assert calls == [URL] and one.result is None and two.result is None


def test_cache_keeps_original_observation_day_across_later_publication_year(monkeypatch, tmp_path):
    class Clock(datetime):
        day = 4

        @classmethod
        def now(cls, zone=None):
            return cls(2026, 11, cls.day, 12, tzinfo=timezone.utc)

    monkeypatch.setattr(module, "datetime", Clock)
    calls = []
    loader = module.ResultsLoader(lambda url: calls.append(url) or page([category()]))
    one = event("one")
    enrich(loader, [one], tmp_path)
    Clock.day = 5
    two = event("two")
    loader.enrich([two], 2027, tmp_path, now=NOW)
    assert calls == [URL]
    assert one.result["checked_date"] == two.result["checked_date"] == "2026-11-04"


def test_default_transport_keeps_normal_caching_headers_and_bounded_gzip(monkeypatch, tmp_path):
    body = page([category()])

    class Response(BytesIO):
        headers = {"Content-Encoding": "gzip"}

    requests = []

    def read(request, timeout):
        requests.append(request)
        return Response(gzip.compress(body))

    monkeypatch.setattr(module, "urlopen", read)
    item = event()
    enrich(module.ResultsLoader(), [item], tmp_path)
    assert requests[0].get_header("Accept-encoding") == "gzip"
    assert requests[0].get_header("User-agent").startswith("kickoff-refresh/")
    assert requests[0].get_header("Cache-control") is None


def test_youth_and_masters_never_trigger_optional_result_requests(tmp_path):
    calls = []
    events = [
        event(league, source="weightlifting", sport="weightlifting", league=league)
        for league in ["IWF_YOUTH_WORLDS", "MASTERS_WORLDS"]
    ]
    assert enrich(module.ResultsLoader(lambda url: calls.append(url)), events, tmp_path) == []
    assert calls == []


def test_stored_partial_result_within_seven_days_is_refetched_and_replaced(tmp_path):
    calls = []
    loader = module.ResultsLoader(lambda url: calls.append(url) or page([category()]))
    item = event()
    item.result = {"kind": "podium", "rows": [], "complete": False}
    item.result_complete = False
    from kickoff.published import PublishedWindow
    from kickoff.web import _event_payload

    stored = _event_payload(item)
    item.result = None
    window = PublishedWindow(NOW, {(2026, item.league): {"events": [stored]}})
    window.restore_results([item])
    assert item.result == stored["result"] and not item.result_complete
    previous = item.to_dict()
    enrich(loader, [item], tmp_path, window=window)
    assert calls == [URL] and item.to_dict() != previous
    assert item.result_complete and len(item.result["rows"]) == 3


def test_explicit_future_start_and_same_venue_day_prevent_lookup_before_session(tmp_path):
    calls = []
    loader = module.ResultsLoader(lambda url: calls.append(url))
    early = datetime(2026, 11, 4, 0, tzinfo=timezone.utc)
    future = event(
        "future",
        calendar_date="2026-11-03",
        end_calendar_date="2026-11-03",
        timezone="America/Los_Angeles",
        start_time_utc="2026-11-04T02:00:00Z",
    )
    date_only = event(
        "date-only", calendar_date="2026-11-03", end_calendar_date="2026-11-03", timezone="America/Los_Angeles"
    )
    assert loader.enrich([future, date_only], 2026, tmp_path, now=early) == []
    assert calls == []


def test_stored_complete_result_needs_no_new_lookup(tmp_path):
    calls = []
    loader = module.ResultsLoader(lambda url: calls.append(url) or page([category()]))
    item = event()
    item.result = {"kind": "podium", "rows": [], "complete": True}
    item.result_complete = True
    previous = item.to_dict()
    enrich(loader, [item], tmp_path)
    assert calls == [] and item.to_dict() == previous


def test_failure_does_not_clear_existing_result(tmp_path):
    item = event()
    item.result = {"kind": "podium", "rows": [], "complete": True}
    item.result_complete = True
    original = deepcopy(item.to_dict())

    def failed(_):
        raise OSError("optional source unavailable")

    assert enrich(module.ResultsLoader(failed), [item], tmp_path) == []
    assert item.to_dict() == original


@pytest.mark.parametrize("complete", [False, True])
@pytest.mark.parametrize("family", ["F1", "climbing", "Wikipedia", "Junior"])
@pytest.mark.parametrize("rebuild", ["force_full", "missing_league"])
def test_rebuild_publishes_older_results_including_partial_ones(monkeypatch, tmp_path, family, complete, rebuild):
    from kickoff.published import PublishedWindow
    from kickoff.web import _event_payload

    fields = {
        "F1": dict(source="f1db", sport="motorsport", league="F1", event_type="race"),
        "climbing": {},
        "Wikipedia": dict(source="weightlifting", sport="weightlifting", league="IWF_WORLDS"),
        "Junior": dict(source="weightlifting", sport="weightlifting", league="IWF_JUNIOR_WORLDS"),
    }[family]
    item = event("past", calendar_date="2026-05-01", end_calendar_date="2026-05-01", **fields)
    result = {
        "kind": "podium",
        "rows": [{"rank": 1, "name": "Past Winner"}],
        "source_url": URL,
        "checked_date": "2026-11-04",
        "revision": REVISION,
        "_complete": complete,
    }
    if item.sport == "weightlifting":
        result.update(kind="weightlifting", athletes=[{"name": "Past Winner", "nation": "GER", "total_kg": 200}])
        del result["rows"]
    calls = []

    def fetch(*_):
        calls.append(item.event_id)
        return result

    method = "_f1" if family == "F1" else "_climbing" if family == "climbing" else "_weightlifting"
    loader = module.ResultsLoader()
    monkeypatch.setattr(loader, method, fetch)
    bundles = {} if rebuild == "force_full" else {(2026, "OTHER_LEAGUE"): {"events": []}}
    window = PublishedWindow(NOW, bundles)
    enrich(loader, [item], tmp_path, window=window, f1_contexts={item.event_id: {}})
    (public,) = window.merge([_event_payload(item)], 2026)
    assert calls == ["past"]
    assert public["result"]["complete"] is complete
    assert (public["result"].get("rows") or public["result"].get("athletes"))[0]["name"] == "Past Winner"


def test_restored_partial_older_than_seven_days_is_kept_without_lookup(tmp_path):
    from kickoff.published import PublishedWindow
    from kickoff.web import _event_payload

    item = event(calendar_date="2026-10-01", end_calendar_date="2026-10-01")
    item.result = {"kind": "podium", "rows": [{"rank": 1, "name": "Stored Winner"}], "complete": False}
    stored = _event_payload(item)
    window = PublishedWindow(NOW, {(2026, item.league): {"events": [stored]}})
    item.result = None
    window.restore_results([item])
    calls = []
    enrich(module.ResultsLoader(lambda url: calls.append(url)), [item], tmp_path, window=window)
    assert calls == []
    assert window.merge([_event_payload(item)], 2026) == [stored]


def test_junior_snapshot_rebuild_restores_all_older_results_without_network():
    from kickoff.published import PublishedWindow

    events, _, _ = load_reviewed_schedules(ROOT / "data/reviewed", 2026)
    events = [e for e in events if e.league == "IWF_JUNIOR_WORLDS"]

    def forbidden(_):
        pytest.fail("The Junior snapshot is local")

    sources = enrich(module.ResultsLoader(forbidden), events, ROOT / "data/reviewed", window=PublishedWindow(NOW))
    assert sources
    assert len(events) == 28 and all(e.result is not None and e.result_complete for e in events)
    assert sum(len(e.result["athletes"]) for e in events) == 261
