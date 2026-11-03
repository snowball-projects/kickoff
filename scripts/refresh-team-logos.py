"""Refresh checked-in team-image URLs weekly from the published schedule cohorts."""

import argparse
from pathlib import Path

from kickoff.team_logo_refresh import BASE_URL, refresh_team_logos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=BASE_URL)
    args = parser.parse_args()
    config = Path(__file__).resolve().parents[1] / "src/kickoff/config"
    cohorts, logos = refresh_team_logos(config / "team_logos.json", config / "team_logo_receipts.json", args.base_url)
    print(f"Refreshed {cohorts} team cohorts; {logos} source-linked images")


if __name__ == "__main__":
    main()
