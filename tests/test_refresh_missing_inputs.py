import json
from datetime import datetime, timezone
from urllib.error import HTTPError

import pytest

from kickoff import open_schedules


@pytest.fixture(autouse=True)
def fixed_refresh_time(monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 4, 12, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(open_schedules, "datetime", FixedDatetime)


def serve_inputs(monkeypatch, year):
    state = {"revision": "a" * 40, "missing": [], "listing": None}

    def read(url):
        if any(fragment in url for fragment in state["missing"]):
            raise HTTPError(url, 404, "Not Found", {}, None)
        if "/commits/" in url:
            return json.dumps({"sha": state["revision"]}).encode()
        if "/contents/" in url:
            listing = state["listing"]
            if listing is None:
                listing = [{"type": "dir", "path": f"src/data/seasons/{year}/races/01"}]
            return json.dumps(listing).encode()
        if url.endswith("race.yml"):
            return f"id: 1234\nround: 1\ndate: {year}-03-01\ntime: 12:00\ngrandPrixId: test\n".encode()
        return json.dumps(
            {"matches": [{"date": f"{year}-10-01", "team1": "Home", "team2": "Away", "round": "Round 1"}]}
        ).encode()

    monkeypatch.setattr(open_schedules, "read_url", read)
    return state


@pytest.mark.parametrize("missing", ["/2026-27/en.1.json", "/2026/br.1.json", "/races/01/race.yml"])
def test_missing_published_input_preserves_snapshot(monkeypatch, tmp_path, missing):
    state = serve_inputs(monkeypatch, 2026)
    output = tmp_path / "published"
    path = open_schedules.refresh_open_schedules(2026, tmp_path / "working", output)
    original = path.read_bytes()
    state.update(revision="b" * 40, missing=[missing])

    with pytest.raises(HTTPError) as error:
        open_schedules.refresh_open_schedules(2026, tmp_path / "working", output)

    assert error.value.code == 404
    assert path.read_bytes() == original


@pytest.mark.parametrize("prior_reference", ["input_evidence", "source_url"])
def test_published_future_football_is_required_across_revisions(monkeypatch, tmp_path, prior_reference):
    state = serve_inputs(monkeypatch, 2027)
    output = tmp_path / "published"
    path = open_schedules.refresh_open_schedules(2027, tmp_path / "working", output)
    bundle = json.loads(path.read_text())
    if prior_reference == "input_evidence":
        # Evidence also protects an input that previously had no dated events in this year.
        bundle["events"] = [event for event in bundle["events"] if event["season"] != "2027-28"]
    else:
        # Older bundles can identify published files through per-event source links.
        bundle.pop("input_evidence")
    path.write_text(json.dumps(bundle))
    original = path.read_bytes()
    state.update(revision="b" * 40, missing=["/2027-28/en.1.json"])

    with pytest.raises(HTTPError):
        open_schedules.refresh_open_schedules(2027, tmp_path / "working", output)

    assert path.read_bytes() == original


@pytest.mark.parametrize(("previous_year", "year"), [(2026, 2027), (2027, 2026)])
@pytest.mark.parametrize("with_evidence", [True, False])
def test_first_refresh_requires_football_published_in_adjacent_year(
    monkeypatch, tmp_path, previous_year, year, with_evidence
):
    serve_inputs(monkeypatch, previous_year)
    output = tmp_path / "published"
    old_path = open_schedules.refresh_open_schedules(previous_year, tmp_path / "working", output)
    if not with_evidence:
        bundle = json.loads(old_path.read_text())
        bundle.pop("input_evidence")
        old_path.write_text(json.dumps(bundle))
    original = old_path.read_bytes()
    state = serve_inputs(monkeypatch, year)
    state.update(revision="b" * 40, missing=["/2026-27/en.1.json"])

    with pytest.raises(HTTPError):
        open_schedules.refresh_open_schedules(year, tmp_path / "working", output)

    assert old_path.read_bytes() == original
    assert not (output / f"{year}.json").exists()


@pytest.mark.parametrize(
    ("year", "missing"), [(2026, "/2026/br.1.json"), (2026, "/races/01/race.yml"), (2027, "/races/01/race.yml")]
)
def test_current_brazil_and_listed_f1_files_are_required_on_first_refresh(monkeypatch, tmp_path, year, missing):
    state = serve_inputs(monkeypatch, year)
    state["missing"] = [missing]
    output = tmp_path / "published"

    with pytest.raises(HTTPError):
        open_schedules.refresh_open_schedules(year, tmp_path / "working", output)

    assert not (output / f"{year}.json").exists()


@pytest.mark.parametrize("missing_listing", [True, False])
@pytest.mark.parametrize("with_evidence", [True, False])
def test_published_future_f1_listing_cannot_disappear(monkeypatch, tmp_path, missing_listing, with_evidence):
    state = serve_inputs(monkeypatch, 2027)
    output = tmp_path / "published"
    path = open_schedules.refresh_open_schedules(2027, tmp_path / "working", output)
    if not with_evidence:
        bundle = json.loads(path.read_text())
        bundle.pop("input_evidence")
        path.write_text(json.dumps(bundle))
    original = path.read_bytes()
    state["revision"] = "b" * 40
    if missing_listing:
        state["missing"] = ["/contents/"]
    else:
        state["listing"] = []

    with pytest.raises(HTTPError if missing_listing else ValueError):
        open_schedules.refresh_open_schedules(2027, tmp_path / "working", output)

    assert path.read_bytes() == original


def test_never_published_future_seasons_can_be_absent(monkeypatch, tmp_path):
    state = serve_inputs(monkeypatch, 2027)
    state["missing"] = ["/2027-28/", "/2027/br.1.json", "/contents/"]
    path = open_schedules.refresh_open_schedules(2027, tmp_path / "working", tmp_path / "published")
    bundle = json.loads(path.read_text())

    assert bundle["events"]
    assert {event["season"] for event in bundle["events"]} == {"2026-27"}
    assert all("/2026-27/" in item["url"] for item in bundle["input_evidence"])
