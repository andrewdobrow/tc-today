"""Ensure Update can publish generated files after main moves during a long run.

All integration tests use a temporary, local bare Git remote; they do not
contact GitHub, alter the source repo, or use real news generation.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PUSH = ROOT / "scripts" / "push_generated_update.sh"

# Emitted by the failing Oct. 23 Update workflow and changed every run.
GENERATED_OCT23 = (
    # Additional files from the preceding successful automated commit 4f4c453,
    # which can also conflict when an older queued run rebases over it.
    "archive.html",
    "data.json",
    "data/canonical-cleanup-history.jsonl",
    "data/canonical-publication-ledger.json",
    "data/canonical-redirect-safety-audit.json",
    "data/canonical-redirects.json",
    "data/editorial_activation.json",
    "data/editorial_activation_history.jsonl",
    "data/editorial-image-rotation.json",
    "data/editorial-image-migration.json",
    "data/editorial_observability.json",
    "data/custom-post-publication-rebind.json",
    "data/event-audit.json",
    "data/events.json",
    "data/events-source-status.json",
    "data/late-reprint-identity-lock-pre_publication.json",
    "data/late-reprint-identity-lock-same_run_final_barrier.json",
    "data/homepage-ranking-recommendations.json",
    "data/section-editorial-ranking.json",
    "data/exact-headline-incident-reconciliation.json",
    "data/final-canonical-surface-contract.json",
    "data/final-canonical-surface-dedup.json",
    "data/final-canonical-surface-repair.json",
    "data/final-live-image-contract.json",
    "data/final-topic-category-integrity.json",
    "data/front-page-hero-selection.json",
    "data/homepage-permalink-contract.json",
    "data/homepage-permalink-dedupe.json",
    "data/homepage-ranking-review.md",
    "data/latest-news-rail-contract.json",
    "data/live-category-canonical-contract.json",
    "data/live-category-canonical-dedup.json",
    "data/live-publication-reconciliation.json",
    "data/material-update-headline-repair.json",
    "data/material-update-publication-invariant.json",
    "data/nonstory-publication-contract.json",
    "data/nonstory-purge.json",
    "data/rss-publication-contract.json",
    "data/rss-social-image-authority.json",
    "data/rss-social-image-contract.json",
    "data/semantic-publication-gate.json",
    "data/sports-expired-preview-live-suppression.json",
    "data/stories.json",
    "data/story-processed-articles.json",
    "data/story-registry.json",
    "data/story-shadow-log.json",
    "data/top-news-app-feed.json",
    "data/trusted-source-recovery.json",
    "feed.xml",
    "story-registry.json",
)

NEVER_OVERWRITE = (
    "data/article-content-overrides.json",
    "data/custom_articles.json",
    "data/manual_events.json",
    "data/article-image-overrides.json",
    "scripts/generate.py",
    ".github/workflows/update.yml",
)


def git(*args, cwd: Path, check: bool = True):
    result = subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True,
        check=False,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if check and result.returncode:
        raise AssertionError(f"git {args!r} failed {result.returncode}\n{result.stdout}\n{result.stderr}")
    return result


def write(root: Path, name: str, value: str):
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(value, encoding="utf-8")


def local_repos(tmp_path: Path, files: tuple[str, ...]):
    remote = tmp_path / "origin.git"
    remote.mkdir()
    git("init", "--bare", "--initial-branch=main", cwd=remote)
    bot = tmp_path / "bot"
    human = tmp_path / "human"
    git("clone", str(remote), str(bot), cwd=tmp_path)
    git("config", "user.name", "Test bot", cwd=bot)
    git("config", "user.email", "bot@example.test", cwd=bot)
    for path in files:
        write(bot, path, "base\n")
    git("add", "-A", cwd=bot)
    git("commit", "-m", "Initial state", cwd=bot)
    git("push", "-u", "origin", "main", cwd=bot)
    git("clone", str(remote), str(human), cwd=tmp_path)
    git("config", "user.name", "Test editor", cwd=human)
    git("config", "user.email", "editor@example.test", cwd=human)
    return remote, bot, human


def run_publish(bot: Path):
    return subprocess.run(
        ["bash", str(PUSH)], cwd=bot, text=True, capture_output=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_EDITOR": "true"},
        timeout=40,
    )


def check_remote_file(tmp_path: Path, remote: Path, path: str):
    tmp_path.mkdir(parents=True, exist_ok=True)
    view = tmp_path / "check"
    git("clone", str(remote), str(view), cwd=tmp_path)
    target = view / path
    return target.read_text() if target.exists() else None


@pytest.mark.parametrize("path", GENERATED_OCT23)
def test_every_oct23_generated_output_is_safe_to_rebase(path):
    function_only = PUSH.read_text().split("resolve_generated_conflicts()", 1)[0]
    cmd = ["bash", "-c", function_only + '\nis_generated_conflict "$1"', "--", path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, (path, result.stderr)


@pytest.mark.parametrize("path", NEVER_OVERWRITE)
def test_editor_managed_files_still_fail_closed(path):
    function_only = PUSH.read_text().split("resolve_generated_conflicts()", 1)[0]
    cmd = ["bash", "-c", function_only + '\nis_generated_conflict "$1"', "--", path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    assert result.returncode == 1, (path, result.stderr)


def test_rebase_generated_conflicts_retains_unrelated_human_commit(tmp_path):
    generated = ("feed.xml", "story-registry.json", "data/stories.json", "data/final-canonical-surface-contract.json")
    remote, bot, human = local_repos(tmp_path, generated + ("editor-note.txt",))
    for path in generated:
        write(human, path, "human intermediate generation\n")
    write(human, "editor-note.txt", "unrelated human source update\n")
    git("add", "-A", cwd=human)
    git("commit", "-m", "Human moved main during bot generation", cwd=human)
    git("push", "origin", "main", cwd=human)
    for path in generated:
        write(bot, path, "new generated output\n")
    result = run_publish(bot)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "Auto-resolving generated rebase conflict" in result.stdout
    for path in generated:
        assert check_remote_file(tmp_path / path.replace("/", "_"), remote, path) == "new generated output\n"
    assert check_remote_file(tmp_path / "humancheck", remote, "editor-note.txt") == "unrelated human source update\n"


def test_deleting_generated_output_survives_concurrent_edit(tmp_path):
    remote, bot, human = local_repos(tmp_path, ("feed.xml",))
    write(human, "feed.xml", "old remote feed updated\n")
    git("add", "-A", cwd=human)
    git("commit", "-m", "Remote modified feed", cwd=human)
    git("push", "origin", "main", cwd=human)
    git("rm", "feed.xml", cwd=bot)
    result = run_publish(bot)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert check_remote_file(tmp_path / "check_deleted", remote, "feed.xml") is None


def test_editor_override_conflict_stops_without_overwriting_remote(tmp_path):
    path = "data/article-content-overrides.json"
    remote, bot, human = local_repos(tmp_path, (path, "feed.xml"))
    write(human, path, "human verified correction\n")
    write(human, "feed.xml", "human updated feed\n")
    git("add", "-A", cwd=human)
    git("commit", "-m", "Human editorial correction", cwd=human)
    git("push", "origin", "main", cwd=human)
    write(bot, path, "stale bot correction\n")
    write(bot, "feed.xml", "generated feed\n")
    result = run_publish(bot)
    assert result.returncode == 2, result.stdout + "\n" + result.stderr
    assert "Unsafe source/config" in result.stderr
    assert path in result.stderr
    assert check_remote_file(tmp_path / "check_manual", remote, path) == "human verified correction\n"
    assert check_remote_file(tmp_path / "check_feed", remote, "feed.xml") == "human updated feed\n"



def test_update_uses_shallow_checkout_unless_historical_bakeoff_requested():
    """Production must not download every historical hourly editorial commit."""
    workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
    checkout = workflow.split("      - name: Checkout repo\n", 1)[1].split("\n      - name: ", 1)[0]
    assert "actions/checkout@v4" in checkout
    assert "fetch-depth: ${{ inputs.model_bakeoff && '0' || '2' }}" in checkout
    # Deploy checks out fresh main separately, independent of the generator.
    assert "      - name: Checkout latest main" in workflow


def test_two_commit_checkout_rebases_generated_output_after_human_push(tmp_path):
    """Simulate real production publishing on a shallow local clone.

    The bot begins with only two commits. A human then modifies generated
    content AND a manually edited file. The bot must preserve the human's
    manual corrections and resolve only generated-file conflicts.
    No live GitHub repositories are contacted.
    """
    remote, setup, human = local_repos(
        tmp_path, ("feed.xml", "data/article-content-overrides.json")
    )
    write(setup, "data/previous-generated.json", "second base commit\n")
    git("add", "-A", cwd=setup)
    git("commit", "-m", "Second base", cwd=setup)
    git("push", "origin", "main", cwd=setup)
    bot = tmp_path / "shallow-bot"
    git("clone", "--depth", "2", f"file://{remote}", str(bot), cwd=tmp_path)
    assert (bot / ".git" / "shallow").exists()
    write(bot, "feed.xml", "new bot generated feed\n")
    git("pull", "--ff-only", cwd=human)
    write(human, "feed.xml", "human intermediate generated feed\n")
    write(human, "data/article-content-overrides.json", '{"editor":"keep"}\n')
    git("add", "-A", cwd=human)
    git("commit", "-m", "Human updated generated and protected data", cwd=human)
    git("push", "origin", "main", cwd=human)
    result = run_publish(bot)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "Auto-resolving generated rebase conflict" in result.stdout
    assert check_remote_file(tmp_path / "shallow-feed", remote, "feed.xml") == "new bot generated feed\n"
    assert check_remote_file(tmp_path / "shallow-protected", remote, "data/article-content-overrides.json") == '{"editor":"keep"}\n'
