import copy
import hashlib
import importlib.util
import json
import subprocess
from dataclasses import replace
from urllib.error import HTTPError

import pytest

from kickoff import feeds, open_schedules
from tests.test_reviewed_schedules import ROOT, fake_open_read

spec = importlib.util.spec_from_file_location("refresh_public", ROOT / "scripts/refresh-public.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def game(league="NBA", identity="old"):
    return feeds.make_event(
        source="espn",
        league=league,
        sport="basketball",
        upstream_id=identity,
        season="2026",
        title=f"{league} {identity}",
        day="2026-11-01",
        utc=None,
        source_url=f"https://www.espn.com/{league.lower()}/{identity}",
    )


@pytest.fixture
def previous(monkeypatch, tmp_path):
    monkeypatch.setattr(open_schedules, "read_url", fake_open_read)
    path = open_schedules.refresh_open_schedules(
        2026,
        tmp_path / "old",
        feeds={league: ("espn", lambda _, league=league: [game(league)]) for league in ("NBA", "NFL")},
    )
    bundle = json.loads(path.read_text())
    bundle["updated_at"] = "2026-09-01T12:00:00Z"
    for receipt in bundle["feed_status"]:
        receipt["checked_at"] = bundle["updated_at"]
    return bundle


def broken(_):
    raise OSError("source offline")


@pytest.mark.parametrize("failed", [[], ["NBA"], ["NBA", "NFL"], ["EPL"], ["F1"], ["EPL", "F1", "NBA"]])
def test_success_and_independent_single_or_multiple_fallback(monkeypatch, tmp_path, previous, failed):
    def read(url):
        if ("EPL" in failed and url.endswith("en.1.json")) or ("F1" in failed and "f1db/f1db" in url):
            raise OSError("source offline")
        return fake_open_read(url).replace(b"a" * 40, b"b" * 40)

    monkeypatch.setattr(open_schedules, "read_url", read)
    warnings = []
    path = open_schedules.refresh_open_schedules(
        2026,
        tmp_path / "new",
        previous=previous,
        warnings=warnings,
        feeds={
            league: ("espn", broken if league in failed else lambda _, league=league: [game(league, "fresh")])
            for league in ("NBA", "NFL")
        },
    )
    actual = json.loads(path.read_text())
    assert len(warnings) == len(failed)
    receipts = {r["league"]: r for r in actual["feed_status"]}
    for league in receipts:
        selected = [e for e in actual["events"] if e["league"] == league]
        old = [e for e in previous["events"] if e["league"] == league]
        if league in failed:
            assert selected == old
            assert receipts[league]["status"] == "fallback"
            assert receipts[league]["checked_at"] == previous["updated_at"]
            assert any(league in warning for warning in warnings)
        else:
            assert receipts[league]["status"] == "fresh"
            assert receipts[league]["checked_at"] != previous["updated_at"]
            if league in {"NBA", "NFL"}:
                assert selected[0]["event_id"].endswith("fresh")
    if "EPL" in failed:
        old_epl = next(e for e in previous["events"] if e["league"] == "EPL")
        assert any(s.get("revision") == "a" * 40 for s in actual["sources"])
        assert any(s.get("revision") == "b" * 40 for s in actual["sources"])
        old_input = (
            old_epl["source_url"]
            .replace("https://github.com/", "https://raw.githubusercontent.com/")
            .replace("/blob/", "/")
        )
        assert next(i for i in previous["input_evidence"] if i["url"] == old_input) in actual["input_evidence"]
        assert any("/" + "b" * 40 + "/" in e["source_url"] for e in actual["events"] if e["league"] == "BUNDESLIGA")


@pytest.mark.parametrize("bad", [None, {}, {"events": []}])
def test_missing_fallback_is_precise_and_never_overwrites_output(monkeypatch, tmp_path, bad):
    monkeypatch.setattr(open_schedules, "read_url", fake_open_read)
    output = tmp_path / "data"
    output.mkdir()
    target = output / "2026.json"
    target.write_text("existing live export")
    warnings = []
    with pytest.raises(ValueError, match="Cannot publish without fallback.*NBA"):
        open_schedules.refresh_open_schedules(
            2026,
            output,
            feeds={"NBA": ("espn", broken)},
            previous=bad,
            previous_error="HTTP 403 from live 2026.json",
            warnings=warnings,
        )
    assert target.read_text() == "existing live export"
    assert "NBA 2026" in warnings[0] and "fallback unavailable" in warnings[0]
    if bad is None:
        assert "HTTP 403" in warnings[0]


def test_invalid_fresh_events_recover_without_touching_another_feed(monkeypatch, tmp_path, previous):
    warning = []
    bad = replace(game(), calendar_date="2026-02-30")
    result = open_schedules.refresh_open_schedules(
        2026,
        tmp_path / "data",
        previous=previous,
        warnings=warning,
        feeds={"NBA": ("espn", lambda _: [bad]), "NFL": ("espn", lambda _: [game("NFL", "fresh")])},
    )
    bundle = json.loads(result.read_text())
    assert any("invalid calendar date" in line for line in warning)
    assert next(e for e in bundle["events"] if e["league"] == "NBA")["event_id"].endswith("old")
    assert next(e for e in bundle["events"] if e["league"] == "NFL")["event_id"].endswith("fresh")


def test_invalid_fallback_cannot_be_claimed_as_recovered(monkeypatch, tmp_path, previous):
    invalid = copy.deepcopy(previous)
    next(e for e in invalid["events"] if e["league"] == "NBA")["calendar_date"] = "2026-02-30"
    warning = []
    with pytest.raises(ValueError, match="fallback.*NBA"):
        open_schedules.refresh_open_schedules(
            2026, tmp_path, previous=invalid, warnings=warning, feeds={"NBA": ("espn", broken)}
        )
    assert "fallback unavailable" in warning[0]


@pytest.mark.parametrize(
    "fetch", [feeds.nfl_events, feeds.nhl_events, feeds.mlb_events, feeds.ucl_events, feeds.FEEDS["PGA_TOUR"][1]]
)
def test_malformed_payload_never_becomes_successful_empty_feed(monkeypatch, fetch):
    monkeypatch.setattr(feeds, "get_json", lambda *_, **__: {})
    with pytest.raises((ValueError, KeyError)):
        fetch(2026)


def test_empty_previous_feed_requires_receipt_and_keeps_check_date(monkeypatch, tmp_path, previous):
    previous["events"] = [e for e in previous["events"] if e["league"] != "NBA"]
    warning = []
    path = open_schedules.refresh_open_schedules(
        2026, tmp_path, previous=previous, warnings=warning, feeds={"NBA": ("espn", broken)}
    )
    receipt = next(r for r in json.loads(path.read_text())["feed_status"] if r["league"] == "NBA")
    assert receipt["status"] == "fallback" and receipt["checked_at"] == previous["updated_at"]
    assert "reused 0 live events" in warning[0]


def test_runner_reads_index_preserves_other_year_and_component(monkeypatch, tmp_path, previous):
    archive = {**previous, "season": 2025, "available_seasons": [2025, 2026]}
    component = b'{"license":"CC BY-SA 4.0","events":[]}'
    archive["components"] = [
        {
            "path": "2025-wikipedia-" + hashlib.sha256(component).hexdigest() + ".json",
            "sha256": hashlib.sha256(component).hexdigest(),
        }
    ]
    paths = []

    def read(url):
        paths.append(url)
        if url.endswith("2026.json"):
            return json.dumps(previous).encode()
        if url.endswith("2025.json"):
            return json.dumps(archive).encode()
        assert url.endswith(archive["components"][0]["path"])
        return component

    monkeypatch.setattr(runner, "read_url", read)
    monkeypatch.setattr(runner, "read_optional", lambda _: b'{"schema_version":"1","available_seasons":[2025,2026]}')
    monkeypatch.setattr(runner, "FEEDS", {"NBA": ("espn", broken), "NFL": ("espn", lambda _: [game("NFL", "fresh")])})
    warning = []
    runner.refresh([2026], tmp_path, tmp_path / "reviewed", warning)
    assert json.loads((tmp_path / "2025.json").read_text()) == archive
    assert (tmp_path / archive["components"][0]["path"]).read_bytes() == component
    assert json.loads((tmp_path / "index.json").read_text())["available_seasons"] == [2025, 2026]
    assert len(warning) == 1 and "NBA" in warning[0]
    assert any(path.endswith("2025.json") for path in paths)


def test_runner_supports_live_bundle_contract_when_index_is_404(monkeypatch, tmp_path, previous):
    def missing(_):
        return None

    monkeypatch.setattr(runner, "read_optional", missing)
    monkeypatch.setattr(runner, "read_url", lambda _: json.dumps(previous).encode())
    monkeypatch.setattr(runner, "FEEDS", {"NBA": ("espn", broken)})
    warnings = []
    runner.refresh([2026], tmp_path, tmp_path / "reviewed", warnings)
    assert len(warnings) == 1
    assert json.loads((tmp_path / "2026.json").read_text())["feed_status"][-1]["status"] == "fallback"


def test_all_failed_feeds_are_reported_even_when_live_data_is_unavailable(monkeypatch, tmp_path):
    def unavailable(_):
        raise HTTPError("https://example.test/data", 503, "offline", {}, None)

    monkeypatch.setattr(runner, "read_url", unavailable)
    monkeypatch.setattr(runner, "read_optional", unavailable)
    monkeypatch.setattr(open_schedules, "read_url", fake_open_read)
    monkeypatch.setattr(runner, "FEEDS", {league: ("espn", broken) for league in ["NBA", "NFL"]})
    target = tmp_path / "2026.json"
    target.write_text("last live data")
    warnings = []
    with pytest.raises(ValueError, match="fallback unavailable"):
        runner.refresh([2026], tmp_path, tmp_path / "reviewed", warnings)
    assert target.read_text() == "last live data"
    assert len(warnings) == 2 and "NBA" in warnings[0] and "NFL" in warnings[1]


def test_workflow_deploys_before_failing_and_summarizes_every_feed(tmp_path):
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    assert text.index("Check Python") < text.index("Fetch every schedule") < text.index("Build site")
    assert text.index("Build site") < text.index("Deploy Pages") < text.index("Report feed failures after deployment")
    assert 'cron: "17 9 * * *"' in text and "branches: [main]" in text and "workflow_dispatch:" in text
    assert "contents: write" not in text and "issues: write" not in text and "GH_TOKEN" not in text
    report = text.split("Report feed failures after deployment", 1)[1].split("run: |\n", 1)[1]
    script = "\n".join(line[10:] for line in report.splitlines())
    warning_file = tmp_path / "feed-failures.md"
    summary = tmp_path / "summary.md"
    warning_file.write_text("- NBA 2026: reused previous events\n- F1 2026: reused previous events\n")
    result = subprocess.run(
        ["bash", "-e", "-c", script], env={"RUNNER_TEMP": str(tmp_path), "GITHUB_STEP_SUMMARY": str(summary)}
    )
    assert result.returncode == 1
    assert "NBA 2026" in summary.read_text() and "F1 2026" in summary.read_text()
    warning_file.write_text("")
    assert (
        subprocess.run(
            ["bash", "-e", "-c", script], env={"RUNNER_TEMP": str(tmp_path), "GITHUB_STEP_SUMMARY": str(summary)}
        ).returncode
        == 0
    )


def test_empty_response_cannot_erase_a_previously_published_feed(tmp_path, previous):
    warnings = []
    path = open_schedules.refresh_open_schedules(
        2026, tmp_path, previous=previous, warnings=warnings, feeds={"NBA": ("espn", lambda _: [])}
    )
    bundle = json.loads(path.read_text())
    assert next(e for e in bundle["events"] if e["league"] == "NBA")["event_id"].endswith("old")
    assert "Feed returned no events" in warnings[0]


def test_known_split_season_404_recovers_just_that_league(monkeypatch, tmp_path, previous):
    def read(url):
        if url.endswith("2026-27/en.1.json"):
            raise HTTPError(url, 404, "missing previously published file", {}, None)
        return fake_open_read(url)

    monkeypatch.setattr(open_schedules, "read_url", read)
    warnings = []
    path = open_schedules.refresh_open_schedules(
        2026,
        tmp_path,
        previous=previous,
        warnings=warnings,
        published_inputs={"https://example.test/revision/2026-27/en.1.json"},
    )
    actual = json.loads(path.read_text())
    assert next(e for e in actual["events"] if e["league"] == "EPL") in previous["events"]
    assert len(warnings) == 1 and "EPL" in warnings[0]
