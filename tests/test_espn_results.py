"""Minimal offline ESPN source shapes, deliberately not copied feed payloads."""

from copy import deepcopy

import pytest

from kickoff.espn_results import espn_result

PROOF = {
    "source_url": "https://site.api.espn.com/scoreboard?dates=2025",
    "checked_date": "2026-11-03",
}


def status(name="STATUS_FINAL", *, completed=True, state="post"):
    return {"type": {"name": name, "completed": completed, "state": state}}


def player(identity, name, *, winner=False, rank=None, sets=None):
    row = {"id": identity, "type": "athlete", "athlete": {"fullName": name}, "winner": winner}
    if rank is not None:
        row["order"] = rank
    if sets is not None:
        row["linescores"] = sets
    return row


def race():
    # Unranked entrants precede the winner in the real Daytona scoreboard.
    return {
        "id": "race",
        "status": status(),
        "competitions": [
            {
                "id": "race",
                "status": status(),
                "competitors": [
                    player("unranked", "Unranked Driver"),
                    player("third", "Third Driver", rank=3),
                    player("winner", "Winning Driver", rank=1, winner=True),
                    player("second", "Second Driver", rank=2),
                ],
            }
        ],
    }


def tennis(league="ATP", name="STATUS_FINAL"):
    kind = {"slug": "mens-singles", "id": "1"} if league == "ATP" else {"slug": "womens-singles", "id": "2"}
    return {
        "status": status(),
        "previousWinners": [{"athlete": {"fullName": "Historical Champion"}}],
        "groupings": [
            {
                "grouping": kind,
                "competitions": [
                    {
                        "id": "final",
                        "type": dict(kind),
                        "round": {"displayName": "Final", "id": "7"},
                        "status": status(name),
                        "competitors": [
                            player("runner", "Runner Up", sets=[{"value": 6.0, "tiebreak": 5, "winner": False}]),
                            player(
                                "winner",
                                "Champion",
                                winner=True,
                                sets=[{"value": 7.0, "tiebreak": 7, "winner": True}],
                            ),
                        ],
                    }
                ],
            }
        ],
    }


def final(row):
    return row["groupings"][0]["competitions"][0]


@pytest.mark.parametrize("league", ["NASCAR_CUP", "INDYCAR"])
def test_podium_is_explicit_finishing_rank_not_input_order_and_keeps_provenance(league):
    row = race()
    before = deepcopy(row)
    result = espn_result(row, league, **PROOF)
    assert result == {
        "kind": "podium",
        "_complete": True,
        "rows": [
            {"rank": 1, "name": "Winning Driver", "participant_id": "winner"},
            {"rank": 2, "name": "Second Driver", "participant_id": "second"},
            {"rank": 3, "name": "Third Driver", "participant_id": "third"},
        ],
        **PROOF,
    }
    assert row == before


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r.update(status=status(completed=False)),
        lambda r: r["competitions"][0].update(status=status(state="in")),
        lambda r: r["competitions"][0].update(status=status("STATUS_CANCELED")),
        lambda r: r["competitions"][0].update(id="other-race"),
        lambda r: r["competitions"].append(deepcopy(r["competitions"][0])),
        lambda r: r["competitions"][0]["competitors"][1].update(order=2),
        lambda r: r["competitions"][0]["competitors"][1].update(order=None),
        lambda r: r["competitions"][0]["competitors"][1].update(order=2.5),
        lambda r: r["competitions"][0]["competitors"][1].update(id="winner"),
        lambda r: r["competitions"][0]["competitors"][1].update(winner=True),
        lambda r: r["competitions"][0]["competitors"][2].update(order=True),
        lambda r: r["competitions"][0]["competitors"][2]["athlete"].update(fullName="TBD"),
    ],
)
def test_partial_ambiguous_or_unfinished_podium_is_not_a_result(mutation):
    row = race()
    mutation(row)
    assert espn_result(row, "NASCAR_CUP", **PROOF) is None


@pytest.mark.parametrize("league", ["ATP", "WTA"])
def test_singles_final_uses_own_tour_group_explicit_winner_and_supplied_set_facts(league):
    row = tennis(league)
    other = tennis("WTA" if league == "ATP" else "ATP")["groupings"][0]
    other["competitions"][0]["competitors"][1]["athlete"]["fullName"] = "Other Tour Winner"
    row["groupings"].insert(0, other)
    before = deepcopy(row)
    result = espn_result(row, league, **PROOF)
    assert result == {
        "kind": "tennis-final",
        "_complete": True,
        "winner": {"name": "Champion", "participant_id": "winner"},
        "runner_up": {"name": "Runner Up", "participant_id": "runner"},
        "status": "final",
        "score": {
            "winner": [{"value": 7, "tiebreak": 7, "winner": True}],
            "runner_up": [{"value": 6, "tiebreak": 5, "winner": False}],
        },
        **PROOF,
    }
    assert row == before


def test_completed_final_is_authoritative_despite_incomplete_aggregate_tournament_status():
    row = tennis()
    row["status"] = status("STATUS_IN_PROGRESS", completed=False, state="in")
    assert espn_result(row, "ATP", **PROOF)["winner"]["name"] == "Champion"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: final(r).update(status=status(completed=False)),
        lambda r: final(r).update(status=status("STATUS_SCHEDULED", completed=False, state="pre")),
        lambda r: final(r).update(status=status("STATUS_CANCELED")),
        lambda r: final(r)["round"].update(displayName="Semifinal"),
        lambda r: final(r)["round"].update(id="6"),
        lambda r: final(r)["type"].update(slug="mens-doubles"),
        lambda r: final(r)["type"].update(id="2"),
        lambda r: final(r)["competitors"][0].update(winner=True),
        lambda r: final(r)["competitors"][1].update(winner=False),
        lambda r: final(r)["competitors"][0].pop("winner"),
        lambda r: final(r)["competitors"][0].update(id="winner"),
        lambda r: final(r)["competitors"][1]["athlete"].update(fullName="TBA"),
        lambda r: final(r)["competitors"].pop(),
        lambda r: r["groupings"][0]["competitions"].append(deepcopy(final(r))),
    ],
)
def test_tennis_rejects_wrong_category_ambiguous_winner_and_incomplete_final(mutation):
    row = tennis()
    mutation(row)
    assert espn_result(row, "ATP", **PROOF) is None


@pytest.mark.parametrize("name", ["STATUS_RETIRED", "STATUS_WALKOVER"])
def test_retired_or_walkover_can_have_an_explicit_winner_without_a_score(name):
    row = tennis(name=name)
    for p in final(row)["competitors"]:
        p.pop("linescores")
    result = espn_result(row, "ATP", **PROOF)
    assert result["winner"]["name"] == "Champion"
    assert result["status"] == ("retired" if name == "STATUS_RETIRED" else "walkover")
    assert "score" not in result


def test_retirement_keeps_partial_source_score_without_inventing_set_winners():
    row = tennis(name="STATUS_RETIRED")
    for p, value in zip(final(row)["competitors"], [0, 5], strict=True):
        p["linescores"] = [{"value": value, "winner": False}]
    result = espn_result(row, "ATP", **PROOF)
    assert result["score"] == {"winner": [{"value": 5, "winner": False}], "runner_up": [{"value": 0, "winner": False}]}


def test_historical_champion_or_other_tour_cannot_supply_missing_current_final():
    assert espn_result(tennis("WTA"), "ATP", **PROOF) is None
    row = tennis()
    row["groupings"] = []
    assert espn_result(row, "ATP", **PROOF) is None


@pytest.mark.parametrize("league", ["NASCAR_CUP", "INDYCAR", "ATP", "WTA", "PGA_TOUR"])
@pytest.mark.parametrize("row", [{}, None, {"status": "bad", "groupings": [None]}, {"groupings": ["bad"]}])
def test_malformed_or_unsupported_optional_result_cannot_abort_publication(league, row):
    assert espn_result(row, league, **PROOF) is None


def test_final_without_any_supplied_score_preserves_confirmed_champion():
    row = tennis()
    for p in final(row)["competitors"]:
        p.pop("linescores")
    result = espn_result(row, "ATP", **PROOF)
    assert result["winner"]["name"] == "Champion"
    assert "score" not in result and result["_complete"] is True


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: final(r)["competitors"][0].pop("linescores"),
        lambda r: final(r)["competitors"][0]["linescores"].append({"value": 4}),
        lambda r: final(r)["competitors"][0]["linescores"][0].update(value=-1),
        lambda r: final(r)["competitors"][0]["linescores"][0].update(value=float("nan")),
        lambda r: final(r)["competitors"][0].update(linescores=[None]),
        lambda r: final(r)["competitors"][0]["linescores"][0].update(tiebreak=True),
        lambda r: final(r)["competitors"][0]["linescores"][0].update(winner="unknown"),
    ],
)
def test_partial_or_malformed_supplied_score_keeps_champion_but_stays_refreshable(mutation):
    row = tennis()
    mutation(row)
    result = espn_result(row, "ATP", **PROOF)
    assert result["winner"]["name"] == "Champion"
    assert result["runner_up"]["name"] == "Runner Up"
    assert result["_complete"] is False
    assert "score" not in result


def test_numeric_race_ranks_are_facts_even_when_source_has_no_winner_boolean():
    row = race()
    for competitor in row["competitions"][0]["competitors"]:
        competitor["winner"] = False
    assert espn_result(row, "NASCAR_CUP", **PROOF)["rows"][0]["name"] == "Winning Driver"


@pytest.mark.parametrize("identity", [None, "", " ", 123])
def test_racing_requires_an_explicit_source_event_identity(identity):
    row = race()
    row["id"] = row["competitions"][0]["id"] = identity
    assert espn_result(row, "NASCAR_CUP", **PROOF) is None


def test_racing_missing_both_source_ids_does_not_confirm_a_podium():
    row = race()
    row.pop("id")
    row["competitions"][0].pop("id")
    assert espn_result(row, "NASCAR_CUP", **PROOF) is None
