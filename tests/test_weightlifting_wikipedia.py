"""Small invented MediaWiki tables; no fetched pages, DOB or copied source rows."""

import hashlib
import json
from copy import deepcopy

import pytest

from kickoff.weightlifting_wikipedia import (
    api_url,
    class_requests,
    classes_for_session,
    competition_title,
    parse_classes,
)

MAIN = "2026 World Weightlifting Championships"
TITLE = MAIN + " – Men's 60 kg"
CHECKED = "2026-11-04"


def payload(html, *, title=TITLE, links=(), revid=1234):
    return json.dumps({"parse": {"title": title, "revid": revid, "text": html, "links": list(links)}}).encode()


def medal(rank):
    suffix = {1: "st", 2: "nd", 3: "rd"}[rank]
    return f'<span data-sort-value="0{rank} !"><img alt="{rank}{suffix} place, medalist(s)"></span>'


def athlete(name, nation="ZZZ"):
    return f'<a href="/wiki/{name}">{name}</a> (<abbr title="Source nation">{nation}</abbr>)'


def row(rank, name, snatch, clean, total, *, group="A", srank=1, crank=1):
    values = [
        medal(rank) if rank in {1, 2, 3} else rank,
        athlete(name),
        group,
        *snatch,
        medal(srank) if srank in {1, 2, 3} else srank,
        *clean,
        medal(crank) if crank in {1, 2, 3} else crank,
        total,
    ]
    return "<tr>" + "".join(f"<td>{value}</td>" for value in values) + "</tr>"


def table(*, extra="", first_attempt="70", group=True):
    head = '<tr><th rowspan="2">Rank</th><th rowspan="2">Athlete</th><th rowspan="2">Group</th>'
    head += '<th colspan="4">Snatch (kg)</th><th colspan="4">Clean &amp; Jerk (kg)</th><th rowspan="2">Total</th></tr>'
    head += "<tr>" + "<th>1</th><th>2</th><th>3</th><th>Rank</th>" * 2 + "</tr>"
    html = "<table class=wikitable>" + head
    html += row(1, "Example_One", [first_attempt, "<s>75</s>", "<b>80</b>"], ["90", "95", "100"], 180, srank=2, crank=1)
    html += row(2, "Example_Two", ["80", "85", "90"], ["75", "80", "85"], 175, group="B", srank=1, crank=3)
    html += row(3, "Example_Three", ["60", "65", "70"], ["85", "90", "95"], 165, srank=3, crank=2)
    html += extra + "</table>"
    if not group:
        html = html.replace('<th rowspan="2">Group</th>', "").replace("<td>A</td>", "").replace("<td>B</td>", "")
    return html


def infobox(value="27 October"):
    return f"<table class=infobox><tr><th>Date</th><td>{value}</td></tr></table>"


def parse(html=None, **kwargs):
    title = kwargs.get("title", TITLE)
    content = payload(infobox() + (table() if html is None else html), **kwargs)
    return parse_classes(content, input_url=api_url(title), checked_date=CHECKED)


def session(identity="session-a", *, group="A", weight="60", league="IWF_WORLDS"):
    return {
        "id": identity,
        "league": league,
        "start_date": "2026-10-27",
        "local_time": "17:00",
        "categories": [{"gender": "men", "weight_class": weight, "group": group}],
    }


def test_all_six_explicit_attempts_and_independent_lift_medals_are_preserved():
    (result,) = parse()
    assert result["_complete"]
    first = result["athletes"][0]
    assert first["snatch"] == [
        {"weight_kg": 70, "status": "made"},
        {"weight_kg": 75, "status": "missed"},
        {"weight_kg": 80, "status": "made"},
    ]
    assert [a["weight_kg"] for a in first["clean_and_jerk"]] == [90, 95, 100]
    assert first["total_kg"] == 180 and first["total_rank"] == 1
    assert (first["snatch_rank"], first["clean_and_jerk_rank"]) == (2, 1)
    assert [r["rank"] for r in result["snatch_medalists"]] == [2, 1, 3]
    assert [r["rank"] for r in result["clean_and_jerk_medalists"]] == [1, 3, 2]
    assert len(result["total_medalists"]) == 3
    assert first["source_article_url"] == "https://en.wikipedia.org/wiki/Example_One"
    assert not {"lot", "participant_id", "born", "birth_date", "bodyweight"} & first.keys()
    assert first["_row_index"] == 0


@pytest.mark.parametrize(
    "mark",
    [
        "<s>70</s>",
        "<strike>70</strike>",
        "<del>70</del>",
        '<span style="text-decoration:line-through">70</span>',
        "−70",
        "-70",
    ],
)
def test_literal_missed_marks_never_come_from_the_best_lift(mark):
    (result,) = parse(table(first_attempt=mark))
    assert result["athletes"][0]["snatch"][0] == {"weight_kg": 70, "status": "missed"}


@pytest.mark.parametrize("token", ["70 WR", "70 WR, CR", "70 WYR"])
def test_record_annotations_are_not_attempts_or_medal_ranks(token):
    (result,) = parse(table(first_attempt=token))
    assert result["athletes"][0]["snatch"][0] == {"weight_kg": 70, "status": "made"}


def test_explicit_dns_spanning_cells_means_unused_attempts_without_zero_weights():
    dns = (
        "<tr><td>—</td><td>"
        + athlete("Absent")
        + "</td><td>B</td><td colspan=4>Did not start</td><td colspan=4>Did not start</td><td>—</td></tr>"
    )
    (result,) = parse(table(extra=dns))
    last = result["athletes"][-1]
    assert last["snatch"] + last["clean_and_jerk"] == [{"weight_kg": None, "status": "unused"}] * 6
    assert last["total_kg"] is None and last["total_rank"] is None
    assert result["_complete"]


def test_unknown_or_blank_attempt_omits_only_that_row_and_keeps_class_nonfreezable():
    (result,) = parse(table(first_attempt=""))
    assert len(result["athletes"]) == 2
    assert result["_omitted_rows"] == 1 and result["_complete"] is False
    assert [r["rank"] for r in result["total_medalists"]] == [2, 3]


def test_total_contradiction_is_not_silently_corrected_from_the_best_lifts():
    (result,) = parse(table().replace("<td>180</td>", "<td>179</td>"))
    assert result["_complete"] is False and result["_omitted_rows"] == 1
    assert all(row["name"] != "Example_One" for row in result["athletes"])


def test_tied_source_lift_medals_are_never_reassigned_or_sorted_by_weight():
    (result,) = parse(table().replace(medal(2), medal(1)))
    assert [row["rank"] for row in result["snatch_medalists"]] == [1, 1, 3]


def test_guest_annotation_is_explicit_and_not_inferred_from_an_athletes_surname():
    (result,) = parse(table().replace("Example_One", "Example Guest"))
    assert result["athletes"][0]["guest"] is False
    (result,) = parse(table().replace("Example_One", "Example_One [Guest]"))
    assert result["athletes"][0]["guest"] is True
    assert all(row["name"] != "Example_One" for row in result["total_medalists"])


def test_games_trailing_country_link_is_a_literal_noc_not_part_of_the_athlete_name():
    original = athlete("Example_One")
    games = '<a href="/wiki/Example_One">Example_One</a> <span style="font-size:90%;">(<a href="/wiki/North_Korea_at_the_2026_Asian_Games">PRK</a>)</span>'
    (result,) = parse(table().replace(original, games))
    row = result["athletes"][0]
    assert row["name"] == "Example_One" and row["nation"] == "PRK"
    assert row["source_article_url"] == "https://en.wikipedia.org/wiki/Example_One"
    assert result["total_medalists"][0]["name"] == "Example_One"
    assert result["total_medalists"][0]["nation"] == "PRK"
    assert "country_code" not in row  # No flag or ISO mapping is inferred here.


@pytest.mark.parametrize("code", ["EWF", "WRT"])
def test_parenthesized_abbreviation_keeps_non_country_labels_without_inventing_flags(code):
    replacement = f'<a href="/wiki/Example_One">Example_One</a> <abbr title="Literal source team label">({code})</abbr>'
    (result,) = parse(table().replace(athlete("Example_One"), replacement))
    row = result["athletes"][0]
    assert row["name"] == "Example_One" and row["nation"] == code
    assert "country_code" not in row


def test_parenthesized_name_suffix_without_a_structured_country_code_stays_in_the_name():
    replacement = '<a href="/wiki/Example_One">Example_One (PRK)</a>'
    (result,) = parse(table().replace(athlete("Example_One"), replacement))
    assert result["athletes"][0]["name"] == "Example_One (PRK)"
    assert result["athletes"][0]["nation"] == ""


def test_api_revision_hash_request_identity_and_explicit_class_end_bound():
    content = payload(infobox("27–28 October") + table())
    (result,) = parse_classes(content, input_url=api_url(TITLE), checked_date=CHECKED)
    assert result["revision"] == "1234" and "oldid=1234" in result["source_url"]
    assert result["sha256"] == hashlib.sha256(content).hexdigest()
    assert result["hash_scope"] == "raw MediaWiki API JSON response bytes"
    assert result["checked_date"] == CHECKED
    assert result["_source_date"] == "2026-10-28" and result["_ended_before"] == "2026-10-29"
    assert parse_classes(content, input_url=api_url(TITLE.replace("60", "65")), checked_date=CHECKED) == []
    assert (
        parse_classes(
            content, input_url="https://en.wikipedia.org/w/api.php?action=parse&oldid=999", checked_date=CHECKED
        )
        == []
    )


def test_inline_europe_classes_use_literal_heading_and_not_the_whole_competition_date():
    title = "2026 European Weightlifting Championships"
    (result,) = parse(
        infobox("19–26 April 2026") + "<h2>Men's results</h2><h3 id=\"Men's_60_kg\">Men's 60 kg</h3>" + table(),
        title=title,
    )
    assert (result["league"], result["gender"], result["weight_class"]) == ("WEIGHTLIFTING_EUROPE", "men", "60")
    assert "#Men%27s_60_kg" in result["source_url"]
    assert result["_source_date"] is result["_ended_before"] is None


def test_class_title_and_section_disagreement_and_duplicate_tables_are_ambiguous():
    assert parse("<h3>Women's 60 kg</h3>" + table()) == []
    assert parse(table() + table()) == []


def test_html_leading_integer_span_matches_browser_without_inventing_an_extra_column():
    (result,) = parse(table().replace('rowspan="2"', 'rowspan=2width="275"', 1))
    assert len(result["athletes"]) == 3 and result["_complete"]


def overview():
    html = "<h2>Medal overview</h2><h3>Men</h3><table><tr><th>Event</th><th></th>"
    html += "<th colspan=2>Gold</th><th colspan=2>Silver</th><th colspan=2>Bronze</th></tr>"
    for index, lift in enumerate(["Snatch", "Clean &amp; Jerk", "Total"]):
        html += "<tr>" + ("<td rowspan=3>– + 110 kg</td>" if index == 0 else "") + f"<td>{lift}</td>"
        html += (
            "".join(f"<td>{athlete(f'Medalist_{i}')}</td><td>{100 + index * 100 + i} kg</td>" for i in [1, 2, 3])
            + "</tr>"
        )
    return html + "</table>"


def test_medal_only_continental_classes_are_useful_explicit_partial_facts_with_no_attempts():
    (result,) = parse(overview(), title="2026 Pan American Weightlifting Championships")
    assert result["weight_class"] == "+110" and result["athletes"] == []
    assert result["_complete"] is False and result["_ended_before"] is None
    for lift in ["total", "snatch", "clean_and_jerk"]:
        assert [row["rank"] for row in result[f"{lift}_medalists"]] == [1, 2, 3]
    assert [row["weight_kg"] for row in result["total_medalists"]] == [301, 302, 303]
    assert "#" not in result["source_url"]  # The source supplied no heading ID.


@pytest.mark.parametrize("heading_id", ["Men", "Men_2"])
def test_overview_source_uses_only_actual_heading_ids_and_keeps_raw_hash_and_facts(heading_id):
    title = "2026 Pan American Weightlifting Championships"
    html = overview().replace("<h3>Men</h3>", f'<h3 id="{heading_id}">Men</h3>')
    content = payload(html, title=title)
    (result,) = parse_classes(content, input_url=api_url(title), checked_date=CHECKED)
    assert result["source_url"].endswith(f"#{heading_id}")
    assert "Men%27s_110_kg" not in result["source_url"]
    assert result["sha256"] == hashlib.sha256(content).hexdigest()
    assert result["revision"] == "1234" and result["checked_date"] == CHECKED
    assert [row["rank"] for row in result["total_medalists"]] == [1, 2, 3]
    assert "_source_anchor" not in result


def test_full_width_class_overview_and_explicit_name_country_line_break_keep_literal_identity():
    html = "<h3>Men</h3><table><tr><th>Event</th><th colspan=2>Gold</th><th colspan=2>Silver</th><th colspan=2>Bronze</th></tr><tr><td colspan=7>60 kg (details)</td></tr>"
    for lift in ["Snatch", "Clean &amp; Jerk", "Total"]:
        html += f"<tr><td>{lift}</td>"
        for rank in [1, 2, 3]:
            html += f'<td><a href="/wiki/Person_{rank}">Person_{rank}</a><br><span class=flagicon><img alt="Never infer a country from this"></span><a href="/wiki/Source_nation">Source nation</a></td><td>{100 + rank} kg AF</td>'
        html += "</tr>"
    (result,) = parse(html + "</table>", title=MAIN)
    assert result["weight_class"] == "60" and result["athletes"] == []
    assert result["total_medalists"][0]["name"] == "Person_1"
    assert result["total_medalists"][0]["nation"] == "Source nation"
    assert result["total_medalists"][0]["source_article_url"] == "https://en.wikipedia.org/wiki/Person_1"


def test_missing_medal_weight_keeps_a_named_medalist_but_never_publishes_a_placeholder_athlete():
    html = overview().replace("<td>301 kg</td>", "<td>—</td>")
    (result,) = parse(html, title="2026 Pan American Weightlifting Championships")
    assert result["total_medalists"][0]["name"] == "Medalist_1"
    assert "weight_kg" not in result["total_medalists"][0]
    html = html.replace(athlete("Medalist_1"), "—")
    (result,) = parse(html, title="2026 Pan American Weightlifting Championships")
    assert [row["rank"] for row in result["total_medalists"]] == [2, 3]


def test_actual_existing_class_links_are_discovered_without_synthetic_pages_or_youth_scope():
    links = [
        {"title": TITLE, "ns": 0, "exists": True},
        {"title": TITLE.replace("60", "65"), "ns": 0, "exists": False},
        {"title": "2026 European Weightlifting Championships – Men's 60 kg", "ns": 0, "exists": True},
        {"title": "2026 World Junior Weightlifting Championships – Men's 60 kg", "ns": 0, "exists": True},
    ]
    content = payload("", title=MAIN, links=links)
    (request,) = class_requests(content, input_url=api_url(MAIN), checked_date=CHECKED)
    assert (request["title"], request["weight_class"]) == (TITLE, "60")
    assert request["input_url"] == api_url(TITLE)
    assert competition_title("IWF_JUNIOR_WORLDS", 2026) is None
    assert competition_title("IWF_YOUTH_WORLDS", 2026) is None
    assert competition_title("MASTERS_WORLDS", 2026) is None


@pytest.mark.parametrize("body", [None, b"not JSON", b"{}", b'{"error":{"code":"missingtitle"}}'])
def test_optional_missing_or_malformed_api_never_aborts_publication(body):
    assert parse_classes(body, input_url=api_url(TITLE), checked_date=CHECKED) == []
    assert class_requests(body, input_url=api_url(TITLE), checked_date=CHECKED) == []


def test_session_groups_use_source_membership_but_global_class_medals_stay_global():
    classes = parse()
    a, b = session(), session("session-b", group="B")
    before = deepcopy((classes, a, b))
    (result,) = classes_for_session(classes, b, reviewed_sessions=[a, b])
    assert [row["name"] for row in result["athletes"]] == ["Example_Two"]
    assert result["athletes"][0]["total_rank"] == 2
    assert [row["rank"] for row in result["total_medalists"]] == [1, 2, 3]
    assert (classes, a, b) == before and b["local_time"] == "17:00"


def test_missing_or_ambiguous_group_membership_never_becomes_group_a_from_rank():
    classes = parse(table(group=False))
    a, b = session(), session("session-b", group="B")
    for peers in [[a], [a, b]]:
        (result,) = classes_for_session(classes, a, reviewed_sessions=peers)
        assert result["athletes"] == [] and result["_complete"] is False
        assert len(result["total_medalists"]) == 3
    (result,) = classes_for_session(parse(), a, reviewed_sessions=[a, session("another-a")])
    assert result["athletes"] == [] and result["_complete"] is False


def test_unmatched_literal_weight_class_does_not_fuzzily_join_neighbouring_class():
    assert classes_for_session(parse(), session(weight="61"), reviewed_sessions=[session(weight="61")]) == []


def test_complete_class_article_is_preferred_over_its_partial_overview_without_mutating_either():
    (full,) = parse()
    partial = {**deepcopy(full), "athletes": [], "_complete": False}
    a = session()
    (result,) = classes_for_session([partial, full], a, reviewed_sessions=[a])
    assert len(result["athletes"]) == 2 and result["_complete"]
    assert partial["athletes"] == [] and len(full["athletes"]) == 3


def test_missing_class_in_a_combined_session_keeps_available_facts_nonfreezable():
    item = session()
    item["categories"].append({"gender": "men", "weight_class": "65", "group": "A"})
    (result,) = classes_for_session(parse(), item, reviewed_sessions=[item])
    assert result["athletes"] and result["_complete"] is False


def test_explicit_games_best_cells_validate_marks_but_never_generate_lift_medals():
    # Source best cells replace the two independent lift rank cells.
    html = "<table><tr><th rowspan=2>Rank</th><th rowspan=2>Athlete</th><th rowspan=2>Group</th><th colspan=4>Snatch (kg)</th><th colspan=4>Clean &amp; Jerk (kg)</th><th rowspan=2>Total</th></tr>"
    html += "<tr>" + "<th>1</th><th>2</th><th>3</th><th>Result</th>" * 2 + "</tr>"
    for rank, (name, snatch, clean) in enumerate(
        [("Example_One", 80, 100), ("Example_Two", 90, 85), ("Example_Three", 70, 95)], 1
    ):
        html += row(
            rank, name, [str(snatch)] * 3, [str(clean)] * 3, snatch + clean, srank=str(snatch), crank=str(clean)
        )
    html += "</table>"
    (result,) = parse(html)
    assert result["_complete"] and not result["snatch_medalists"] and not result["clean_and_jerk_medalists"]
    assert all(row["snatch_rank"] is None for row in result["athletes"])
    (partial,) = parse(html.replace("<td>80</td>", "<td><s>80</s></td>", 3))
    assert partial["_complete"] is False
