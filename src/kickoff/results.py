"""Attach already-validated optional source result facts to a schedule event."""

from copy import deepcopy

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


def same_result_scope(event: CalendarEvent | dict, previous: dict) -> bool:
    """Identity and source scope must match before reusing an optional result."""
    return all(
        (event.get(key) if isinstance(event, dict) else getattr(event, key)) == previous.get(key)
        for key in (
            "event_id",
            "source",
            "sport",
            "league",
            "season",
            "event_type",
            "title",
            "round_or_stage",
            "source_url",
            "calendar_date",
            "end_calendar_date",
        )
    ) and sorted(event.get("tags", []) if isinstance(event, dict) else event.tags) == sorted(previous.get("tags", []))


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
                    "sha256",
                    "hash_scope",
                    "membership_source",
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
