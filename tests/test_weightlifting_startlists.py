"""Offline, synthetic layout fixtures; no copied PDF pages or athlete birth dates."""

from copy import deepcopy
from types import SimpleNamespace
from zlib import error as ZlibError

import pytest
from pypdf.errors import PdfReadError

from kickoff import weightlifting_startlists as startlists
from kickoff.feeds import make_event

EASY = """1 Women SE 48A 2 19/04 09:00
START LIST WOMEN SE 48A
101 Example Strong 01.01.2000 GER 48 SE 180
102 Example Neutral 01.01.2000 AIN 48 SE 160
"""
OWL = """1 - GROUP A 79 KG M 4:00 PM 6:00 PM M 1
Session GROUP A 79 KG M Weigh-in Time: 2026-05-14 16:00 Start Time: 2026-05-14 18:00
GROUP A MEN 79 KG
1 101 Example One GER 1/1/2000 SR M 79 300
2 102 Example Guest [guest] AUS 1/1/2000 SR M 79 290
"""


def pages(monkeypatch, texts):
    monkeypatch.setattr(
        startlists,
        "_reader_from_bytes",
        lambda _: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda text=text: text) for text in texts]),
    )


def test_easywl_reads_only_roster_rows_and_confirms_complete_timetable(monkeypatch):
    pages(monkeypatch, [EASY + "President: Some Official GER\n"])
    (session,) = startlists.parse_start_book(b"fixture", "easywl")
    assert session.categories == frozenset({("women", "48", "A")})
    assert [(row.name, row.total, row.nation) for row in session.entries] == [
        ("Example Strong", 180, "GER"),
        ("Example Neutral", 160, "AIN"),
    ]
    assert session.expected == 2 and session.issue is None
    assert not hasattr(session.entries[0], "dob")
    pages(monkeypatch, [EASY.replace("48A 2", "48A 3")])
    with pytest.raises(ValueError, match="count"):
        startlists.parse_start_book(b"fixture", "easywl")


@pytest.mark.parametrize("expected", [1, 2])
def test_owlcms_keeps_guest_rows_whether_timetable_includes_or_excludes_guests(monkeypatch, expected):
    pages(monkeypatch, [OWL.replace("6:00 PM M 1", f"6:00 PM M {expected}")])
    (session,) = startlists.parse_start_book(b"fixture", "owlcms")
    assert len(session.entries) == 2 and session.expected == expected
    assert session.entries[1].guest and session.entries[1].name == "Example Guest"
    assert session.issue is None
    pages(monkeypatch, [OWL.replace("2 102", "3 102")])
    with pytest.raises(ValueError, match="sequence"):
        startlists.parse_start_book(b"fixture", "owlcms")


@pytest.mark.parametrize(
    "text",
    [
        OWL.replace("6:00 PM M 1", "6:00 PM M 2").replace("2 102 Example Guest [guest] AUS 1/1/2000 SR M 79 290\n", ""),
        OWL.replace(" [guest]", ""),
    ],
    ids=["truncated-final-row", "unexplained-non-guest-extra-row"],
)
def test_owlcms_rejects_incomplete_and_unexplained_roster_counts(monkeypatch, text):
    pages(monkeypatch, [text])
    with pytest.raises(ValueError, match="count"):
        startlists.parse_start_book(b"fixture", "owlcms")


def test_contradictory_source_class_is_retained_for_audit_and_marks_whole_cohort(monkeypatch):
    pages(monkeypatch, [OWL.replace("SR M 79 300", "SR M 71 300")])
    (session,) = startlists.parse_start_book(b"fixture", "owlcms")
    assert session.entries[0].weight == "71"
    assert "lot 101, class 71" in session.issue


def test_duplicate_or_missing_sessions_and_incomplete_rows_do_not_publish_a_partial_book(monkeypatch):
    pages(monkeypatch, [EASY, EASY])
    with pytest.raises(ValueError):
        startlists.parse_start_book(b"fixture", "easywl")
    pages(monkeypatch, [OWL.replace("1/1/2000 SR M 79 290", "not-a-date SR M 79 290")])
    with pytest.raises(ValueError, match="sequence"):
        startlists.parse_start_book(b"fixture", "owlcms")
    pages(monkeypatch, ["Results are not a start list"])
    with pytest.raises(ValueError):
        startlists.parse_start_book(b"fixture", "easywl")


def event(identity, league="WEIGHTLIFTING_EUROPE"):
    result = make_event(
        source="weightlifting",
        league=league,
        sport="weightlifting",
        upstream_id=identity,
        season="2026",
        title="Reviewed source session",
        utc=None,
        day="2026-04-19",
        event_type="session",
    )
    result.event_id = identity
    return result


def setup_catalog(monkeypatch, tmp_path):
    config = {
        "books": [
            {
                "league": "WEIGHTLIFTING_EUROPE",
                "year": 2026,
                "format": "easywl",
                "name": "Official example start list",
                "publisher": "EWF",
                "landing_url": "https://ewf.sport/meet",
                "link_pattern": r"/startbook-v\d+\.pdf",
            }
        ],
        "country_codes": {"GER": {"code": "DE", "source_url": "https://iwf.sport/codes", "checked_date": "2026-11-03"}},
    }
    monkeypatch.setattr(startlists, "catalog", lambda: config)
    import json

    (tmp_path / "2026-weightlifting.json").write_text(
        json.dumps(
            {"events": [{"id": "session", "categories": [{"gender": "women", "weight_class": "48", "group": "A"}]}]}
        )
    )
    pages(monkeypatch, [EASY])
    calls = []

    def read(url):
        calls.append(url)
        return b'<a href="/startbook-v1.pdf">Start book</a>' if url.endswith("/meet") else b"PDF1"

    return config, calls, read


def test_source_revision_replaces_entire_cohort_and_preserves_every_schedule_fact(monkeypatch, tmp_path):
    _, calls, read = setup_catalog(monkeypatch, tmp_path)
    item = event("session")
    before = deepcopy(item.to_dict())
    loader = startlists.StartListLoader(read)
    sources, evidence = loader.enrich([item], tmp_path, 2026)
    assert len(item.participants) == 2
    assert item.participants[0].metadata["country_code"] == "DE"
    assert "country_code" not in item.participants[1].metadata
    assert item.participants[1].metadata["start_list_nation"] == "AIN"
    assert sources and evidence[0]["athletes"] == 2
    after = item.to_dict()
    after["participants"] = []
    assert after == before
    loader.enrich([item], tmp_path, 2026)
    loader.enrich([item], tmp_path, 2027)
    assert calls == ["https://ewf.sport/meet", "https://ewf.sport/startbook-v1.pdf"]
    pages(monkeypatch, [EASY.replace("48A 2", "48A 1").replace("102 Example Neutral 01.01.2000 AIN 48 SE 160\n", "")])
    revised = startlists.StartListLoader(
        lambda url: b'<a href="/startbook-v2.pdf">Start book</a>' if url.endswith("/meet") else b"PDF2"
    )
    revised.enrich([item], tmp_path, 2026)
    assert len(item.participants) == 1
    assert item.participants[0].metadata["start_list_source_url"].endswith("v2.pdf")


@pytest.mark.parametrize(
    "response",
    [
        OSError("403 or unavailable"),
        EOFError("truncated gzip"),
        ZlibError("invalid gzip"),
        PdfReadError("invalid PDF"),
        b'<a href="/startbook-v1.pdf">one</a><a href="/startbook-v2.pdf">two</a>',
        b"no start list",
    ],
)
def test_missing_failed_or_ambiguous_book_does_not_add_facts_or_abort_schedule(monkeypatch, tmp_path, response):
    setup_catalog(monkeypatch, tmp_path)

    def read(_):
        if isinstance(response, Exception):
            raise response
        return response

    item = event("session")
    before = deepcopy(item.to_dict())
    assert startlists.StartListLoader(read).enrich([item], tmp_path, 2026) == ([], [])
    assert item.to_dict() == before


@pytest.mark.parametrize(
    "error", [OSError("unavailable"), EOFError("truncated"), ZlibError("corrupt"), PdfReadError("bad")]
)
def test_failed_pdf_parse_does_not_add_facts_or_abort_schedule(monkeypatch, tmp_path, error):
    _, _, read = setup_catalog(monkeypatch, tmp_path)

    def parse(*_):
        raise error

    monkeypatch.setattr(startlists, "parse_start_book", parse)
    item = event("session")
    before = deepcopy(item.to_dict())
    assert startlists.StartListLoader(read).enrich([item], tmp_path, 2026) == ([], [])
    assert item.to_dict() == before


def test_invalid_revised_book_cannot_partially_attach_athletes(monkeypatch, tmp_path):
    _, _, read = setup_catalog(monkeypatch, tmp_path)
    pages(monkeypatch, [EASY.replace("48A 2", "48A 3")])
    item = event("session")
    assert startlists.StartListLoader(read).enrich([item], tmp_path, 2026) == ([], [])
    assert item.participants == []


def test_budget_prevents_new_requests_and_failed_reads_are_cached_once():
    calls = []

    def read(url):
        calls.append(url)
        raise OSError("outage")

    loader = startlists.StartListLoader(read, clock=lambda: 10, budget=0)
    assert loader._read("https://ewf.sport/one") is None and not calls
    loader = startlists.StartListLoader(read)
    loader._read("https://ewf.sport/one")
    loader._read("https://ewf.sport/one")
    for index in range(7):
        loader._read(f"https://ewf.sport/{index}")
    assert len(calls) == 6


def test_public_export_keeps_only_requested_athlete_facts_and_scope(monkeypatch, tmp_path):
    from kickoff.web import _event_payload

    _, _, read = setup_catalog(monkeypatch, tmp_path)
    item = event("session")
    startlists.StartListLoader(read).enrich([item], tmp_path, 2026)
    item.participants[0].metadata.update(birth_date="private", raw_pdf="private", unrelated="private")
    payload = _event_payload(item)
    athlete = payload["participants"][0]
    assert athlete["entry_total_kg"] == 180
    assert athlete["country_code"] == "DE"
    assert athlete["start_list_nation"] == "GER"
    assert athlete["start_list_source_url"] == "https://ewf.sport/startbook-v1.pdf"
    assert all(field not in athlete for field in ["metadata", "birth_date", "raw_pdf", "unrelated", "logo_url"])
    for league, sport in [
        ("IWF_YOUTH_WORLDS", "weightlifting"),
        ("MASTERS_WORLDS", "weightlifting"),
        ("PGA_TOUR", "golf"),
    ]:
        other = deepcopy(item)
        other.league, other.sport = league, sport
        public = _event_payload(other)["participants"][0]
        assert not any(field in public for field in startlists.ENTRY_FIELDS)
        assert "country_code" not in public


def test_ambiguous_session_is_omitted_whole_without_discarding_other_confirmed_cohorts(monkeypatch, tmp_path):
    import json

    _, _, read = setup_catalog(monkeypatch, tmp_path)
    registry = json.loads((tmp_path / "2026-weightlifting.json").read_text())
    registry["events"].append({"id": "bad", "categories": [{"gender": "men", "weight_class": "79", "group": "A"}]})
    (tmp_path / "2026-weightlifting.json").write_text(json.dumps(registry))
    parsed = [
        startlists.Session(
            frozenset({("women", "48", "A")}), [startlists.Entry("101", "Confirmed Athlete", "GER", "48", 180, 7)], 1
        ),
        startlists.Session(
            frozenset({("men", "79", "A")}),
            [startlists.Entry("102", "Ambiguous Athlete", "GER", "71", 300, 13)],
            1,
            "Source class 71 versus session 79",
        ),
    ]
    monkeypatch.setattr(startlists, "parse_start_book", lambda *_: parsed)
    valid, invalid = event("session"), event("bad")
    sources, evidence = startlists.StartListLoader(read).enrich([valid, invalid], tmp_path, 2026)
    assert len(valid.participants) == 1 and not invalid.participants
    assert sources and evidence[0]["sessions"] == 1 and evidence[0]["parsed_sessions"] == 2
    assert evidence[0]["omitted_sessions"] == [{"event_id": "bad", "reason": parsed[1].issue}]


def test_publisher_calls_optional_loader_without_changing_schedule_or_primary_sources(monkeypatch, tmp_path):
    import json
    from pathlib import Path

    from kickoff import open_schedules
    from tests.test_reviewed_schedules import fake_open_read

    root = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(open_schedules, "read_url", fake_open_read)

    class Loader:
        def __init__(self):
            self.calls = []

        def enrich(self, events, directory, year):
            self.calls.append((year, directory))
            chosen = next(item for item in events if item.league == "WEIGHTLIFTING_EUROPE")
            from kickoff.models import Participant

            chosen.participants = [
                Participant(
                    name="Confirmed Athlete",
                    entity_type="athlete",
                    metadata={
                        "entry_total_kg": 180,
                        "start_list_nation": "GER",
                        "start_list_source_url": "https://ewf.sport/startbook.pdf",
                        "start_list_checked_date": "2026-11-03",
                    },
                )
            ]
            return [
                {
                    "kind": "weightlifting",
                    "name": "Official entries",
                    "url": "https://ewf.sport/startbook.pdf",
                    "license": "Schedule facts; no data license granted",
                }
            ], [{"kind": "weightlifting", "url": "https://ewf.sport/startbook.pdf", "sha256": "a" * 64}]

    loader = Loader()
    result = json.loads(
        open_schedules.refresh_open_schedules(
            2026, tmp_path, root / "data/reviewed", start_list_loader=loader
        ).read_text()
    )
    assert loader.calls == [(2026, root / "data/reviewed")]
    assert any(p.get("entry_total_kg") == 180 for item in result["events"] for p in item["participants"])
    assert any(source["name"] == "Official entries" for source in result["sources"])
    assert any(proof["url"] == "https://ewf.sport/startbook.pdf" for proof in result["input_evidence"])


def test_spanish_book_reassembles_wrapped_names_and_requires_full_session_count(monkeypatch):
    text = """CRONOGRAMA DE COMPETENCIAS
F 53 12:00 a.m. 2:00 p.m. 2
START LIST
F 53 KG A
Tanda F53 Hora de inicio: 2026-04-27 14:00
1 122 Example First Middle
Last BAR 23/4/1995 F 53 98
2 131 Example Second PAN 30/12/2000 F 53 145
"""
    pages(monkeypatch, [text])
    (session,) = startlists.parse_start_book(b"fixture", "owlcms-es")
    assert session.categories == frozenset({("women", "53", "A")})
    assert [(entry.name, entry.total) for entry in session.entries] == [
        ("Example First Middle Last", 98),
        ("Example Second", 145),
    ]
    pages(monkeypatch, [text.replace("2:00 p.m. 2", "2:00 p.m. 3")])
    with pytest.raises(ValueError, match="count"):
        startlists.parse_start_book(b"fixture", "owlcms-es")
    pages(monkeypatch, [text.replace("2 131", "4 131")])
    with pytest.raises(ValueError, match="sequence"):
        startlists.parse_start_book(b"fixture", "owlcms-es")


def test_catalog_has_only_reviewed_supported_publishers_and_country_identities():
    from datetime import date
    from urllib.parse import urlsplit

    from kickoff.countries import ISO_CODES

    config = startlists.catalog()
    assert {(row["league"], row["format"]) for row in config["books"]} == {
        ("WEIGHTLIFTING_EUROPE", "easywl"),
        ("WEIGHTLIFTING_ASIA", "owlcms"),
        ("WEIGHTLIFTING_PAN_AMERICA", "owlcms-es"),
    }
    assert len(config["books"]) == 3
    for book in config["books"]:
        assert book["year"] == 2026
        assert urlsplit(book["landing_url"]).netloc in {"ewf.sport", "awf.sport", "panampesas.org"}
    for code, identity in config["country_codes"].items():
        assert len(code) == 3 and code.isupper()
        assert identity["code"] in ISO_CODES | {"GB-ENG", "GB-SCT", "GB-WLS", "GB-NIR", "XK"}
        assert identity["source_url"].startswith("https://")
        assert date.fromisoformat(identity["checked_date"]).isoformat() == identity["checked_date"]
    assert all(code not in config["country_codes"] for code in ["AIN", "EWF", "MAL", "JER", "TRI"])
    assert {code: config["country_codes"][code]["code"] for code in ["BRN", "BRU", "SLO", "SVK"]} == {
        "BRN": "BH",
        "BRU": "BN",
        "SLO": "SI",
        "SVK": "SK",
    }
