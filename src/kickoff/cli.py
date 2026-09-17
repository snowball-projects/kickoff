from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from kickoff.audit import audit_normalized_selection
from kickoff.dataset import load_events_from_json
from kickoff.registry import build_registry
from kickoff.settings import Settings
from kickoff.storage import write_run_outputs
from kickoff.validation import validate_batch
from kickoff.web import export_web_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kickoff")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch = subparsers.add_parser("fetch", help="Fetch raw data and write normalized outputs.")
    fetch.add_argument("provider", help="Provider key or 'all'.")
    fetch.add_argument("--season", type=int, default=None)
    fetch.add_argument(
        "--event-scope",
        choices=["regular_only", "all_published"],
        default=None,
        help="Filter postseason-like phases. Special and support events remain opt-in.",
    )
    fetch.add_argument(
        "--include-special-events",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Include exhibitions, preseason, qualifying, testing, and other special phases.",
    )
    fetch.add_argument(
        "--include-support-events",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Include support-series or support-event cards when a provider emits them.",
    )
    fetch.add_argument(
        "--motorsport-view",
        choices=["race_only", "full_weekend"],
        default=None,
        help="Publish races only (default) or every official main-series weekend session the source provides.",
    )

    validate = subparsers.add_parser("validate", help="Validate normalized outputs.")
    validate.add_argument("--season", type=int, default=None)

    audit = subparsers.add_parser("audit", help="Audit normalized provider outputs.")
    audit.add_argument("provider", help="Provider key or 'all'.")
    audit.add_argument("--season", type=int, default=None)

    export_web = subparsers.add_parser("export-web", help="Write a sanitized static bundle for the dashboard.")
    export_web.add_argument("--season", type=int, default=None)
    export_web.add_argument("--output-dir", type=Path, default=None)

    return parser


def _resolve_provider_keys(provider_arg: str, registry: dict[str, object]) -> list[str]:
    if provider_arg == "all":
        return list(registry.keys())
    if provider_arg not in registry:
        raise SystemExit(f"unknown provider: {provider_arg}")
    return [provider_arg]


def run_fetch(
    settings: Settings,
    provider_arg: str,
    season: int,
    *,
    event_scope: str | None,
    include_special_events: bool | None,
    include_support_events: bool | None,
    motorsport_view: str | None,
) -> int:
    registry = build_registry()
    provider_keys = _resolve_provider_keys(provider_arg, registry)

    provider_results = []
    for key in provider_keys:
        result = registry[key].fetch(
            season=season,
            settings=settings,
            options=settings.provider_options(
                key,
                event_scope=event_scope,
                include_special_events=include_special_events,
                include_support_events=include_support_events,
                motorsport_view=motorsport_view,
            ),
        )
        provider_results.append(result)

    merged_events = write_run_outputs(provider_results, settings, season)
    errors = validate_batch(merged_events)

    print(
        json.dumps(
            {
                "season": season,
                "providers": provider_keys,
                "provider_event_counts": {result.provider_key: len(result.events) for result in provider_results},
                "season_event_count": len(merged_events),
                "validation_errors": errors,
            },
            indent=2,
        )
    )
    return 1 if errors else 0


def run_validate(settings: Settings, season: int) -> int:
    target = settings.normalized_dir / str(season) / "all_events.json"
    if not target.exists():
        raise SystemExit(f"normalized file not found: {target}")
    events = load_events_from_json(target)
    errors = validate_batch(events)
    print(json.dumps({"season": season, "errors": errors}, indent=2))
    return 1 if errors else 0


def run_audit(settings: Settings, provider_arg: str, season: int) -> int:
    provider_keys = _resolve_provider_keys(provider_arg, build_registry())
    payload = audit_normalized_selection(settings, season, provider_keys)
    print(json.dumps(payload, indent=2))
    return 0


def run_export_web(settings: Settings, season: int, output_dir: Path | None) -> int:
    target = output_dir or settings.repo_root / "frontend" / "public" / "data"
    bundle_path = export_web_bundle(settings, season, target)
    print(json.dumps({"season": season, "bundle": str(bundle_path)}, indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    settings = Settings.load(Path.cwd())
    settings.ensure_directories()
    season = args.season or settings.default_season

    if args.command == "fetch":
        return run_fetch(
            settings,
            args.provider,
            season,
            event_scope=args.event_scope,
            include_special_events=args.include_special_events,
            include_support_events=args.include_support_events,
            motorsport_view=args.motorsport_view,
        )
    if args.command == "validate":
        return run_validate(settings, season)
    if args.command == "audit":
        return run_audit(settings, args.provider, season)
    if args.command == "export-web":
        return run_export_web(settings, season, args.output_dir)
    raise SystemExit("unsupported command")
