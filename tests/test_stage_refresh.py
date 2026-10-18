"""Local Git integration plus mocked GitHub control flow; no live API or feeds."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stage-refresh.py"


def git(directory, *arguments, check=True):
    return subprocess.run(["git", "-C", str(directory), *arguments], check=check, text=True, capture_output=True)


@pytest.fixture
def coordinator(tmp_path, monkeypatch):
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
    hook = origin / "hooks/pre-receive"
    hook.write_text('#!/bin/sh\nwhile read old new ref; do\n  if [ "$ref" = refs/heads/main ]; then exit 1; fi\ndone\n')
    hook.chmod(0o755)
    spec = importlib.util.spec_from_file_location("stage_refresh_fixture", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.chdir(work)
    monkeypatch.setenv("GITHUB_REPOSITORY", "snowball-projects/kickoff")
    monkeypatch.setenv("REFRESH_STATUS_PATH", str(tmp_path / "publication-status.md"))
    return module, work, origin


class GitHub:
    """Only API decisions are mocked; every branch push is real local Git."""

    def __init__(self, module, monkeypatch, *, conclusion="success", mergeable="clean", merged=True, race=None):
        self.module = module
        self.calls = []
        self.created = False
        self.run = 0
        self.conclusion = conclusion
        self.mergeable = mergeable
        self.merged = merged
        self.race = race
        monkeypatch.setattr(module, "api", self.api)

    def api(self, path, method="GET", payload=None):
        self.calls.append((path, method, payload))
        head = self.module.git("rev-parse", "HEAD").stdout.strip()
        base = self.module.git("rev-parse", "origin/main").stdout.strip()
        pr = {
            "number": 17,
            "state": "open",
            "draft": False,
            "head": {"sha": "f" * 40 if self.race == "head" else head},
            "base": {"sha": "e" * 40 if self.race == "base" else base},
            "mergeable_state": self.mergeable,
        }
        if "/pulls?" in path:
            return [pr] if self.created else []
        if path.endswith("/pulls") and method == "POST":
            self.created = True
            return pr
        if path.endswith("/pulls/17"):
            return pr
        if "/ci.yml/runs?" in path:
            runs = (
                []
                if not self.run
                else [
                    {
                        "id": self.run,
                        "head_sha": head,
                        "event": "workflow_dispatch",
                        "head_branch": self.module.BRANCH,
                        "status": "completed",
                        "conclusion": self.conclusion,
                        "html_url": "https://example.invalid/fixture-ci",
                    }
                ]
            )
            return {"workflow_runs": runs}
        if path.endswith("ci.yml/dispatches"):
            self.run += 1
            return None
        if path.endswith("/merge"):
            assert payload["sha"] == head and payload["merge_method"] == "merge"
            return {"merged": self.merged, "sha": "a" * 40}
        if path.endswith("pages.yml/dispatches"):
            assert payload == {"ref": "main"}
            return None
        raise AssertionError(f"Unexpected API call: {path}")

    def mutations(self):
        return [(path, method) for path, method, _ in self.calls if method != "GET"]


def changed(coordinator):
    module, work, _ = coordinator
    module.prepare()
    (work / "data/published/2026.json").write_text('{"events": ["reviewed fixture"]}\n')


def test_checked_pr_and_explicit_dispatches_never_git_push_main(coordinator, monkeypatch):
    module, work, origin = coordinator
    before = git(origin, "rev-parse", "main").stdout
    changed(coordinator)
    (work / "README.md").write_text("Unrelated unstaged work\n")
    github = GitHub(module, monkeypatch)
    module.publish()
    assert git(origin, "rev-parse", "main").stdout == before  # API merge is a mock, not a direct Git push.
    assert git(origin, "diff", "--name-only", "main", module.BRANCH).stdout.strip() == "data/published/2026.json"
    assert git(origin, "show", f"{module.BRANCH}:README.md").stdout == "Original source\n"
    changes = github.mutations()
    assert [path.rsplit("/", 2)[-2:] for path, _ in changes][-2:] == [["17", "merge"], ["pages.yml", "dispatches"]]
    dispatch = next(payload for path, _, payload in github.calls if path.endswith("ci.yml/dispatches"))
    assert dispatch["ref"] == module.BRANCH
    assert dispatch["inputs"]["expected_head"] == git(origin, "rev-parse", module.BRANCH).stdout.strip()


def test_non_publishing_rehearsal_does_not_merge_or_dispatch_pages(coordinator, monkeypatch):
    module, _, _ = coordinator
    changed(coordinator)
    github = GitHub(module, monkeypatch)
    module.publish(verify_only=True)
    assert not any(path.endswith(("/merge", "pages.yml/dispatches")) for path, _ in github.mutations())


def test_no_pending_data_creates_no_remote_branch_or_api_calls(coordinator, monkeypatch, capsys):
    module, _, origin = coordinator
    module.prepare()
    github = GitHub(module, monkeypatch)
    module.publish()
    assert not github.calls
    assert git(origin, "for-each-ref", "--format=%(refname)", "refs/heads").stdout.strip() == "refs/heads/main"
    assert "previous publication failure is not retried" in capsys.readouterr().out


def test_same_branch_and_pr_are_reused_without_force(coordinator, monkeypatch, tmp_path):
    module, _, origin = coordinator
    changed(coordinator)
    github = GitHub(module, monkeypatch)
    module.publish(verify_only=True)
    previous = git(origin, "rev-parse", module.BRANCH).stdout.strip()
    # Fresh checkout models the next runner; pending PR data remains on the same remote ref.
    second = tmp_path / "second"
    subprocess.run(["git", "clone", str(origin), str(second)], check=True, capture_output=True)
    monkeypatch.chdir(second)
    module.prepare()
    (second / "data/published/2026.json").write_text('{"events": ["newer fixture"]}\n')
    module.publish(verify_only=True)
    git(origin, "merge-base", "--is-ancestor", previous, module.BRANCH)
    assert sum(path.endswith("/pulls") and method == "POST" for path, method in github.mutations()) == 1
    assert git(origin, "for-each-ref", "--format=%(refname)", "refs/heads").stdout.splitlines() == [
        f"refs/heads/{module.BRANCH}",
        "refs/heads/main",
    ]


def test_shallow_runner_recovers_merge_base_after_main_advances(coordinator, monkeypatch, tmp_path):
    module, work, origin = coordinator
    changed(coordinator)
    GitHub(module, monkeypatch)
    module.publish(verify_only=True)
    pending = git(origin, "rev-parse", module.BRANCH).stdout.strip()
    git(work, "switch", "main")
    (work / "README.md").write_text("Main advanced after the pending refresh\n")
    git(work, "add", "README.md")
    git(work, "commit", "-m", "Advance main independently")
    # Model an owner merge on the fixture server; retain the hook forbidding runtime main pushes.
    git(origin, "fetch", str(work), "main:refs/heads/main")
    main = git(origin, "rev-parse", "main").stdout.strip()
    shallow = tmp_path / "shallow-runner"
    # Local-path clones ignore --depth, so use file:// to exercise a real shallow runner.
    subprocess.run(
        ["git", "clone", "--depth=1", "--branch=main", origin.as_uri(), str(shallow)],
        check=True,
        capture_output=True,
    )
    assert git(shallow, "rev-parse", "--is-shallow-repository").stdout.strip() == "true"
    git(shallow, "fetch", "origin", module.BRANCH)
    assert git(shallow, "merge-base", "HEAD", "FETCH_HEAD", check=False).returncode == 1
    monkeypatch.chdir(shallow)
    module.prepare()
    assert git(shallow, "rev-parse", "--is-shallow-repository").stdout.strip() == "false"
    git(shallow, "merge-base", "--is-ancestor", pending, "HEAD")
    git(shallow, "merge-base", "--is-ancestor", main, "HEAD")
    assert (shallow / "README.md").read_text() == "Main advanced after the pending refresh\n"
    assert "reviewed fixture" in (shallow / "data/published/2026.json").read_text()
    assert module.data_changes() == ["data/published/2026.json"]


@pytest.mark.parametrize("failed_request", ["/merge", "pages.yml/dispatches"])
def test_lost_merge_or_dispatch_response_records_uncertainty_without_retry(coordinator, monkeypatch, failed_request):
    module, work, _ = coordinator
    changed(coordinator)
    github = GitHub(module, monkeypatch)
    original = github.api

    def lost_response(path, method="GET", payload=None):
        response = original(path, method, payload)  # Request can succeed before its response is lost.
        if path.endswith(failed_request):
            raise subprocess.CalledProcessError(1, ["gh", "api"], stderr="connection lost after request")
        return response

    monkeypatch.setattr(module, "api", lost_response)
    with pytest.raises(subprocess.CalledProcessError):
        module.publish()
    status = (work.parent / "publication-status.md").read_text()
    assert "unchanged" not in status or "do not assume the calendar is unchanged" in status
    assert module.RECOVERY in status
    if failed_request == "/merge":
        assert "outcome is not confirmed" in status
        assert "No Pages dispatch has been attempted" in status
        assert not any(path.endswith("pages.yml/dispatches") for path, _ in github.mutations())
    else:
        assert f"confirmed merged at {'a' * 40}" in status
        assert "acceptance and deployment are not confirmed" in status
        assert sum(path.endswith("pages.yml/dispatches") for path, _ in github.mutations()) == 1


def test_accepted_dispatch_does_not_claim_live_publication(coordinator, monkeypatch):
    module, work, _ = coordinator
    changed(coordinator)
    GitHub(module, monkeypatch)
    module.publish()
    status = (work.parent / "publication-status.md").read_text()
    assert "Pages dispatch was accepted" in status
    assert "deployment and live publication still require verification" in status


def test_merged_data_with_failed_dispatch_does_not_disappear_into_no_change_success(
    coordinator, monkeypatch, tmp_path, capsys
):
    module, work, origin = coordinator
    changed(coordinator)
    github = GitHub(module, monkeypatch)
    original = github.api

    def merged_then_failed_dispatch(path, method="GET", payload=None):
        response = original(path, method, payload)
        if path.endswith("/merge"):
            head = git(work, "rev-parse", "HEAD").stdout.strip()
            base = git(origin, "rev-parse", "main").stdout.strip()
            merged = git(
                work,
                *module.IDENTITY,
                "commit-tree",
                f"{head}^{{tree}}",
                "-p",
                base,
                "-p",
                head,
                "-m",
                "Fixture GitHub server merge",
            ).stdout.strip()
            # Simulate GitHub's server merge, retaining the runtime main-push rejection hook.
            git(origin, "fetch", str(work), f"{merged}:refs/heads/main")
            return {"merged": True, "sha": merged}
        if path.endswith("pages.yml/dispatches"):
            raise subprocess.CalledProcessError(1, ["gh", "api"], stderr="dispatch response unavailable")
        return response

    monkeypatch.setattr(module, "api", merged_then_failed_dispatch)
    with pytest.raises(subprocess.CalledProcessError):
        module.publish()
    failed_status = (work.parent / "publication-status.md").read_text()
    assert git(origin, "rev-parse", "main").stdout.strip() in failed_status
    second = tmp_path / "next-runner"
    subprocess.run(["git", "clone", str(origin), str(second)], check=True, capture_output=True)
    monkeypatch.chdir(second)
    monkeypatch.setenv("REFRESH_STATUS_PATH", str(tmp_path / "next-run-status.md"))
    module.prepare()
    calls_before = len(github.calls)
    capsys.readouterr()
    module.publish()
    assert len(github.calls) == calls_before  # No duplicate merge or blind redispatch.
    output = capsys.readouterr().out
    assert "this run does not merge or dispatch Pages" in output
    assert "previous publication failure is not retried" in output
    assert module.RECOVERY in output
    assert (work.parent / "publication-status.md").read_text() == failed_status


@pytest.mark.parametrize(
    "stage",
    [
        None,
        "Merge request outcome is not confirmed. No Pages dispatch has been attempted.",
        "PR #17 is confirmed merged. Pages dispatch acceptance is not confirmed.",
        "Pages dispatch was accepted; deployment requires verification.",
    ],
)
def test_failure_issue_reports_actual_stage_without_claiming_calendar_unchanged(tmp_path, stage):
    workflow = (SCRIPT.parents[1] / ".github/workflows/refresh-pr.yml").read_text()
    # Execute the actual reporting shell with a fake gh; it cannot contact GitHub.
    report = workflow.split("      - name: Report failure\n", 1)[1].split("        run: |\n", 1)[1]
    shell = "\n".join(line.removeprefix("          ") for line in report.splitlines())
    status = tmp_path / "status.md"
    if stage is not None:
        status.write_text(stage + "\n")
    subprocess.run(
        ["bash", "-e", "-c", 'gh() { printf "%s\\n" "$@"; }\n' + shell],
        check=True,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "RUNNER_TEMP": str(tmp_path),
            "REFRESH_STATUS_PATH": str(status),
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_REPOSITORY": "snowball-projects/kickoff",
            "GITHUB_RUN_ID": "1234",
        },
    )
    body = (tmp_path / "refresh-failure.md").read_text()
    assert "The published calendar is unchanged" not in body
    assert (stage or "No publication stage was recorded") in body
    assert "A no-change refresh does not retry publication" in body
    assert "bounded operator recovery procedure" in body


@pytest.mark.parametrize(
    "conclusion,mergeable,merged,race",
    [
        ("failure", "clean", True, None),
        ("success", "blocked", True, None),
        ("success", "clean", False, None),
        ("success", "clean", True, "head"),
        ("success", "clean", True, "base"),
    ],
)
def test_failed_ci_or_merge_gates_never_dispatch_publication(
    coordinator, monkeypatch, conclusion, mergeable, merged, race
):
    module, _, origin = coordinator
    before = git(origin, "rev-parse", "main").stdout
    changed(coordinator)
    github = GitHub(module, monkeypatch, conclusion=conclusion, mergeable=mergeable, merged=merged, race=race)
    with pytest.raises(RuntimeError):
        module.publish()
    assert not any(path.endswith("pages.yml/dispatches") for path, _ in github.mutations())
    assert not any(path.endswith(("/approve", "/reviews")) for path, _ in github.mutations())
    assert git(origin, "rev-parse", "main").stdout == before


def test_missing_pr_permission_fails_without_dispatch_or_main_fallback(coordinator, monkeypatch):
    module, _, origin = coordinator
    before = git(origin, "rev-parse", "main").stdout
    changed(coordinator)
    github = GitHub(module, monkeypatch)
    original = github.api

    def denied(path, method="GET", payload=None):
        if path.endswith("/pulls") and method == "POST":
            raise subprocess.CalledProcessError(1, ["gh", "api"], stderr="Actions PR creation is disabled")
        return original(path, method, payload)

    monkeypatch.setattr(module, "api", denied)
    with pytest.raises(subprocess.CalledProcessError):
        module.publish()
    assert not any(path.endswith("/dispatches") for path, _ in github.mutations())
    assert git(origin, "rev-parse", "main").stdout == before


def test_preexisting_staged_work_is_preserved(coordinator, monkeypatch):
    module, work, _ = coordinator
    changed(coordinator)
    (work / "README.md").write_text("Existing staged work\n")
    git(work, "add", "README.md")
    with pytest.raises(ValueError, match="index must be empty"):
        module.publish()
    assert git(work, "diff", "--cached", "--name-only").stdout.strip() == "README.md"


def test_pending_non_data_branch_work_is_refused(coordinator, monkeypatch, tmp_path):
    module, work, origin = coordinator
    module.prepare()
    (work / "README.md").write_text("Do not automatically publish code\n")
    git(work, "add", "README.md")
    git(work, "commit", "-m", "Owner work")
    git(work, "push", "origin", f"HEAD:refs/heads/{module.BRANCH}")
    second = tmp_path / "second"
    subprocess.run(["git", "clone", str(origin), str(second)], check=True, capture_output=True)
    monkeypatch.chdir(second)
    with pytest.raises(ValueError, match="non-published-data changes"):
        module.prepare()


def test_old_successful_run_cannot_satisfy_new_dispatch(coordinator, monkeypatch):
    module, _, _ = coordinator
    github = GitHub(module, monkeypatch)
    github.run = 1
    times = iter([0, 0, 601])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    with pytest.raises(TimeoutError):
        module.wait_for_ci(module.repository(), module.git("rev-parse", "HEAD").stdout.strip(), {1})


def test_rejected_branch_push_has_no_api_or_main_fallback(coordinator, monkeypatch):
    module, _, origin = coordinator
    changed(coordinator)
    (origin / "hooks/pre-receive").write_text("#!/bin/sh\nexit 1\n")
    github = GitHub(module, monkeypatch)
    with pytest.raises(subprocess.CalledProcessError):
        module.publish()
    assert not github.calls
