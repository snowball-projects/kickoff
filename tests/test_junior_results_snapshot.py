"""Validate the one-time reviewed Junior page snapshot without source requests."""

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = ROOT / "data/reviewed/receipts"


def snapshot():
    return json.loads((RECEIPTS / "2026-junior-results.json").read_text())


def athletes(data):
    return [row for session in data["sessions"] for row in session["athletes"]]


def test_snapshot_is_hash_bound_to_dated_reviewed_facts_without_inferred_end_times():
    data = snapshot()
    canonical = json.dumps(data["sessions"], sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(canonical).hexdigest() == data["sha256"]
    assert data["league"] == "IWF_JUNIOR_WORLDS" and data["year"] == 2026
    assert data["source_url"] == (
        "https://iwf.sport/results/results-by-events/results-by-events-2025-2026/?event_id=684"
    )
    assert data["checked_date"] == data["review_revision"] == "2026-11-04"
    assert data["finished_observed_at"] == "2026-11-04T04:25:07Z"
    assert "not an actual session end" in data["finished_observation_basis"]
    assert "not raw source" in data["hash_scope"]
    assert "No build-time IWF requests" in data["collection_method"] or (
        "no build-time IWF requests" in data["collection_method"]
    )
    assert all(not any(key in session for key in ["end_at", "end_date", "local_time"]) for session in data["sessions"])


def test_every_result_matches_its_reviewed_session_and_source_lot_without_filling_missing_entries():
    data = snapshot()
    start = json.loads((RECEIPTS / "2026-junior-start-list.json").read_text())
    calendar = {
        row["id"]: row
        for row in json.loads((ROOT / "data/reviewed/2026-weightlifting.json").read_text())["events"]
        if row["league"] == "IWF_JUNIOR_WORLDS"
    }
    start_sessions = {row["event_id"]: row for row in start["sessions"]}
    seen = set()
    assert data["session_count"] == len(data["sessions"]) == len(calendar) == 28
    for session in data["sessions"]:
        event_id = session["event_id"]
        assert session["categories"] == calendar[event_id]["categories"] == start_sessions[event_id]["categories"]
        starters = {row["lot"]: row for row in start_sessions[event_id]["entries"]}
        categories = {tuple(c[k] for k in ["gender", "weight_class", "group"]) for c in session["categories"]}
        assert session["athletes"]
        for row in session["athletes"]:
            assert row["lot"] not in seen
            seen.add(row["lot"])
            assert row["nation"] == starters[row["lot"]]["nation"]
            assert row["weight_class"] == starters[row["lot"]]["weight"]
            assert tuple(row[k] for k in ["gender", "weight_class", "group"]) in categories
    start_lots = {row["lot"] for s in start["sessions"] for row in s["entries"]}
    assert data["athlete_count"] == len(seen) == 261
    assert (
        start_lots - seen
        == set(data["start_lots_without_result"])
        == {"6", "35", "67", "69", "89", "96", "145", "184", "216", "250"}
    )
    assert not seen - start_lots


def test_explicit_six_attempts_preserve_unused_slots_and_agree_with_source_bests_and_totals():
    counts = Counter()
    for row in athletes(snapshot()):
        for lift in ["snatch", "clean_and_jerk"]:
            assert len(row[lift]) == 3
            for attempt in row[lift]:
                assert set(attempt) == {"weight_kg", "status"}
                assert attempt["status"] in {"made", "missed", "unused"}
                counts[attempt["status"]] += 1
                if attempt["status"] == "unused":
                    assert attempt["weight_kg"] is None
                else:
                    assert type(attempt["weight_kg"]) is int and attempt["weight_kg"] > 0
            made = [attempt["weight_kg"] for attempt in row[lift] if attempt["status"] == "made"]
            assert row[lift + "_best_kg"] == max(made, default=None)
        bests = [row["snatch_best_kg"], row["clean_and_jerk_best_kg"]]
        assert row["total_kg"] == (sum(bests) if None not in bests else None)
    assert counts == {"made": 951, "missed": 605, "unused": 10}
    assert sum(counts.values()) == 1566


def test_all_three_global_rank_tables_and_medals_cover_every_class_not_local_group_winners():
    classes = defaultdict(list)
    for row in athletes(snapshot()):
        classes[row["gender"], row["weight_class"]].append(row)
    assert len(classes) == 16
    for lift in ["snatch", "clean_and_jerk", "total"]:
        medals = Counter()
        for rows in classes.values():
            ranks = []
            for row in rows:
                rank = row[lift + "_rank"]
                best = row["total_kg" if lift == "total" else lift + "_best_kg"]
                assert (rank is None) == (best is None)
                if rank is not None:
                    assert type(rank) is int and rank > 0
                    ranks.append(rank)
                if rank in [1, 2, 3]:
                    assert row[lift + "_medal"] == {1: "gold", 2: "silver", 3: "bronze"}[rank]
                    medals[row[lift + "_medal"]] += 1
                else:
                    assert lift + "_medal" not in row
            assert sorted(ranks) == list(range(1, len(ranks) + 1))
        assert medals == {"gold": 16, "silver": 16, "bronze": 16}


def test_snapshot_contains_only_result_facts_and_literal_current_source_names():
    rows = athletes(snapshot())
    required = {
        "lot",
        "name",
        "nation",
        "gender",
        "weight_class",
        "group",
        "snatch",
        "clean_and_jerk",
        "snatch_best_kg",
        "clean_and_jerk_best_kg",
        "total_kg",
        "snatch_rank",
        "clean_and_jerk_rank",
        "total_rank",
    }
    for row in rows:
        assert required <= row.keys() <= required | {"snatch_medal", "clean_and_jerk_medal", "total_medal"}
    assert next(row for row in rows if row["lot"] == "180")["name"] == "TAGGART Zak William"
    assert next(row for row in rows if row["lot"] == "41")["name"] == "ABDELNABY A A M Fatma"
    encoded = json.dumps(rows)
    assert not any(field in encoded for field in ["dateOfBirth", "Born:", "bodyweight", "reader_link_ref", "athlete="])


def test_source_lot_identity_is_cited_separately_from_the_current_page_name():
    data = snapshot()
    assert data["identity_source"]["source_url"].endswith("2026-IWF-WJC_RESULTS-BOOK.pdf")
    assert data["identity_source"]["checked_date"] == "2026-11-04"
    assert "not raw PDF bytes" in data["identity_source"]["hash_scope"]
    assert "not extracted from the results page" in data["lot_identity_basis"]
    assert data["identity_name_variants"][0]["lot"] == "180"
    assert data["identity_name_variants"][0]["identity_source_name"] == "TAGGART Zak"
    assert data["identity_name_variants"][0]["result_source_name"] == "TAGGART Zak William"
