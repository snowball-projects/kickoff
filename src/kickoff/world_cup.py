"""CC0 openfootball World Cup fixtures, with separately reviewed host facts."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from kickoff.models import CalendarEvent, Participant
from kickoff.normalize import stable_event_id
from kickoff.semantics import classification_fields
from kickoff.timeutils import isoformat_z

SOURCE = {
    "kind": "openfootball",
    "name": "openfootball contributors",
    "url": "https://github.com/openfootball/worldcup.json",
    "license": "CC0 1.0",
    "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
    "changes": "Normalized fixtures, explicit UTC offsets, phases and final scores; national-team flag identities added.",
}
# FIFA lists the 16 host cities/stadiums under their three countries. The
# parenthesized municipalities below retain openfootball's exact ground names.
HOST_SOURCE = "https://www.fifa.com/en/articles/fifa-world-cup-2026-hosts-cities-dates-usa-mexico-canada"
HOST_CHECKED = "2026-10-31"
HOST_COUNTRIES = {
    "Toronto": "CA",
    "Vancouver": "CA",
    "Mexico City": "MX",
    "Guadalajara (Zapopan)": "MX",
    "Monterrey (Guadalupe)": "MX",
    "Atlanta": "US",
    "Boston (Foxborough)": "US",
    "Dallas (Arlington)": "US",
    "Houston": "US",
    "Kansas City": "US",
    "Los Angeles (Inglewood)": "US",
    "Miami (Miami Gardens)": "US",
    "New York/New Jersey (East Rutherford)": "US",
    "Philadelphia": "US",
    "San Francisco Bay Area (Santa Clara)": "US",
    "Seattle": "US",
}
TEAM_COUNTRIES = {
    "Algeria": "DZ",
    "Argentina": "AR",
    "Australia": "AU",
    "Austria": "AT",
    "Belgium": "BE",
    "Bosnia & Herzegovina": "BA",
    "Brazil": "BR",
    "Canada": "CA",
    "Cape Verde": "CV",
    "Colombia": "CO",
    "Croatia": "HR",
    "Curaçao": "CW",
    "Czech Republic": "CZ",
    "DR Congo": "CD",
    "Ecuador": "EC",
    "Egypt": "EG",
    "England": "GB-ENG",
    "France": "FR",
    "Germany": "DE",
    "Ghana": "GH",
    "Haiti": "HT",
    "Iran": "IR",
    "Iraq": "IQ",
    "Ivory Coast": "CI",
    "Japan": "JP",
    "Jordan": "JO",
    "Mexico": "MX",
    "Morocco": "MA",
    "Netherlands": "NL",
    "New Zealand": "NZ",
    "Norway": "NO",
    "Panama": "PA",
    "Paraguay": "PY",
    "Portugal": "PT",
    "Qatar": "QA",
    "Saudi Arabia": "SA",
    "Scotland": "GB-SCT",
    "Senegal": "SN",
    "South Africa": "ZA",
    "South Korea": "KR",
    "Spain": "ES",
    "Sweden": "SE",
    "Switzerland": "CH",
    "Tunisia": "TN",
    "Turkey": "TR",
    "USA": "US",
    "Uruguay": "UY",
    "Uzbekistan": "UZ",
}
KNOCKOUT_ROUNDS = {"Round of 32", "Round of 16", "Quarter-final", "Semi-final", "Match for third place", "Final"}


def world_cup_events(payload: dict, year: int, source_url: str) -> list[CalendarEvent]:
    rows = payload.get("matches")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Missing World Cup matches")
    checked = datetime.now(timezone.utc).date().isoformat()
    events = []
    for row in rows:
        group, stage = row.get("group"), row.get("round")
        if group and re.fullmatch(r"Group [A-L]", group):
            phase = "regular_season"
        elif not group and stage in KNOCKOUT_ROUNDS:
            phase = "postseason"
        else:
            raise ValueError(f"Unknown World Cup phase: {group or stage}")
        clock = re.fullmatch(r"(\d{2}:\d{2}) UTC([+-])(\d{1,2})(?::(\d{2}))?", row.get("time") or "")
        if not clock:
            raise ValueError("World Cup clock needs an explicit UTC offset")
        time, sign, hours, minutes = clock.groups()
        if int(minutes or 0) >= 60:
            raise ValueError("Invalid World Cup UTC offset minutes")
        delta = timedelta(hours=int(hours), minutes=int(minutes or 0))
        local = datetime.fromisoformat(f"{row['date']}T{time}").replace(
            tzinfo=timezone(delta if sign == "+" else -delta)
        )
        if local.year != year:
            raise ValueError("Unexpected World Cup year")
        ground = row["ground"]
        country = HOST_COUNTRIES[ground]
        score = row.get("score") or {}
        # Extra-time totals are the final on-field score. Shootouts are separate.
        final = score.get("et", score.get("ft"))
        finished = isinstance(final, list) and len(final) == 2 and all(type(n) is int and n >= 0 for n in final)
        if score and not finished:
            raise ValueError("Invalid World Cup final score")
        participants = [
            Participant(
                name=row[key],
                role=role,
                entity_type="national_team",
                metadata={"country_code": TEAM_COUNTRIES[row[key]]},
                final_score=final[index] if finished else None,
            )
            for index, (key, role) in enumerate((("team1", "home"), ("team2", "away")))
        ]
        label = group or stage
        penalties = score.get("p")
        if penalties:
            if not finished or len(penalties) != 2 or any(type(n) is not int or n < 0 for n in penalties):
                raise ValueError("Invalid World Cup shootout score")
            label += f" · Penalties {penalties[0]}-{penalties[1]}"
        events.append(
            CalendarEvent(
                event_id=stable_event_id(
                    "openfootball", "worldcup", year, row.get("num") or (group, stage, row["team1"], row["team2"])
                ),
                source="openfootball",
                sport="soccer",
                league="FIFA_WORLD_CUP",
                season=str(year),
                event_type="game",
                title=f"{row['team1']} vs {row['team2']}",
                subtitle=label,
                start_time_utc=isoformat_z(local),
                start_time_local=local.isoformat(),
                timezone=local.tzname(),
                status="finished" if finished else "scheduled",
                venue=ground,
                city=None,
                region=None,
                country=country,
                participants=participants,
                home_participant=participants[0],
                away_participant=participants[1],
                round_or_stage=group or stage,
                calendar_date=row["date"],
                end_calendar_date=row["date"],
                source_url=source_url,
                country_source_url=HOST_SOURCE,
                country_checked_date=HOST_CHECKED,
                facts_source_url=source_url,
                facts_checked_date=checked,
                tags=["football"],
                **classification_fields(phase),
            )
        )
    return events
