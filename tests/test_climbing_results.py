"""Minimal invented SSR shapes, not copies of official pages or athlete data."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from kickoff.climbing_results import climbing_result, parse_climbing_podiums

URL = "https://www.worldclimbing.com/events/source-event-2026"
CHECKED = "2026-11-04"


def athlete(identity, rank):
    return {
        "athlete_id": identity,
        "rank": rank,
        "firstname": f"Given {identity}",
        "lastname": "FAMILY",
        "country": "GER",
    }


def category(identity=3, name="men", discipline="boulder", athletes=None):
    return {
        "dcat_id": identity,
        "dcat_name": f"{discipline.upper()} {name}",
        "discipline_kind": discipline,
        "category_name": name,
        "link": URL + "/results/index?discipline=boulder&category=women",
        "athletes": athletes if athletes is not None else [athlete(9, 3), athlete(1, 1), athlete(7, 2)],
    }


def page(categories, *, url=URL, marker="d3-event-podium-athletes", header="The Podium", split=False):
    props = {"dcats": categories, "headerTitle": header, "hideHeaderTitle": False}
    tree = ["$", "section", None, {"className": marker + " py-6", "children": ["$", "$L1", None, props]}]
    record = "1f:" + json.dumps(tree) + "\n"
    chunks = [record[: len(record) // 2], record[len(record) // 2 :]] if split else [record]
    return (
        f'<link rel="canonical" href="{url}">'
        + "".join("<script>self.__next_f.push(" + json.dumps([1, chunk]) + ")</script>" for chunk in chunks)
    ).encode()


def parse(body, **kwargs):
    return parse_climbing_podiums(body, source_url=URL, checked_date=CHECKED, **kwargs)


def event(*, tags=None, **fields):
    # The helper only consumes these existing normalized CalendarEvent fields.
    return SimpleNamespace(
        **{
            "event_id": "source-final",
            "calendar_date": "2026-08-28",
            "sport": "climbing",
            "event_type": "session",
            "round_or_stage": "final",
            "source_url": URL,
            "tags": tags if tags is not None else ["session", "Boulder", "Men"],
            "title": "Source event · Men's Boulder Final",
            **fields,
        }
    )


def test_explicit_category_rank_and_identity_win_over_wrong_link_and_array_order():
    body = page([category(), category(7, "women")], split=True)
    results = parse(body)
    result = climbing_result(event(), results)
    assert result["rows"] == [
        {"rank": 1, "name": "Given 1 FAMILY", "participant_id": "1", "country": "GER"},
        {"rank": 2, "name": "Given 7 FAMILY", "participant_id": "7", "country": "GER"},
        {"rank": 3, "name": "Given 9 FAMILY", "participant_id": "9", "country": "GER"},
    ]
    assert result["source_url"] == URL
    assert result["checked_date"] == CHECKED
    assert result["scope"]["category"] == "men"
    assert result["_complete"] is True
    assert "results/index" not in result["source_url"]


def test_source_supported_tied_third_is_not_truncated_or_renumbered():
    result = parse(page([category(athletes=[athlete(1, 1), athlete(2, 2), athlete(3, 3), athlete(4, 3)])]))[0]
    assert [row["rank"] for row in result["rows"]] == [1, 2, 3, 3]


def test_youth_age_gender_and_discipline_are_exact_source_scope():
    results = parse(page([category(1, "u17 men", "lead"), category(2, "u19 men", "lead"), category(3, "men", "lead")]))
    chosen = climbing_result(event(tags=["Lead", "Men", "U17", "Youth"]), results)
    assert chosen["scope"]["category_id"] == "1"
    assert climbing_result(event(tags=["Lead", "Women", "U17", "Youth"]), results) is None
    assert climbing_result(event(tags=["Boulder", "Men", "U17", "Youth"]), results) is None
    assert climbing_result(event(tags=["Lead", "Men", "Youth"]), results) is None


def test_relay_uses_only_explicit_unique_national_team_codes_not_individual_speed_podium():
    teams = [
        {"rank": rank, "country": country, "athlete_id": None, "firstname": None, "lastname": None}
        for rank, country in [(1, "CHN"), (2, "USA"), (3, "UKR")]
    ]
    results = parse(page([category(1, "men", "speed"), category(843, "men", "speed_relay", teams)]))
    relay = climbing_result(event(tags=["Speed", "Men"], title="Source event · Men's Speed Relay Final"), results)
    assert relay["scope"]["discipline"] == "speed_relay"
    assert relay["scope"]["competitor_kind"] == "national_team"
    assert relay["rows"] == [
        {"rank": rank, "name": country, "country": country} for rank, country in [(1, "CHN"), (2, "USA"), (3, "UKR")]
    ]
    individual = climbing_result(event(tags=["Speed", "Men"], title="Source event · Men's Speed Final"), results)
    assert individual["scope"]["discipline"] == "speed"
    assert (
        climbing_result(event(tags=["Speed", "Men"], title="Source event · Men's Speed Relay Final"), results[:1])
        is None
    )
    teams[1]["country"] = "CHN"
    repeated = parse(page([category(843, "men", "speed_relay", teams)]))[0]
    assert [(row["rank"], row["name"]) for row in repeated["rows"]] == [(1, "CHN"), (2, "CHN"), (3, "UKR")]
    assert all("participant_id" not in row for row in repeated["rows"])
    teams[1]["rank"] = 1
    assert parse(page([category(843, "men", "speed_relay", teams)])) == []


def test_mixed_relay_is_not_split_into_separate_mens_and_womens_results():
    teams = [{"rank": rank, "country": country} for rank, country in [(1, "JPN"), (2, "CHN"), (3, "USA")]]
    results = parse(page([category(1, "mixed", "speed_relay", teams), category(2, "men", "speed")]))
    result = climbing_result(event(tags=["Speed", "Men", "Women"], title="Source · Mixed Speed Relay Final"), results)
    assert result["scope"]["category"] == "mixed"
    assert climbing_result(event(tags=["Speed", "Men", "Women"], title="Source · Speed Final"), results) is None


@pytest.mark.parametrize(
    "fields",
    [
        {"source_url": URL + "-different"},
        {"round_or_stage": "semi-final"},
        {"event_type": "tournament"},
        {"sport": "golf"},
    ],
)
def test_wrong_event_or_nonfinal_cannot_get_result(fields):
    assert climbing_result(event(**fields), parse(page([category()]))) is None


@pytest.mark.parametrize("tags", [["Lead", "Para"], ["Lead", "Men", "Para"], ["Speed"], ["Boulder", "Men", "Women"]])
def test_unallocated_category_blocks_stay_missing_even_with_event_podiums(tags):
    assert climbing_result(event(tags=tags), parse(page([category()]))) is None


@pytest.mark.parametrize(
    "body",
    [
        None,
        b"",
        b"<html>Results client shell</html>",
        b"\xff",
        page([]),
        page([category()], header="Qualification ranking"),
        page([category()], marker="related-event-podium"),
        page([category()], url=URL + "-other"),
    ],
)
def test_missing_malformed_or_unscoped_source_is_optional_absence(body):
    assert parse(body) == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c.update(athletes=[]),
        lambda c: c["athletes"][0].update(rank=True),
        lambda c: c["athletes"][0].update(lastname=None),
        lambda c: c["athletes"][0].update(athlete_id=1),
        lambda c: c.update(dcat_id=None),
        lambda c: c.update(discipline_kind="qualifying"),
    ],
)
def test_ambiguous_primary_identity_or_rank_is_not_a_complete_result(mutate):
    c = category()
    mutate(c)
    assert parse(page([c])) == []


def test_unknown_country_is_omitted_without_guessing_from_flag_or_photo_url():
    c = category()
    c["athletes"][0].update(country="?", flag_url="https://example.com/AUS.png", photo_url="private-biography")
    result = parse(page([c]))[0]
    assert "country" not in result["rows"][2]
    assert "flag_url" not in json.dumps(result)
    assert "photo_url" not in json.dumps(result)


def test_duplicate_matching_categories_are_ambiguous_and_bad_sibling_does_not_hide_valid_category():
    c = category()
    assert climbing_result(event(), parse(page([c, deepcopy(c)]))) is None
    invalid = category(7, "women", athletes=[{"rank": 1}])
    assert len(parse(page([c, invalid]))) == 1


def allocation(
    *, identity="source-final", title="Source event · Men's Boulder Final", tags=None, day="2026-08-28", categories=None
):
    expected = (
        categories
        if categories is not None
        else [
            {"category_id": "31", "category": "men b1", "discipline": "lead"},
            {"category_id": "32", "category": "men b2", "discipline": "lead"},
        ]
    )
    return {
        "event_id": identity,
        "event_title": title,
        "event_source_url": URL,
        "calendar_date": day,
        "scope_tags": tags if tags is not None else ["Lead", "Men", "Para"],
        "categories": expected,
        "expected_category_count": len(expected),
        "allocation_complete": True,
        "allocation_source": {
            "source_url": "https://ifsc.results.info/events/42/infosheet",
            "checked_date": CHECKED,
            "page": 4,
            "scope": "Invented test programme explicitly assigns these classes to this dated final block.",
        },
    }


def test_explicit_para_sessions_do_not_cross_assign_classes_or_dates():
    source = parse(
        page(
            [
                category(31, "men b1", "lead"),
                category(32, "men b2", "lead"),
                category(33, "women b1", "lead"),
                category(34, "women b2", "lead"),
            ]
        )
    )
    one = event(event_id="one", title="Source · Women's Lead Final Session 1", tags=["Lead", "Women", "Para"])
    two = event(
        event_id="two",
        title="Source · Women's Lead Final Session 2",
        tags=["Lead", "Women", "Para"],
        calendar_date="2026-08-29",
    )
    first = allocation(
        identity="one",
        title=one.title,
        tags=["Lead", "Women", "Para"],
        categories=[{"category_id": "33", "category": "women b1", "discipline": "lead"}],
    )
    second = allocation(
        identity="two",
        title=two.title,
        tags=["Lead", "Women", "Para"],
        day="2026-08-29",
        categories=[{"category_id": "34", "category": "women b2", "discipline": "lead"}],
    )
    assert climbing_result(one, source, allocation=first)["scope"]["category_id"] == "33"
    assert climbing_result(two, source, allocation=second)["scope"]["category_id"] == "34"
    assert climbing_result(one, source, allocation=second) is None
    assert climbing_result(two, source, allocation=first) is None
    wrong_gender = deepcopy(first)
    wrong_gender["scope_tags"] = ["Lead", "Men", "Para"]
    assert climbing_result(one, source, allocation=wrong_gender) is None


def test_complete_programme_all_category_block_returns_separate_labelled_podiums():
    source = parse(page([category(31, "men b1", "lead"), category(32, "men b2", "lead")]))
    final = event(tags=["Lead", "Para"])
    block = allocation(tags=["Lead", "Para"])
    result = climbing_result(final, source, allocation=block)
    assert result["kind"] == "podiums"
    assert [group["label"] for group in result["categories"]] == ["LEAD men b1", "LEAD men b2"]
    assert all([row["rank"] for row in group["rows"]] == [1, 2, 3] for group in result["categories"])
    assert result["scope"]["category_ids"] == ["31", "32"]
    assert result["scope"]["expected_category_count"] == 2
    assert result["_complete"] is True
    assert result["allocation_source"] == block["allocation_source"]
    assert climbing_result(final, source) is None


def test_missing_expected_category_is_partial_and_cannot_freeze_the_block():
    source = parse(page([category(31, "men b1", "lead")]))
    result = climbing_result(event(tags=["Lead", "Men", "Para"]), source, allocation=allocation())
    assert result["kind"] == "podiums"
    assert len(result["categories"]) == 1
    assert result["_complete"] is False
    assert climbing_result(event(tags=["Lead", "Men", "Para"]), [], allocation=allocation()) is None


def test_unresolved_gender_allocation_stays_unconfirmed_even_when_known_classes_have_podiums():
    source = parse(page([category(31, "men b1", "lead"), category(32, "men b2", "lead")]))
    block = allocation()
    block["allocation_complete"] = False
    block["unresolved_categories"] = [{"category_id": "99", "category": "combined al1"}]
    result = climbing_result(event(tags=["Lead", "Men", "Para"]), source, allocation=block)
    assert len(result["categories"]) == 2
    assert result["_complete"] is False
    block["allocation_complete"] = True
    block["expected_category_count"] = 3
    assert climbing_result(event(tags=["Lead", "Men", "Para"]), source, allocation=block)["_complete"] is False


def test_ambiguous_or_mixed_observation_provenance_does_not_become_one_complete_block():
    source = parse(page([category(31, "men b1", "lead"), category(32, "men b2", "lead")]))
    final = event(tags=["Lead", "Men", "Para"])
    duplicated = [*source, deepcopy(source[0])]
    partial = climbing_result(final, duplicated, allocation=allocation())
    assert partial["_complete"] is False
    assert [group["label"] for group in partial["categories"]] == ["LEAD men b2"]


def test_reviewed_block_receipt_has_unique_exact_scope_and_source_evidence():
    from datetime import date
    from pathlib import Path

    receipt = json.loads((Path(__file__).parents[1] / "data/reviewed/receipts/climbing-result-blocks.json").read_text())
    assert receipt["schema_version"] == 1
    assert len({block["event_id"] for block in receipt["blocks"]}) == len(receipt["blocks"])
    for block in receipt["blocks"]:
        date.fromisoformat(block["calendar_date"])
        assert block["expected_category_count"] == len(block["categories"])
        assert len({row["category_id"] for row in block["categories"]}) == len(block["categories"])
        assert {row["discipline"].title() for row in block["categories"]} <= set(block["scope_tags"])
        for key in ["allocation_source", "category_source"]:
            proof = block[key]
            date.fromisoformat(proof["checked_date"])
        assert block["allocation_source"]["page"] > 0
        assert block["allocation_complete"] or block.get("unresolved_categories")
