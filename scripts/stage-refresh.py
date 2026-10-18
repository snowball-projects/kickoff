"""Coordinate one reusable, checked refresh PR without direct main pushes."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from urllib.parse import quote

BRANCH = "automation/schedule-refresh"
IDENTITY = [
    "-c",
    "user.name=github-actions[bot]",
    "-c",
    "user.email=41898282+github-actions[bot]@users.noreply.github.com",
]


def git(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], check=check, capture_output=True, text=True)


def api(path: str, method: str = "GET", payload: dict | None = None):
    command = ["gh", "api", path]
    if method != "GET":
        command.extend(["--method", method, "--input", "-"])
    result = subprocess.run(
        command,
        input=json.dumps(payload) if payload is not None else None,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else None


def repository() -> str:
    name = os.environ.get("GITHUB_REPOSITORY", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name):
        raise ValueError("A GitHub owner/repository name is required.")
    return f"repos/{name}"


def data_changes() -> list[str]:
    paths = git("diff", "--name-only", "origin/main", "HEAD").stdout.splitlines()
    if any(not path.startswith("data/published/") for path in paths):
        raise ValueError("The refresh branch has non-published-data changes; refusing automatic publication.")
    return paths


def prepare() -> None:
    if git("branch", "--show-current").stdout.strip() != "main":
        raise ValueError("Preparation must start on main.")
    if git("status", "--porcelain", "--untracked-files=no").stdout:
        raise ValueError("Preparation requires a clean tracked working tree and index.")
    git("fetch", "origin", "main")
    remote = git("ls-remote", "--heads", "origin", f"refs/heads/{BRANCH}").stdout.strip()
    if remote:
        git("fetch", "origin", BRANCH)
        git("switch", "-c", BRANCH, "FETCH_HEAD")
        git(*IDENTITY, "merge", "--no-edit", "origin/main")
    else:
        git("switch", "-c", BRANCH, "origin/main")
    data_changes()


def wait_for_ci(repo: str, head: str, previous: set[int]) -> None:
    path = f"{repo}/actions/workflows/ci.yml/runs?event=workflow_dispatch&head_sha={head}&per_page=30"
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        runs = api(path)["workflow_runs"]
        matching = [
            r
            for r in runs
            if r["id"] not in previous
            and r["head_sha"] == head
            and r["event"] == "workflow_dispatch"
            and r["head_branch"] == BRANCH
        ]
        if matching:
            run = max(matching, key=lambda item: item["id"])
            if run["status"] == "completed":
                if run["conclusion"] != "success":
                    raise RuntimeError(f"Dispatched CI did not pass: {run['html_url']}")
                print(f"Dispatched CI passed: {run['html_url']}", flush=True)
                return
        time.sleep(10)
    raise TimeoutError("Dispatched CI did not complete within ten minutes; no merge attempted.")


def publish(*, verify_only: bool = False) -> None:
    repo = repository()
    if git("branch", "--show-current").stdout.strip() != BRANCH:
        raise ValueError("Publication must use the prepared refresh branch.")
    if git("diff", "--cached", "--quiet", check=False).returncode:
        raise ValueError("The index must be empty before staging schedules.")
    git("add", "--", "data/published")
    staged = git("diff", "--cached", "--quiet", check=False)
    if staged.returncode == 1:
        git(*IDENTITY, "commit", "-m", "Refresh published schedules")
    elif staged.returncode != 0:
        staged.check_returncode()
    if not data_changes():
        print("No pending published schedule changes; no PR or publication needed.")
        return
    git("push", "origin", f"HEAD:refs/heads/{BRANCH}")
    head = git("rev-parse", "HEAD").stdout.strip()
    base = git("rev-parse", "origin/main").stdout.strip()
    owner = repo.split("/")[1]
    prs = api(f"{repo}/pulls?state=open&base=main&head={quote(f'{owner}:{BRANCH}', safe='')}")
    if len(prs) > 1:
        raise RuntimeError("More than one refresh PR exists; no merge attempted.")
    pr = (
        prs[0]
        if prs
        else api(
            f"{repo}/pulls",
            "POST",
            {
                "title": "Refresh published schedules",
                "base": "main",
                "head": BRANCH,
                "body": "Automated validated schedule update. Publication waits for dispatched CI and normal branch rules.",
            },
        )
    )
    number = pr["number"]
    runs_path = f"{repo}/actions/workflows/ci.yml/runs?event=workflow_dispatch&head_sha={head}&per_page=30"
    previous = {r["id"] for r in api(runs_path)["workflow_runs"]}
    api(
        f"{repo}/actions/workflows/ci.yml/dispatches",
        "POST",
        {
            "ref": BRANCH,
            "inputs": {"base_sha": base, "expected_head": head},
        },
    )
    print(f"Dispatched CI for PR #{number} at {head}; waiting for that new run.", flush=True)
    wait_for_ci(repo, head, previous)
    current = api(f"{repo}/pulls/{number}")
    if current["head"]["sha"] != head or current["base"]["sha"] != base:
        raise RuntimeError("PR head or main changed during CI; no merge attempted. The next refresh can retry.")
    if current["state"] != "open" or current.get("draft") or current["mergeable_state"] != "clean":
        raise RuntimeError("GitHub does not report the refresh PR mergeable; no approval or bypass will be attempted.")
    if verify_only:
        print(f"Rehearsal passed for PR #{number} at {head}; no merge or Pages dispatch.")
        return
    merged = api(f"{repo}/pulls/{number}/merge", "PUT", {"sha": head, "merge_method": "merge"})
    if not merged.get("merged"):
        raise RuntimeError("GitHub refused the normal checked merge; no publication dispatched.")
    # GITHUB_TOKEN merges do not trigger push workflows; dispatch publication explicitly.
    api(f"{repo}/actions/workflows/pages.yml/dispatches", "POST", {"ref": "main"})
    print(f"Merged PR #{number} at {merged['sha']}; Pages publication dispatched.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "publish"])
    parser.add_argument(
        "--verify-only", action="store_true", help="Open/update PR and verify CI/merge eligibility only."
    )
    arguments = parser.parse_args()
    try:
        if arguments.phase == "prepare":
            prepare()
        else:
            publish(verify_only=arguments.verify_only)
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.stderr.strip() or str(error)) from error
