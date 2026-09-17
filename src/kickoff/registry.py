from __future__ import annotations

from kickoff.providers.base import Provider
from kickoff.providers.f1 import F1Provider
from kickoff.providers.indycar import IndyCarProvider
from kickoff.providers.mlb import MLBProvider
from kickoff.providers.nascar_cup import NascarCupProvider
from kickoff.providers.nba import NBAProvider
from kickoff.providers.nfl import NFLProvider
from kickoff.providers.nhl import NHLProvider
from kickoff.providers.static_csv import StaticScheduleProvider


def build_registry() -> dict[str, Provider]:
    providers: list[Provider] = [
        NFLProvider(),
        NBAProvider(),
        MLBProvider(),
        NHLProvider(),
        F1Provider(),
        NascarCupProvider(),
        IndyCarProvider(),
        StaticScheduleProvider("fifa_world_cup", "FIFA_WORLD_CUP", "soccer", "reference_csv_fixture_download"),
        StaticScheduleProvider(
            "uefa_champions_league", "UEFA_CHAMPIONS_LEAGUE", "soccer", "reference_csv_fixture_download"
        ),
        StaticScheduleProvider("ifsc", "IFSC_WORLD_CUP", "climbing", "reference_csv_official_calendar"),
        StaticScheduleProvider("pga_tour", "PGA_TOUR", "golf", "reference_csv_official_schedule"),
    ]
    return {provider.key: provider for provider in providers}
