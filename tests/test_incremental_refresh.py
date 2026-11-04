"""Offline publication exercises the real publisher and hash-bound refresh state."""

import gzip
import importlib.util
import json
import threading
import zlib
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import pytest

from kickoff.published import publish_sports
from kickoff.refresh_state import SourceUnit, build_refresh_state, load_published_baseline

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("incremental_public_refresh", ROOT / "scripts/refresh-public.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def game(identity="game", year=2026, **fields):
    return {
        "event_id": identity,
        "sport": "american-football",
        "league": "NFL",
        "source": "espn",
        "event_type": "game",
        "status": "finished",
        "title": identity,
        "season": str(year),
        "calendar_date": f"{year}-10-01",
        "subtitle": None,
        "start_time_utc": None,
        "start_time_local": None,
        "timezone": None,
        "venue": None,
        "city": None,
        "region": None,
        "country": None,
        "checked_date": "2025-10-01",
        "participants": [
            {"name": "Away", "entity_type": "team", "role": "away", "final_score": 0},
            {"name": "Home", "entity_type": "team", "role": "home", "final_score": 20},
        ],
        **fields,
    }


def unit(key="source", identities=("game",), **fields):
    return SourceUnit(
        **{
            "key": key,
            "source_url": f"https://example.test/{key}",
            "observed_at": (NOW - timedelta(hours=1)).isoformat(),
            "event_ids": identities,
            "complete": True,
            "closed": True,
            **fields,
        }
    )


def bundle(year, events, years=None):
    return {
        "schema_version": "1",
        "season": year,
        "available_seasons": years or [year],
        "events": events,
        "updated_at": NOW.isoformat(),
        "providers": [],
        "coverage": "Offline fixture",
        "sources": [{"kind": "espn", "url": "https://example.test/source"}],
        "input_evidence": [],
        "data_licenses": {"espn": "Factual fixture"},
        "data_license_notice": "Offline factual fixture",
        "exclusions": [],
    }


def baseline_files(tmp_path, events=None, units=None, frozen=(), bounds=None, published_at=None):
    path = tmp_path / "baseline"
    published_at = published_at or NOW - timedelta(minutes=30)
    envelope = bundle(2026, [game()] if events is None else events)
    envelope["updated_at"] = published_at.isoformat()
    publish_sports([envelope], path)
    files = {p.name: p.read_bytes() for p in path.glob("*.json")}
    state = build_refresh_state(
        files,
        [unit()] if units is None else units,
        published_at=published_at,
        frozen_ids=frozen,
        ended_before=(
            {identity: (NOW - timedelta(days=3)).isoformat() for identity in frozen} if bounds is None else bounds
        ),
    )
    files["refresh-state.json"] = json.dumps(state).encode()
    return files


def collector(monkeypatch, rows=None, observe=None):
    calls = []
    loaders = []

    def collect(year, output, reviewed, *, plan, start_list_loader, **kwargs):
        calls.append(year)
        loaders.append(start_list_loader)
        fresh = [game(f"new-{year}", year)] if rows is None else rows
        if observe is None:
            plan.observe(unit(f"new-{year}", tuple(row["event_id"] for row in fresh), observed_at=NOW.isoformat()))
        else:
            observe(plan)
        path = output / f"{year}.json"
        path.write_text(json.dumps(bundle(year, plan.public_events(fresh, year), kwargs["available_seasons"])))
        return path

    monkeypatch.setattr(runner, "refresh_open_schedules", collect)
    return calls, loaders


def clock():
    ticks = iter([NOW, NOW + timedelta(seconds=12)])
    return lambda: next(ticks)


def state(output):
    return json.loads((output / "refresh-state.json").read_text())


def published_events(output):
    manifest = json.loads((output / "manifest.json").read_text())
    return {
        e["event_id"]: e
        for season in manifest["seasons"].values()
        for row in season["sports"]
        for e in json.loads((output / row["file"]).read_text())["events"]
    }


def test_missing_baseline_collects_every_year_before_real_publication_and_shares_loader(monkeypatch, tmp_path):
    calls, loaders = collector(monkeypatch)
    real_publish = runner.publish_sports
    published = []

    def publish(bundles, output):
        assert calls == [2025, 2026, 2027]
        published.append(output)
        return real_publish(bundles, output)

    monkeypatch.setattr(runner, "publish_sports", publish)
    output = tmp_path / "output"
    plan = runner.refresh([2025, 2026, 2027], output, tmp_path, read_bytes={}.__getitem__, clock=clock())
    assert plan.baseline.full_rebuild
    assert calls == [2025, 2026, 2027] and len(published) == 1 and published[0] != output
    assert len({id(loader) for loader in loaders}) == 1
    assert state(output)["published_at"] == (NOW + timedelta(seconds=12)).isoformat()
    assert len(state(output)["units"]) == 3
    assert not load_published_baseline(
        lambda name: (output / name).read_bytes(), now=NOW + timedelta(seconds=13), expected_years=[2025, 2026, 2027]
    ).full_rebuild
    assert "refresh-state.json" not in (output / "index.html").read_text()
    assert "refresh-state.json" not in (output / "manifest.json").read_text()


def test_frozen_facts_checkdates_and_skipped_observation_are_preserved_exactly(monkeypatch, tmp_path):
    original = game()
    files = baseline_files(tmp_path, frozen={"game"})

    def observe(plan):
        assert plan.try_reuse("source") is not None
        plan.observe(unit("fresh", ("new",), observed_at=NOW.isoformat()))

    collector(monkeypatch, [game(participants=[{"name": "Changed"}]), game("new")], observe)
    output = tmp_path / "output"
    output.mkdir()
    sentinel = output / "legacy-extra.json"
    sentinel.write_bytes(b"keep exactly")
    plan = runner.refresh([2026], output, tmp_path, read_bytes=files.__getitem__, clock=clock())
    assert plan.skipped == 1
    assert published_events(output)["game"] == original
    assert next(u for u in state(output)["units"] if u["key"] == "source")["observed_at"] == unit().observed_at
    assert sentinel.read_bytes() == b"keep exactly"
    assert state(output)["frozen_event_ids"] == ["game"]


def test_unobserved_retained_public_score_cannot_newly_freeze_or_clear_old_unresolved_reason(monkeypatch, tmp_path):
    files = baseline_files(tmp_path, units=[unit(unresolved={"game": "result_unconfirmed"})])
    collector(monkeypatch, [game("new", status="scheduled")])
    output = tmp_path / "output"
    runner.refresh([2026], output, tmp_path, read_bytes=files.__getitem__, clock=clock())
    assert "game" in published_events(output)
    assert state(output)["frozen_event_ids"] == []
    assert next(u for u in state(output)["units"] if u["key"] == "source")["unresolved"] == {
        "game": "result_unconfirmed"
    }


def test_only_actual_confirmations_freeze_clear_result_unknown_and_never_invent_outside_frozen(monkeypatch, tmp_path):
    rows = [game("team"), game("unconfirmed"), game("special", event_type="session", sport="climbing", participants=[])]

    def observe(plan):
        plan.observe(
            unit(
                identities=("team", "unconfirmed", "special", "outside"),
                observed_at=NOW.isoformat(),
                unresolved={"special": "result_unconfirmed", "unconfirmed": "result_unconfirmed"},
            )
        )
        plan.confirmed_results.update({"special", "outside"})

    collector(monkeypatch, rows, observe)
    output = tmp_path / "output"
    runner.refresh([2026], output, tmp_path, force_full=True, clock=clock())
    assert state(output)["frozen_event_ids"] == []
    assert set(state(output)["ended_before"]) == {"special", "team", "outside"}
    assert state(output)["units"][0]["unresolved"] == {
        "unconfirmed": "result_unconfirmed",
        "outside": "outside_published_coverage",
    }
    assert "outside" not in published_events(output)


def test_incomplete_observation_does_not_certify_team_score_or_age_only_freeze(monkeypatch, tmp_path):
    rows = [game("scored"), game("no-result", calendar_date="2020-01-01", participants=[])]
    collector(monkeypatch, rows, lambda plan: plan.observe(unit(identities=("scored", "no-result"), complete=False)))
    output = tmp_path / "output"
    runner.refresh([2026], output, tmp_path, force_full=True, clock=clock())
    assert state(output)["frozen_event_ids"] == []


def test_canceled_orphan_membership_survives_omission_without_creating_public_event(monkeypatch, tmp_path):
    prior = unit(identities=("game", "canceled"), unresolved={"canceled": "STATUS_CANCELED"})
    files = baseline_files(tmp_path, units=[prior], frozen={"game"})
    collector(
        monkeypatch, [game("new")], lambda plan: plan.observe(unit(identities=("new",), observed_at=NOW.isoformat()))
    )
    output = tmp_path / "output"
    runner.refresh([2026], output, tmp_path, read_bytes=files.__getitem__, clock=clock())
    saved = state(output)["units"][0]
    assert set(saved["event_ids"]) == {"game", "new", "canceled"}
    assert saved["unresolved"] == {"canceled": "STATUS_CANCELED"}
    assert set(published_events(output)) == {"game", "new"}


@pytest.mark.parametrize("failure", [FileNotFoundError(), EOFError(), zlib.error("broken gzip")])
def test_failed_bulk_baseline_read_falls_back_to_full_without_stopping_core_publish(monkeypatch, tmp_path, failure):
    files = baseline_files(tmp_path)
    calls = []

    def bulk(names):
        calls.append(set(names))
        raise failure

    collector(monkeypatch)
    output = tmp_path / "output"
    plan = runner.refresh([2026], output, tmp_path, read_bytes=files.__getitem__, read_many=bulk, clock=clock())
    assert plan.baseline.full_rebuild and len(calls) == 1
    assert set(published_events(output)) == {"new-2026"}


@pytest.mark.parametrize("cause", ["old-format", "hash"])
def test_old_format_or_changed_baseline_does_not_retain_old_events(monkeypatch, tmp_path, cause):
    files = baseline_files(tmp_path)
    if cause == "old-format":
        old = json.loads(files["refresh-state.json"])
        del old["ended_before"]
        files["refresh-state.json"] = json.dumps(old).encode()
    else:
        name = next(name for name in files if name not in {"manifest.json", "refresh-state.json"})
        files[name] += b" "
    collector(monkeypatch)
    output = tmp_path / "output"
    plan = runner.refresh([2026], output, tmp_path, read_bytes=files.__getitem__, clock=clock())
    assert plan.baseline.full_rebuild
    assert set(published_events(output)) == {"new-2026"}


def test_force_full_bypasses_every_baseline_read_and_keeps_old_fact_dates(monkeypatch, tmp_path):
    def no_baseline(*_):
        raise AssertionError("force-full must not read the baseline")

    monkeypatch.setattr(runner, "PublishedFiles", no_baseline)
    collector(monkeypatch, [game()])
    output = tmp_path / "output"
    plan = runner.refresh(
        [2026], output, tmp_path, force_full=True, read_bytes=no_baseline, read_many=no_baseline, clock=clock()
    )
    assert plan.baseline.reason == "force_full"
    assert published_events(output)["game"]["checked_date"] == "2025-10-01"


def test_failed_collection_or_invalid_state_cannot_touch_existing_output(monkeypatch, tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    (output / "manifest.json").write_bytes(b"existing publication")
    calls, _ = collector(monkeypatch)
    original = runner.refresh_open_schedules

    def broken(year, *args, **kwargs):
        if year == 2027:
            raise OSError("last source failed")
        return original(year, *args, **kwargs)

    monkeypatch.setattr(runner, "refresh_open_schedules", broken)
    with pytest.raises(OSError):
        runner.refresh([2025, 2026, 2027], output, tmp_path, force_full=True, clock=clock())
    assert calls == [2025, 2026]
    assert (output / "manifest.json").read_bytes() == b"existing publication"
    collector(monkeypatch, observe=lambda plan: plan.observe(unit(observed_at=(NOW + timedelta(days=1)).isoformat())))
    with pytest.raises(ValueError):
        runner.refresh([2026], output, tmp_path, force_full=True, clock=clock())
    assert (output / "manifest.json").read_bytes() == b"existing publication"


def test_reader_bulk_is_after_filename_validation_and_checks_complete_file_coverage(tmp_path):
    files = baseline_files(tmp_path)
    reads, bulk_calls = [], []

    def one(name):
        reads.append(name)
        return files[name]

    def bulk(names):
        bulk_calls.append(tuple(names))
        return {name: files[name] for name in names}

    assert not load_published_baseline(one, read_many=bulk, now=NOW, expected_years=[2026]).full_rebuild
    assert reads == ["refresh-state.json"] and len(bulk_calls) == 1
    old = json.loads(files["refresh-state.json"])
    old["files"]["../escape.json"] = "a" * 64
    files["refresh-state.json"] = json.dumps(old).encode()
    bulk_calls.clear()
    assert load_published_baseline(one, read_many=bulk, now=NOW, expected_years=[2026]).reason == "file_name"
    assert not bulk_calls


def test_cdn_reader_preserves_standard_cache_semantics_and_decodes_gzip(monkeypatch):
    requests = []

    def response(request, timeout):
        requests.append((request, timeout))
        body = BytesIO(gzip.compress(b'{"factual":true}'))
        body.headers = {"Content-Encoding": "gzip"}
        return body

    monkeypatch.setattr(runner, "urlopen", response)
    assert runner.PublishedFiles().read_bytes("manifest.json") == b'{"factual":true}'
    request, timeout = requests[0]
    assert request.full_url == runner.PUBLIC_DATA + "manifest.json"
    assert request.get_header("Accept-encoding") == "gzip"
    assert request.get_header("Cache-control") is None and request.get_header("Pragma") is None
    assert 0 < timeout <= runner.BASELINE_SOCKET_SECONDS


def test_cdn_reader_deadline_and_eight_thread_bulk(monkeypatch):
    reader = runner.PublishedFiles()
    reader.deadline = 0
    monkeypatch.setattr(runner, "urlopen", lambda *_a, **_k: pytest.fail("expired read must not start"))
    with pytest.raises(TimeoutError):
        reader.read_bytes("manifest.json")
    reader = runner.PublishedFiles()
    barrier = threading.Barrier(8, timeout=3)

    def read(name):
        barrier.wait()
        return name.encode()

    monkeypatch.setattr(reader, "read_bytes", read)
    names = [f"{i}.json" for i in range(16)]
    assert reader.read_many(names) == {name: name.encode() for name in names}


def test_source_observed_after_run_start_uses_successful_publication_time(monkeypatch, tmp_path):
    observed = NOW + timedelta(seconds=7)
    collector(monkeypatch, [game()], lambda plan: plan.observe(unit(observed_at=observed.isoformat())))
    output = tmp_path / "output"
    runner.refresh([2026], output, tmp_path, force_full=True, clock=clock())
    assert state(output)["units"][0]["observed_at"] == observed.isoformat()
    assert state(output)["published_at"] == (NOW + timedelta(seconds=12)).isoformat()


def test_frozen_discovery_child_graph_keeps_all_original_coverage_and_observation_dates(monkeypatch, tmp_path):
    child = unit("child")
    parent = unit("parent", identities=(), children=("child",))
    files = baseline_files(tmp_path, units=[parent, child], frozen={"game"})

    def observe(plan):
        assert len(plan.try_reuse("parent")) == 1
        plan.observe(unit("fresh", ("new",), observed_at=NOW.isoformat()))

    collector(monkeypatch, [game("new")], observe)
    output = tmp_path / "output"
    plan = runner.refresh([2026], output, tmp_path, read_bytes=files.__getitem__, clock=clock())
    assert plan.skipped == 2
    units = {u["key"]: u for u in state(output)["units"]}
    assert units["parent"]["children"] == ["child"]
    assert units["parent"]["observed_at"] == parent.observed_at
    assert units["child"]["observed_at"] == child.observed_at
    assert state(output)["frozen_event_ids"] == ["game"]


@pytest.mark.parametrize("corrupt", [b"\x1f\x8bnot-a-valid-deflate-stream", gzip.compress(b"incomplete")[:-5]])
def test_actual_corrupt_cdn_gzip_bundle_falls_back_without_breaking_publish(monkeypatch, tmp_path, corrupt):
    files = baseline_files(tmp_path)
    calls = []

    def response(request, timeout):
        name = request.full_url.rsplit("/", 1)[-1]
        calls.append(name)
        wire = corrupt if name not in {"manifest.json", "refresh-state.json"} else gzip.compress(files[name])
        body = BytesIO(wire)
        body.headers = {"Content-Encoding": "gzip"}
        return body

    monkeypatch.setattr(runner, "urlopen", response)
    collector(monkeypatch)
    output = tmp_path / "output"
    plan = runner.refresh([2026], output, tmp_path, clock=clock())
    assert plan.baseline.full_rebuild
    assert {"refresh-state.json", "manifest.json", "2026-american-football-nfl.json"} <= set(calls)
    assert set(published_events(output)) == {"new-2026"}


def test_optional_result_loader_is_shared_across_years_without_default_construction(monkeypatch, tmp_path):
    calls, _ = collector(monkeypatch)
    original = runner.refresh_open_schedules
    loader = object()
    received = []

    def collect_with_results(*args, **kwargs):
        received.append(kwargs["result_loader"])
        return original(*args, **kwargs)

    monkeypatch.setattr(runner, "refresh_open_schedules", collect_with_results)
    runner.refresh(
        [2025, 2026, 2027], tmp_path / "output", tmp_path, force_full=True, clock=clock(), result_loader=loader
    )
    assert calls == [2025, 2026, 2027]
    assert received == [loader, loader, loader]


@pytest.mark.parametrize("hours,freezes", [(47, False), (48, False), (49, True)])
def test_source_confirmed_result_needs_strictly_more_than_two_days_end_evidence(monkeypatch, tmp_path, hours, freezes):
    proof = (NOW - timedelta(hours=hours)).isoformat()
    files = baseline_files(tmp_path, bounds={"game": proof})
    collector(monkeypatch, [game()], lambda plan: plan.observe(unit(observed_at=NOW.isoformat())))
    output = tmp_path / "output"
    runner.refresh([2026], output, tmp_path, read_bytes=files.__getitem__, clock=lambda: NOW)
    assert state(output)["frozen_event_ids"] == (["game"] if freezes else [])
    assert state(output)["ended_before"] == {"game": proof}


def test_first_finished_observation_warms_up_without_guessing_end_from_schedule(monkeypatch, tmp_path):
    collector(
        monkeypatch, [game(calendar_date="2020-01-01")], lambda plan: plan.observe(unit(observed_at=NOW.isoformat()))
    )
    output = tmp_path / "output"
    runner.refresh([2026], output, tmp_path, force_full=True, clock=clock())
    assert state(output)["frozen_event_ids"] == []
    assert state(output)["ended_before"] == {"game": NOW.isoformat()}


def test_explicit_source_end_can_qualify_without_new_observation_warmup(monkeypatch, tmp_path):
    collector(monkeypatch, [game()], lambda plan: plan.observe(unit(observed_at=NOW.isoformat())))
    output = tmp_path / "output"
    ended = NOW - timedelta(days=3)
    runner.refresh([2026], output, tmp_path, force_full=True, clock=clock(), actual_end=lambda _: ended)
    assert state(output)["frozen_event_ids"] == ["game"]
    assert state(output)["ended_before"] == {"game": ended.isoformat()}


def test_aging_retained_unobserved_score_does_not_promote_it_at_baseline_read(monkeypatch, tmp_path):
    proof = (NOW - timedelta(days=3)).isoformat()
    files = baseline_files(tmp_path, bounds={"game": proof})
    collector(monkeypatch, [game("new", status="scheduled")])
    output = tmp_path / "output"
    runner.refresh([2026], output, tmp_path, read_bytes=files.__getitem__, clock=clock())
    assert state(output)["frozen_event_ids"] == []
    assert state(output)["ended_before"]["game"] == proof


def test_old_valid_format_reuses_certified_frozen_source_instead_of_full_refresh(monkeypatch, tmp_path):
    proof = (NOW - timedelta(days=20)).isoformat()
    files = baseline_files(
        tmp_path,
        frozen={"game"},
        bounds={"game": proof},
        units=[unit(observed_at=(NOW - timedelta(days=15)).isoformat())],
        published_at=NOW - timedelta(days=10),
    )

    def observe(plan):
        assert plan.try_reuse("source") is not None
        plan.observe(unit("fresh", ("new",), observed_at=NOW.isoformat(), unresolved={"new": "STATUS_SCHEDULED"}))

    collector(monkeypatch, [game("new", status="scheduled")], observe)
    output = tmp_path / "output"
    plan = runner.refresh([2026], output, tmp_path, read_bytes=files.__getitem__, clock=clock())
    assert not plan.baseline.full_rebuild and plan.skipped == 1
    assert state(output)["frozen_event_ids"] == ["game"]
    assert state(output)["ended_before"]["game"] == proof


def test_explicit_reopen_discards_old_bound_and_refinish_starts_new_correction_period(monkeypatch, tmp_path):
    files = baseline_files(tmp_path, bounds={"game": (NOW - timedelta(days=3)).isoformat()})
    collector(
        monkeypatch,
        [game(status="scheduled")],
        lambda plan: plan.observe(unit(observed_at=NOW.isoformat(), unresolved={"game": "STATUS_SCHEDULED"})),
    )
    output = tmp_path / "output"
    runner.refresh([2026], output, tmp_path, read_bytes=files.__getitem__, clock=clock())
    assert state(output)["ended_before"] == {} and state(output)["frozen_event_ids"] == []
    refreshed = {p.name: p.read_bytes() for p in output.glob("*.json")}
    later = NOW + timedelta(days=4)
    collector(monkeypatch, [game()], lambda plan: plan.observe(unit(observed_at=later.isoformat())))
    runner.refresh([2026], output, tmp_path, read_bytes=refreshed.__getitem__, clock=lambda: later)
    assert state(output)["ended_before"] == {"game": later.isoformat()}
    assert state(output)["frozen_event_ids"] == []


def test_result_parser_gap_retains_prior_end_bound_without_freezing_missing_result(monkeypatch, tmp_path):
    proof = (NOW - timedelta(days=3)).isoformat()
    files = baseline_files(tmp_path, bounds={"game": proof})
    collector(
        monkeypatch,
        [game(participants=[])],
        lambda plan: plan.observe(unit(observed_at=NOW.isoformat(), unresolved={"game": "result_unconfirmed"})),
    )
    output = tmp_path / "output"
    runner.refresh([2026], output, tmp_path, read_bytes=files.__getitem__, clock=clock())
    assert state(output)["ended_before"] == {"game": proof}
    assert state(output)["frozen_event_ids"] == []


def test_changed_actual_session_scope_resets_unfrozen_end_proof(monkeypatch, tmp_path):
    files = baseline_files(tmp_path, bounds={"game": (NOW - timedelta(days=3)).isoformat()})
    collector(
        monkeypatch, [game(calendar_date="2026-10-02")], lambda plan: plan.observe(unit(observed_at=NOW.isoformat()))
    )
    output = tmp_path / "output"
    runner.refresh([2026], output, tmp_path, read_bytes=files.__getitem__, clock=clock())
    assert state(output)["ended_before"] == {"game": NOW.isoformat()}
    assert state(output)["frozen_event_ids"] == []


def test_actual_raw_confirmation_can_freeze_known_outside_member_without_public_event(monkeypatch, tmp_path):
    proof = (NOW - timedelta(days=3)).isoformat()
    old = unit(identities=("game", "raw"), unresolved={"raw": "outside_published_coverage"})
    files = baseline_files(tmp_path, units=[old], bounds={"raw": proof})
    collector(
        monkeypatch,
        [game(status="scheduled")],
        lambda plan: plan.observe(
            unit(identities=("game", "raw"), observed_at=NOW.isoformat(), unresolved={"game": "STATUS_SCHEDULED"})
        ),
    )
    output = tmp_path / "output"
    runner.refresh([2026], output, tmp_path, read_bytes=files.__getitem__, clock=clock())
    assert set(published_events(output)) == {"game"}
    assert state(output)["frozen_event_ids"] == ["raw"]
    assert state(output)["ended_before"]["raw"] == proof
    assert state(output)["units"][0]["unresolved"] == {"game": "STATUS_SCHEDULED"}


def test_frozen_raw_unit_reuses_only_metadata_without_creating_a_calendar_model(monkeypatch, tmp_path):
    proof = (NOW - timedelta(days=3)).isoformat()
    files = baseline_files(
        tmp_path, units=[unit("source"), unit("raw", ("raw-id",))], frozen={"raw-id"}, bounds={"raw-id": proof}
    )

    def observe(plan):
        assert plan.try_reuse("raw") == []
        plan.observe(unit(observed_at=NOW.isoformat(), unresolved={"game": "result_unconfirmed"}))

    collector(monkeypatch, [game(participants=[])], observe)
    output = tmp_path / "output"
    runner.refresh([2026], output, tmp_path, read_bytes=files.__getitem__, clock=clock())
    assert state(output)["frozen_event_ids"] == ["raw-id"]
    assert state(output)["ended_before"]["raw-id"] == proof
    assert "raw-id" not in published_events(output)


def test_disappearing_unfrozen_member_keeps_its_proved_end_metadata_outside_coverage(monkeypatch, tmp_path):
    proof = (NOW - timedelta(days=1)).isoformat()
    files = baseline_files(tmp_path, bounds={"game": proof})
    collector(
        monkeypatch,
        [game("new", status="scheduled")],
        lambda plan: plan.observe(
            unit(identities=("new",), observed_at=NOW.isoformat(), unresolved={"new": "STATUS_SCHEDULED"})
        ),
    )
    output = tmp_path / "output"
    runner.refresh([2026], output, tmp_path, read_bytes=files.__getitem__, clock=clock())
    assert set(published_events(output)) == {"new"}
    assert state(output)["ended_before"]["game"] == proof
    assert state(output)["frozen_event_ids"] == []
    assert "game" in state(output)["units"][0]["unresolved"]


@pytest.mark.parametrize(
    "bound,valid",
    [
        ((NOW - timedelta(days=3)).isoformat(), True),
        ("2026-11-01", False),
        ("2026-11-01T12:00:00", False),
        ("not-a-timestamp", False),
        ((NOW + timedelta(days=1)).isoformat(), False),
    ],
)
def test_specialized_result_end_bounds_must_be_aware_and_nonfuture(monkeypatch, tmp_path, bound, valid):
    def observe(plan):
        plan.observe(
            unit(identities=("special",), observed_at="2025-01-01", unresolved={"special": "result_unconfirmed"})
        )
        plan.confirmed_results.add("special")
        plan.result_end_bounds = {"special": bound}

    collector(monkeypatch, [game("special", event_type="session", sport="climbing", participants=[])], observe)
    output = tmp_path / "output"
    runner.refresh([2026], output, tmp_path, force_full=True, clock=clock())
    expected = bound if valid else (NOW + timedelta(seconds=12)).isoformat()
    assert state(output)["ended_before"] == {"special": expected}
    assert state(output)["frozen_event_ids"] == (["special"] if valid else [])


def test_result_end_bound_alone_cannot_certify_a_missing_or_failed_result(monkeypatch, tmp_path):
    def observe(plan):
        plan.observe(unit(unresolved={"game": "result_unconfirmed"}))
        plan.result_end_bounds = {"game": (NOW - timedelta(days=3)).isoformat()}

    collector(monkeypatch, [game(participants=[])], observe)
    output = tmp_path / "output"
    runner.refresh([2026], output, tmp_path, force_full=True, clock=clock())
    assert state(output)["ended_before"] == {}
    assert state(output)["frozen_event_ids"] == []
