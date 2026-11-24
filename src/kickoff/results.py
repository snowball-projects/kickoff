"""Attach already-validated optional source result facts to a schedule event."""

from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo

from kickoff.models import CalendarEvent
from kickoff.weightlifting_startlists import catalog

WEIGHTLIFTING_FIELDS = {
    "lot",
    "name",
    "nation",
    "gender",
    "weight_class",
    "group",
    "guest",
    "total_rank",
    "total_kg",
    "snatch",
    "clean_and_jerk",
    "snatch_best_kg",
    "clean_and_jerk_best_kg",
    "snatch_rank",
    "clean_and_jerk_rank",
    "rank",
    "weight_kg",
    "source_article_url",
}


def attach_result(event: CalendarEvent, result: dict | None) -> None:
    if result is None:
        return
    if result["kind"] == "weightlifting":
        countries = catalog()["country_codes"]

        def public_athlete(source):
            athlete = {key: deepcopy(value) for key, value in source.items() if key in WEIGHTLIFTING_FIELDS}
            country = countries.get(athlete.get("nation", "").upper())
            if country:
                athlete.update(
                    country_code=country["code"],
                    country_source_url=country["source_url"],
                    country_checked_date=country["checked_date"],
                )
            return athlete

        event.result = {
            **{
                key: deepcopy(result[key])
                for key in (
                    "kind",
                    "source_url",
                    "checked_date",
                    "sources",
                    "revision",
                    "review_revision",
                )
                if key in result
            },
            "athletes": [public_athlete(athlete) for athlete in result["athletes"]],
            **{
                key: [public_athlete(athlete) for athlete in result[key]]
                for key in ("total_medalists", "snatch_medalists", "clean_and_jerk_medalists")
                if key in result
            },
        }
    else:
        event.result = {key: deepcopy(value) for key, value in result.items() if not key.startswith("_")}
    event.result_complete = result.get("_complete", result.get("complete", True))
    event.result["complete"] = event.result_complete
    if result["kind"] == "weightlifting":
        event.participants = []
        event.home_participant = event.away_participant = None
    # Every supported parser requires an actual final/result classification.
    # Incomplete ancillary facts keep the record refreshable independently.
    event.status = "finished"


def allocate_weightlifting_medals(events: list[dict], sessions: list[dict]) -> list[dict]:
    """Allocate global-class medals to the last reviewed session, without refetching results."""

    def scope(category):
        return category["gender"], category["weight_class"].removesuffix(" kg").replace(">", "+").strip()

    definitions = {row["id"]: row for row in sessions}
    by_class = {}
    for row in sessions:
        for category in row.get("categories", []):
            key = row["league"], row["start_date"][:4], *scope(category)
            by_class.setdefault(key, {})[row["id"]] = row
    deciding = {}

    def medal_session(row, key):
        return any(
            scope(category) == key[2:] and category.get("group") in {None, "A"}
            for category in row.get("categories", [])
        )

    for key, peers in by_class.items():
        if len(peers) == 1:
            event_id, row = next(iter(peers.items()))
            if medal_session(row, key):
                deciding[key] = event_id
            continue
        # Lower groups never award medals. Withhold a contradictory A-session allocation
        # if the reviewed timetable schedules another group after it.
        if not all(row.get("local_time") and row.get("event_timezone") for row in peers.values()):
            continue
        starts = {
            event_id: datetime.fromisoformat(f"{row['start_date']}T{row['local_time']}").replace(
                tzinfo=ZoneInfo(row["event_timezone"])
            )
            for event_id, row in peers.items()
        }
        last = max(starts.values())
        winners = [event_id for event_id, start in starts.items() if start == last]
        if len(winners) == 1 and medal_session(peers[winners[0]], key):
            deciding[key] = winners[0]
    output = []
    for event in events:
        if (event.get("result") or {}).get("kind") != "weightlifting":
            output.append(event)
            continue
        result = deepcopy(event["result"])
        row = definitions.get(event["event_id"])
        result["medal_classes"] = []
        result["mixed_classes"] = False
        if row is not None:
            classes = {scope(category) for category in row.get("categories", [])}
            result["mixed_classes"] = len(classes) > 1
            result["medal_classes"] = [
                {"gender": gender, "weight_class": weight}
                for gender, weight in sorted(classes)
                if deciding.get((row["league"], row["start_date"][:4], gender, weight)) == row["id"]
            ]
            result["allocation_source"] = {"source_url": row["source_url"], "checked_date": row["checked_date"]}
        output.append({**event, "result": result})
    return output
