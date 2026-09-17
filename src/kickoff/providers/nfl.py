from __future__ import annotations

from datetime import date

from kickoff.models import ProviderOptions, ProviderRunResult
from kickoff.providers.base import Provider
from kickoff.settings import Settings


class NFLProvider(Provider):
    key = "nfl"
    league = "NFL"
    sport = "football"

    def fetch(self, season: int, settings: Settings, options: ProviderOptions) -> ProviderRunResult:
        warnings = []
        if date.today() <= date(season, 5, 15):
            warnings.append(
                f"{season} NFL regular-season dates are not published yet as of {date.today().isoformat()}."
            )
        else:
            warnings.append(
                "NFL provider is scaffolded but still intentionally conservative until the official schedule parser is validated."
            )

        return ProviderRunResult(
            provider_key=self.key,
            season=season,
            events=[],
            warnings=warnings,
            metadata={
                "status": "stubbed",
                "expected_source": f"https://www.nfl.com/schedules/{season}/by-week/reg-1",
                "semantics": {
                    "default_behavior": "No events emitted until the official NFL schedule is published and validated.",
                    "special_behavior": "Preseason and postseason are intentionally not modeled yet.",
                },
                "applied_options": options.to_dict(),
            },
        )
