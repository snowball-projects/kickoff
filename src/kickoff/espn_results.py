"""Confirmed individual-event results from already-fetched ESPN scoreboards."""

from __future__ import annotations

import math

TENNIS_SINGLES = {"ATP": ("mens-singles", "1"), "WTA": ("womens-singles", "2")}
TENNIS_FINAL_STATES = {"STATUS_FINAL": "final", "STATUS_RETIRED": "retired", "STATUS_WALKOVER": "walkover"}


def _completed(item: dict, names: set[str] | dict[str, str]) -> bool:
    status = (item.get("status") or {}).get("type") or {}
    return status.get("completed") is True and status.get("state") == "post" and status.get("name") in names


def _integer(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if not math.isfinite(value) or value < 0 or int(value) != value:
        return None
    return int(value)


def _athlete(competitor: dict) -> dict | None:
    if competitor.get("type") != "athlete":
        return None
    athlete = competitor.get("athlete") or {}
    name = athlete.get("fullName") or athlete.get("displayName")
    identity = competitor.get("id")
    if not isinstance(name, str) or not name.strip() or name.strip().upper() in {"TBD", "TBA", "TO BE DETERMINED"}:
        return None
    if not isinstance(identity, str) or not identity.strip():
        return None
    if athlete.get("id") is not None and str(athlete["id"]) != identity:
        return None
    return {"name": name, "participant_id": identity}


def _podium(row: dict) -> dict | None:
    competitions = row.get("competitions") or []
    event_id = row.get("id")
    if not isinstance(event_id, str) or not event_id.strip():
        return None
    if not _completed(row, {"STATUS_FINAL"}) or len(competitions) != 1:
        return None
    competition = competitions[0]
    if not _completed(competition, {"STATUS_FINAL"}) or competition.get("id") != row.get("id"):
        return None
    podium = {}
    for competitor in competition.get("competitors") or []:
        rank = _integer(competitor.get("order"))
        # `order` is the source finishing rank. Unranked starters can precede it.
        if competitor.get("winner") is True and rank != 1:
            return None
        if rank not in {1, 2, 3}:
            continue
        athlete = _athlete(competitor)
        if athlete is None or rank in podium:
            return None
        podium[rank] = {"rank": rank, **athlete}
    if set(podium) != {1, 2, 3} or len({p["participant_id"] for p in podium.values()}) != 3:
        return None
    return {"kind": "podium", "rows": [podium[rank] for rank in (1, 2, 3)], "_complete": True}


def _singles(kind: dict, slug: str, identity: str) -> bool:
    return kind.get("slug") == slug and str(kind.get("id", identity)) == identity


def _sets(competitor: dict) -> list[dict] | None:
    rows = competitor.get("linescores")
    if not isinstance(rows, list) or not rows:
        return None
    result = []
    for row in rows:
        if not isinstance(row, dict):
            return None
        value = _integer(row.get("value"))
        if value is None:
            return None
        item = {"value": value}
        if "tiebreak" in row:
            tiebreak = _integer(row["tiebreak"])
            if tiebreak is None:
                return None
            item["tiebreak"] = tiebreak
        if "winner" in row:
            if not isinstance(row["winner"], bool):
                return None
            item["winner"] = row["winner"]
        result.append(item)
    return result


def _tennis_final(row: dict, league: str) -> dict | None:
    slug, identity = TENNIS_SINGLES[league]
    finals = [
        competition
        for group in row.get("groupings") or []
        if _singles(group.get("grouping") or {}, slug, identity)
        for competition in group.get("competitions") or []
        if (competition.get("round") or {}).get("displayName") == "Final"
    ]
    if len(finals) != 1:
        return None
    final = finals[0]
    if (
        not _singles(final.get("type") or {}, slug, identity)
        or str((final.get("round") or {}).get("id", "7")) != "7"
        or not _completed(final, TENNIS_FINAL_STATES)
    ):
        return None
    competitors = final.get("competitors") or []
    if len(competitors) != 2 or sum(p.get("winner") is True for p in competitors) != 1:
        return None
    winner = next(p for p in competitors if p.get("winner") is True)
    runner_up = next(p for p in competitors if p is not winner)
    # Both flags are explicit; an absent/unknown loser is not a confirmed final.
    if runner_up.get("winner") is not False:
        return None
    players = [_athlete(winner), _athlete(runner_up)]
    if None in players or players[0]["participant_id"] == players[1]["participant_id"]:
        return None
    status = TENNIS_FINAL_STATES[final["status"]["type"]["name"]]
    score = {"winner": _sets(winner), "runner_up": _sets(runner_up)}
    complete_score = all(score.values()) and len(score["winner"]) == len(score["runner_up"])
    supplied_score = any(p.get("linescores") not in (None, []) for p in competitors)
    result = {
        "kind": "tennis-final",
        "winner": players[0],
        "runner_up": players[1],
        "status": status,
        "_complete": bool(complete_score) or not supplied_score,
    }
    if complete_score:
        result["score"] = score
    return result


def espn_result(row: dict, league: str, *, source_url: str, checked_date: str) -> dict | None:
    """Return only a confirmed podium or the selected tour's singles final.

    No I/O, dates inferred from schedules, historical previousWinners, or country
    guesses. Tennis final status is authoritative even if the tournament's aggregate
    status is stale or describes other groups. Absent scores never erase a confirmed
    champion. Supplied but unparseable scores set the internal `_complete` marker
    false so the caller can keep the event refreshable; this marker is not a public
    result fact. Retirement/walkover may legitimately have no score. Provenance
    comes from the caller's actual fetched body, not a synthetic event projection.
    """
    try:
        if league in {"NASCAR_CUP", "INDYCAR"}:
            result = _podium(row)
        elif league in TENNIS_SINGLES:
            result = _tennis_final(row, league)
        else:
            return None
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        # Optional external result facts must not abort schedule publication.
        return None
    if result is not None:
        result.update(source_url=source_url, checked_date=checked_date)
    return result
