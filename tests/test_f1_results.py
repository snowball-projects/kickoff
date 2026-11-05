import json
import zlib

import pytest

from kickoff.f1_results import BLOB, RAW, load_f1_result

REVISION = "a" * 40
PATH = "src/data/seasons/2026/races/06-miami"
RACE = b"id: 1200\ndate: 2026-05-03\nsprintRaceDate: 2026-05-02\nqualifyingDate: 2026-05-02\n"
RESULT_URL = f"{RAW}/{REVISION}/{PATH}/race-results.yml"
SPRINT_URL = f"{RAW}/{REVISION}/{PATH}/sprint-race-results.yml"
DRIVERS = {"driver-a": "Driver A", "driver-b": "Zoë B", "driver-c": "Driver C"}


def classification(rows=((3, "driver-c"), (1, "driver-a"), (2, "driver-b"))):
    return "".join(
        f"- position: {rank}\n  driverId: {driver}\n  gridPosition: {4 - index}\n"
        for index, (rank, driver) in enumerate(rows)
    ).encode()


def sources(body=None):
    return {
        RESULT_URL: classification() if body is None else body,
        SPRINT_URL: classification(((1, "driver-b"), (2, "driver-c"), (3, "driver-a"))),
        **{
            f"{RAW}/{REVISION}/src/data/drivers/{driver}.yml": (
                f"id: {driver}\nname: {name}\ndateOfBirth: 1990-01-01\n"
            ).encode()
            for driver, name in DRIVERS.items()
        },
    }


def load(read, **kwargs):
    return load_f1_result(
        **{
            "event_id": "f1db-1200-race",
            "event_type": "race",
            "race_path": PATH,
            "race_body": RACE,
            "revision": REVISION,
            "checked_date": "2026-11-04",
            "read_bytes": read,
            **kwargs,
        }
    )


def test_explicit_finishing_rank_wins_over_input_and_grid_order_with_exact_names_and_sources():
    data = sources()
    result = load(data.get)
    assert result["rows"] == [
        {"rank": 1, "name": "Driver A", "participant_id": "driver-a"},
        {"rank": 2, "name": "Zoë B", "participant_id": "driver-b"},
        {"rank": 3, "name": "Driver C", "participant_id": "driver-c"},
    ]
    assert result["kind"] == "podium"
    assert result["source_url"] == f"{BLOB}/{REVISION}/{PATH}/race-results.yml"
    assert result["checked_date"] == "2026-11-04"
    assert result["revision"] == REVISION
    assert "dateOfBirth" not in json.dumps(result)
    assert "1990-01-01" not in json.dumps(result)


def test_sprint_is_separate_and_never_uses_race_or_qualifying_results():
    data, reads = sources(), []

    def read(url):
        reads.append(url)
        return data.get(url)

    result = load(read, event_id="f1db-1200-sprintRace", event_type="sprint")
    assert [row["participant_id"] for row in result["rows"]] == ["driver-b", "driver-c", "driver-a"]
    assert reads[0] == SPRINT_URL
    assert RESULT_URL not in reads
    assert all("qualifying" not in url for url in reads)
    data.pop(SPRINT_URL)
    reads.clear()
    assert load(read, event_id="f1db-1200-sprintRace", event_type="sprint") is None
    assert reads == [SPRINT_URL]


@pytest.mark.parametrize("event_type", ["qualifying", "practice", "sprintQualifying", "scheduled"])
def test_other_sessions_do_not_request_results(event_type):
    def read(url):
        pytest.fail(f"Unexpected result read: {url}")

    assert load(read, event_type=event_type) is None


@pytest.mark.parametrize(
    "change",
    [
        {"event_id": "f1db-1201-race"},
        {"event_id": "f1db-1200-sprintRace"},
        {"race_path": "src/data/seasons/2025/races/06-miami"},
        {"race_path": "src/data/seasons/2026/races/../06-miami"},
        {"revision": "main"},
        {"checked_date": "yesterday"},
        {"race_body": b"id: 1200\ndate: 2026-05-03\n", "event_type": "sprint", "event_id": "f1db-1200-sprintRace"},
        {"race_body": RACE + b"id: 1201\n"},
    ],
)
def test_exact_event_year_and_session_join_is_required_before_fetch(change):
    def read(url):
        pytest.fail(f"Unexpected result read: {url}")

    assert load(read, **change) is None


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"[]\n",
        classification(((1, "driver-a"), (2, "driver-b"))),
        classification(((1, "driver-a"), (2, "driver-b"), (2, "driver-c"), (3, "driver-c"))),
        classification(((1, "driver-a"), (2, "driver-a"), (3, "driver-c"))),
        classification(((1, "../driver-a"), (2, "driver-b"), (3, "driver-c"))),
        classification((("DQ", "driver-a"), (2, "driver-b"), (3, "driver-c"))),
        b"- driverId: driver-a\n  gridPosition: 1\n",
        classification() + b"  driverId: driver-b\n",
        b"\xff",
    ],
)
def test_absent_malformed_or_ambiguous_classification_is_not_a_result(body):
    assert load(sources(body).get) is None


def test_no_position_from_list_grid_or_calendar_date_and_no_qualifying_fallback():
    data = sources(b"- position:\n  driverId: driver-a\n  gridPosition: 1\n")
    data[RESULT_URL.replace("race-results", "qualifying-results")] = classification()
    assert load(data.get) is None
    data.pop(RESULT_URL)
    assert load(data.get) is None


@pytest.mark.parametrize("name", ['"Zoë B"', "'Zoë B'", "Zoë B"])
def test_source_name_scalars_are_preserved(name):
    data = sources()
    data[f"{RAW}/{REVISION}/src/data/drivers/driver-b.yml"] = f"id: driver-b\nname: {name}\n".encode()
    assert load(data.get)["rows"][1]["name"] == "Zoë B"


@pytest.mark.parametrize("body", [None, b"id: other\nname: Driver B\n", b"id: driver-b\n", b'id: driver-b\nname: ""\n'])
def test_missing_or_mismatched_driver_is_not_guessed_from_id(body):
    data = sources()
    data[f"{RAW}/{REVISION}/src/data/drivers/driver-b.yml"] = body
    assert load(data.get) is None


@pytest.mark.parametrize("error", [OSError("offline"), TimeoutError("slow"), EOFError("gzip"), zlib.error("corrupt")])
@pytest.mark.parametrize("at_driver", [False, True])
def test_optional_read_failures_never_abort_primary_schedule(error, at_driver):
    data = sources()

    def read(url):
        if ("/drivers/" in url) == at_driver:
            raise error
        return data.get(url)

    assert load(read) is None


def test_shared_revision_keyed_driver_cache_reuses_names_and_caches_failed_reads():
    data, cache, reads = sources(), {}, []

    def read(url):
        reads.append(url)
        return data.get(url)

    assert load(read, driver_cache=cache)
    assert load(read, driver_cache=cache, event_id="f1db-1200-sprintRace", event_type="sprint")
    assert sum("/drivers/" in url for url in reads) == 3
    assert reads.count(RESULT_URL) == reads.count(SPRINT_URL) == 1
    other_revision = "b" * 40
    assert load(read, driver_cache=cache, revision=other_revision) is None
    assert reads[-1].startswith(f"{RAW}/{other_revision}/")
    cache.clear()
    reads.clear()
    data[f"{RAW}/{REVISION}/src/data/drivers/driver-a.yml"] = None
    assert load(read, driver_cache=cache) is None
    assert load(read, driver_cache=cache) is None
    assert sum("/drivers/" in url for url in reads) == 1


def test_failed_driver_exception_is_cached_for_the_run():
    cache, reads = {}, []

    def read(url):
        reads.append(url)
        if "/drivers/" in url:
            raise OSError("offline")
        return classification()

    assert load(read, driver_cache=cache) is None
    assert load(read, driver_cache=cache) is None
    assert sum("/drivers/" in url for url in reads) == 1


def test_unrelated_nested_driver_biography_is_ignored_and_not_exported():
    data = sources()
    url = f"{RAW}/{REVISION}/src/data/drivers/driver-a.yml"
    data[url] += b"familyRelationships:\n  - driverId: private-relative\n    type: PARENT\n"
    result = load(data.get)
    assert result["rows"][0]["name"] == "Driver A"
    assert "private-relative" not in json.dumps(result)
    data[url] += b"name: Different Name\n"
    assert load(data.get) is None
