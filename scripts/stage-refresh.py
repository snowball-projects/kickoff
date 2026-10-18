"""Push validated published schedules to a new review branch, never main."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from urllib.parse import quote


def git(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], check=check, capture_output=True, text=True)


def stage_refresh() -> None:
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not re.fullmatch(r"[0-9]+", run_id) or not re.fullmatch(r"[0-9]+", attempt):
        raise ValueError("A numeric GitHub run ID and attempt are required.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("A GitHub owner/repository name is required.")
    if git("branch", "--show-current").stdout.strip() != "main":
        raise ValueError("Refresh review branches must start from the checked-out main branch.")
    if git("diff", "--cached", "--quiet", check=False).returncode:
        raise ValueError("The index must be empty before staging published schedules.")

    git("add", "--", "data/published")
    changes = git("diff", "--cached", "--quiet", check=False)
    if changes.returncode == 0:
        print("No published schedule changes; no review branch created.")
        return
    if changes.returncode != 1:
        changes.check_returncode()

    branch = f"automation/schedules-{run_id}-{attempt}"
    existing = git("ls-remote", "--heads", "origin", f"refs/heads/{branch}")
    if existing.stdout.strip():
        raise ValueError(f"Review branch {branch} already exists; refusing to overwrite it.")
    git("switch", "-c", branch)
    git(
        "-c",
        "user.name=github-actions[bot]",
        "-c",
        "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit",
        "-m",
        "Refresh published schedules",
    )
    git("push", "origin", f"HEAD:refs/heads/{branch}")
    commit = git("rev-parse", "HEAD").stdout.strip()
    compare = f"https://github.com/{repository}/compare/main...{quote(branch, safe='')}?expand=1"
    message = (
        "## Published schedule update ready for review\n\n"
        f"Branch: `{branch}`\n\nCommit: `{commit}`\n\n"
        f"[Open a pull request]({compare}) against `main`. Review the data changes, "
        "wait for required CI checks, then merge to publish. The live calendar is unchanged until merge.\n\n"
        "Open the PR with your own account so its normal pull-request checks run.\n"
    )
    print(message)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as output:
            output.write(message)


if __name__ == "__main__":
    try:
        stage_refresh()
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.stderr.strip() or str(error)) from error
