"""Fetch schedules into generated static assets; never commit data back to Git."""

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from kickoff.feeds import FEEDS
from kickoff.open_schedules import read_optional, read_url, refresh_open_schedules

LIVE_DATA = "https://snowball-projects.github.io/kickoff/data/"


def refresh(years: list[int], output: Path, reviewed: Path, warnings: list[str]) -> None:
    previous, errors = {}, {}
    # The browser's export contract is data/<calendar year>.json. New deployments
    # also export index.json; older deployments may only advertise years in bundles.
    advertised = set(years)
    try:
        body = read_optional(LIVE_DATA + "index.json")
        if body is not None:
            index = json.loads(body)
            if index["schema_version"] != "1" or not all(type(y) is int for y in index["available_seasons"]):
                raise ValueError("Invalid live index")
            advertised.update(index["available_seasons"])
    except Exception:
        # Year bundles advertise their own available_seasons, so an unavailable
        # index does not prevent independent feed recovery.
        pass
    pending = set(advertised)
    while pending:
        year = pending.pop()
        try:
            bundle = json.loads(read_url(LIVE_DATA + f"{year}.json"))
            if bundle["schema_version"] != "1" or bundle["season"] != year or not isinstance(bundle["events"], list):
                raise ValueError("Invalid live year bundle")
            if not all(type(y) is int for y in bundle["available_seasons"]):
                raise ValueError("Invalid live available_seasons")
            previous[year] = bundle
            for other in bundle["available_seasons"]:
                if other not in advertised:
                    pending.add(other)
                    advertised.add(other)
        except Exception as error:
            errors[year] = f"{LIVE_DATA}{year}.json: {error}"
    with TemporaryDirectory(prefix="kickoff-") as temp:
        stage = Path(temp)
        failed = []
        for year in sorted(advertised):
            if year in years:
                try:
                    refresh_open_schedules(
                        year,
                        stage / "data",
                        reviewed,
                        feeds=FEEDS,
                        warnings=warnings,
                        previous=previous.get(year),
                        previous_error=errors.get(year),
                        published_inputs={
                            row.get("url") or row.get("source_url") or ""
                            for bundle in previous.values()
                            for row in bundle.get("input_evidence", []) + bundle["events"]
                        },
                    )
                except Exception as error:
                    failed.append(f"{year}: {error}")
            else:
                # Keep other advertised years and licensed components intact.
                try:
                    bundle = previous[year]
                    (stage / "data").mkdir(exist_ok=True)
                    for component in bundle.get("components", []):
                        name = component["path"]
                        if Path(name).name != name or not name.endswith(".json"):
                            raise ValueError("Invalid live component path")
                        body = read_url(LIVE_DATA + name)
                        if hashlib.sha256(body).hexdigest() != component["sha256"]:
                            raise ValueError(f"Live component hash mismatch: {name}")
                        (stage / "data" / name).write_bytes(body)
                    (stage / "data" / f"{year}.json").write_text(json.dumps(bundle))
                except Exception as error:
                    failed.append(f"Cannot preserve live {year}: {errors.get(year, error)}")
        if failed:
            raise ValueError("\n".join(failed))
        available = sorted(advertised)
        for year in available:
            path = stage / "data" / f"{year}.json"
            bundle = json.loads(path.read_text())
            bundle["available_seasons"] = available
            path.write_text(json.dumps(bundle, ensure_ascii=True, separators=(",", ":")) + "\n")
        (stage / "data" / "index.json").write_text(json.dumps({"schema_version": "1", "available_seasons": available}))
        output.mkdir(parents=True, exist_ok=True)
        for path in output.glob("*.json"):
            path.unlink()
        shutil.copytree(stage / "data", output, dirs_exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--year", type=int, action="append", help="Calendar year; repeatable. Default: this year and next"
    )
    parser.add_argument("--warnings", type=Path, help="Write failed feed details for the post-deployment workflow step")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    year = datetime.now(timezone.utc).year
    warnings: list[str] = []
    try:
        refresh(args.year or [year, year + 1], root / "frontend/public/data", root / "data/reviewed", warnings)
        for name in ["LICENSE", "THIRD-PARTY-NOTICES.md"]:
            shutil.copyfile(root / name, root / "frontend/public" / name)
    finally:
        for warning in warnings:
            print(f"warning: {warning}")
        if args.warnings:
            args.warnings.write_text("".join(f"- {warning}\n" for warning in warnings))


if __name__ == "__main__":
    main()
