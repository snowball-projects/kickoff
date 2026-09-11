from __future__ import annotations

from abc import ABC, abstractmethod

from sportsbro.models import ProviderOptions, ProviderRunResult
from sportsbro.settings import Settings


class Provider(ABC):
    key: str
    league: str
    sport: str

    @abstractmethod
    def fetch(self, season: int, settings: Settings, options: ProviderOptions) -> ProviderRunResult:
        raise NotImplementedError

    def season_label(self, season: int) -> str:
        return str(season)
