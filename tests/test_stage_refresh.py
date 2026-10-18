"""Real local Git remotes prove refreshes cannot update protected main."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stage-refresh.py"
BRANCH = "automation/schedules-1234567-1"


def git(directory, *arguments, check=True):
    return subprocess.run(["git", "-C", str(directory), *arguments], check=check, text=True, capture_output=True)


@pytest.fixture
def repository(tmp_path):
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(origin)], check=True, capture_output=True)
    subprocess.run(["git", "init", "--initial-branch=main", str(work)], check=True, capture_output=True)
    git(work, "config", "user.name", "Fixture maintainer")
    git(work, "config", "user.email", "fixture@example.invalid")
    git(work, "config", "commit.gpgsign", "false")
    (work / "data/published").mkdir(parents=True)
    (work / "data/published/2026.json").write_text('{"events": []}\n')
    (work / "README.md").write_text("Original source\n")
    git(work, "add", ".")
    git(work, "commit", "-m", "Initial fixture")
    git(work, "remote", "add", "origin", str(origin))
    git(work, "push", "origin", "main")
    # Any accidental direct main update is rejected by this local server.
    hook = origin / "hooks/pre-receive"
    hook.write_text('#!/bin/sh\nwhile read old new ref; do\n  if [ "$ref" = refs/heads/main ]; then exit 1; fi\ndone\n')
    hook.chmod(0o755)
    return work, origin, tmp_path / "summary.md"


def run_stage(repository, **overrides):
    work, _, summary = repository
    environment = {
        **os.environ,
        "GITHUB_RUN_ID": "1234567",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_REPOSITORY": "snowball-projects/kickoff",
        "GITHUB_STEP_SUMMARY": str(summary),
        **overrides,
    }
    return subprocess.run([sys.executable, str(SCRIPT)], cwd=work, env=environment, capture_output=True, text=True)


def test_changed_data_goes_to_review_branch_and_leaves_main_unchanged(repository):
    work, origin, summary = repository
    old_main = git(origin, "rev-parse", "main").stdout
    (work / "data/published/2026.json").write_text('{"events": ["reviewed fixture"]}\n')
    (work / "README.md").write_text("Unrelated local work\n")
    (work / "raw-private-fixture.txt").write_text("Synthetic retained input; never publish\n")
    result = run_stage(repository)
    assert result.returncode == 0, result.stderr
    assert git(origin, "rev-parse", "main").stdout == old_main
    assert git(work, "rev-parse", "main").stdout == old_main
    assert git(origin, "diff", "--name-only", "main", BRANCH).stdout.strip() == "data/published/2026.json"
    assert git(origin, "show", f"{BRANCH}:README.md").stdout == "Original source\n"
    assert (work / "README.md").read_text() == "Unrelated local work\n"
    assert "Open a pull request" in summary.read_text()
    assert "compare/main...automation%2Fschedules-1234567-1" in summary.read_text()


def test_no_published_changes_create_no_branch(repository):
    work, origin, summary = repository
    (work / "README.md").write_text("Unrelated local work\n")
    result = run_stage(repository)
    assert result.returncode == 0, result.stderr
    assert git(origin, "for-each-ref", "--format=%(refname)", "refs/heads").stdout.strip() == "refs/heads/main"
    assert "No published schedule changes" in result.stdout
    assert not summary.exists()


def test_existing_staged_changes_are_not_committed(repository):
    work, origin, _ = repository
    (work / "README.md").write_text("Existing staged work\n")
    git(work, "add", "README.md")
    result = run_stage(repository)
    assert result.returncode != 0
    assert "index must be empty" in result.stderr
    assert git(origin, "show", "main:README.md").stdout == "Original source\n"
    assert git(work, "diff", "--cached", "--name-only").stdout.strip() == "README.md"


def test_duplicate_remote_branch_is_preserved(repository):
    work, origin, _ = repository
    git(work, "push", "origin", f"HEAD:refs/heads/{BRANCH}")
    original = git(origin, "rev-parse", BRANCH).stdout
    (work / "data/published/2026.json").write_text('{"events": ["new fixture"]}\n')
    result = run_stage(repository)
    assert result.returncode != 0
    assert "refusing to overwrite" in result.stderr
    assert git(origin, "rev-parse", BRANCH).stdout == original
    assert git(work, "branch", "--show-current").stdout.strip() == "main"


@pytest.mark.parametrize("run_id,attempt", [("../../main", "1"), ("1234567", "1 --force"), ("", "1")])
def test_invalid_branch_inputs_fail_before_staging(repository, run_id, attempt):
    work, _, _ = repository
    (work / "data/published/2026.json").write_text('{"events": ["new fixture"]}\n')
    result = run_stage(repository, GITHUB_RUN_ID=run_id, GITHUB_RUN_ATTEMPT=attempt)
    assert result.returncode != 0
    assert "numeric GitHub run ID" in result.stderr
    assert not git(work, "diff", "--cached", "--name-only").stdout


def test_non_main_checkout_is_refused(repository):
    work, _, _ = repository
    git(work, "switch", "-c", "work-in-progress")
    result = run_stage(repository)
    assert result.returncode != 0
    assert "checked-out main branch" in result.stderr


def test_failed_review_branch_push_never_falls_back_to_main(repository):
    work, origin, summary = repository
    old_main = git(origin, "rev-parse", "main").stdout
    (origin / "hooks/pre-receive").write_text("#!/bin/sh\nexit 1\n")
    (work / "data/published/2026.json").write_text('{"events": ["new fixture"]}\n')
    result = run_stage(repository)
    assert result.returncode != 0
    assert git(origin, "rev-parse", "main").stdout == old_main
    assert git(origin, "show-ref", "--verify", f"refs/heads/{BRANCH}", check=False).returncode != 0
    assert not summary.exists()
