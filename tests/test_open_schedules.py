from sportsbro.open_schedules import f1_events, football_events


def test_football_keeps_unzoned_times_unknown_and_stable_identity():
    match = {"date": "2026-09-12", "time": "15:00", "team1": "Home", "team2": "Away", "round": "Matchday 1"}
    first = football_events({"matches": [match]}, "en.1", "2026-27", "https://example.org")[0]
    moved = football_events({"matches": [{**match, "date": "2026-09-13"}]}, "en.1", "2026-27", "https://example.org")[0]
    assert first.start_time_utc is None
    assert first.calendar_date == "2026-09-12"
    assert first.event_id == moved.event_id


def test_football_accepts_both_recorded_score_shapes():
    match = {"date": "2026-09-12", "team1": "Home", "team2": "Away"}
    for score in [{"ft": [0, 0]}, [0, 0]]:
        event = football_events({"matches": [{**match, "score": score}]}, "en.1", "2026-27", "https://example.org")[0]
        assert event.status == "finished"


def test_f1_preserves_saturday_race_and_utc_session_times():
    text = "id: 1164\nround: 15\ndate: 2026-09-26\ntime: 11:00\ngrandPrixId: azerbaijan\nqualifyingDate: 2026-09-25\nqualifyingTime: 12:00\n"
    events = f1_events(text, 2026, "https://example.org")
    assert len(events) == 2
    assert events[0].start_time_utc == "2026-09-26T11:00:00Z"
    assert events[1].event_type == "qualifying"
    assert events[1].calendar_date == "2026-09-25"


def test_football_withholds_postponed_and_canceled_dates_and_classifies_playoffs():
    match = {"date": "2026-05-10", "team1": "Home", "team2": "Away", "round": "Playoffs"}
    rows = [{**match, "status": status} for status in ("canceled", "postponed", "cancelled")]
    assert football_events({"matches": rows}, "en.2", "2025-26", "https://example.org") == []
    event = football_events({"matches": [match]}, "en.2", "2025-26", "https://example.org")[0]
    assert event.competition_phase == "postseason"
    assert event.is_postseason and not event.is_regular_season
