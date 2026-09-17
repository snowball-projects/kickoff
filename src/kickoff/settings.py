from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from kickoff import __version__
from kickoff.models import ProviderOptions


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(slots=True)
class Settings:
    repo_root: Path
    data_dir: Path
    raw_dir: Path
    normalized_dir: Path
    config_dir: Path
    providers_config: dict[str, dict[str, object]]
    timeout_seconds: float
    user_agent: str
    default_season: int

    @classmethod
    def load(cls, repo_root: Path | None = None) -> "Settings":
        resolved_root = repo_root or Path.cwd()
        _load_env_file(resolved_root / ".env")
        data_dir = resolved_root / os.environ.get("KICKOFF_DATA_DIR", "data")
        config_dir = resolved_root / "config"
        if not (config_dir / "leagues.json").exists():
            config_dir = Path(__file__).resolve().parent / "config"
        providers_config = {}
        leagues_path = config_dir / "leagues.json"
        if leagues_path.exists():
            providers_config = json.loads(leagues_path.read_text(encoding="utf-8")).get("providers", {})
        return cls(
            repo_root=resolved_root,
            data_dir=data_dir,
            raw_dir=data_dir / "raw",
            normalized_dir=data_dir / "normalized",
            config_dir=config_dir,
            providers_config=providers_config,
            timeout_seconds=float(os.environ.get("KICKOFF_HTTP_TIMEOUT_SECONDS", "20")),
            user_agent=os.environ.get("KICKOFF_USER_AGENT", f"kickoff/{__version__}"),
            default_season=int(os.environ.get("KICKOFF_DEFAULT_SEASON", "2026")),
        )

    def ensure_directories(self) -> None:
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.normalized_dir.mkdir(parents=True, exist_ok=True)

    def provider_options(
        self,
        provider_key: str,
        *,
        event_scope: str | None = None,
        include_special_events: bool | None = None,
        include_support_events: bool | None = None,
        motorsport_view: str | None = None,
    ) -> ProviderOptions:
        provider_config = self.providers_config.get(provider_key, {})
        return ProviderOptions(
            event_scope=event_scope or str(provider_config.get("default_event_scope", "regular_only")),
            include_special_events=(
                include_special_events
                if include_special_events is not None
                else bool(provider_config.get("default_include_special_events", False))
            ),
            include_support_events=(
                include_support_events
                if include_support_events is not None
                else bool(provider_config.get("default_include_support_events", False))
            ),
            motorsport_view=motorsport_view or str(provider_config.get("default_motorsport_view", "race_only")),
        )
