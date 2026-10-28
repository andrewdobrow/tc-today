"""Existing Update workflow must fail visibly if the editorial provider has no credits."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_editorial_api_credits.py"
WORKFLOW = ROOT / ".github/workflows/update.yml"


def _run(tmp_path: Path, log_content: str, report=None, *, stale=False):
    log = tmp_path / "generate.log"
    started = tmp_path / "generate.start"
    diagnostic = tmp_path / "category-generation-report.json"

    log.write_text(log_content, encoding="utf-8")
    if stale:
        diagnostic.write_text(json.dumps(report), encoding="utf-8")
        os.utime(diagnostic, ns=(1_000_000_000, 1_000_000_000))
        started.touch()
    else:
        started.touch()
        if report is not None:
            diagnostic.write_text(json.dumps(report), encoding="utf-8")

    return subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--log", str(log),
            "--started", str(started),
            "--report", str(diagnostic),
        ],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )


def test_fails_on_exact_production_openai_credit_error(tmp_path):
    error = (
        "Error code: 429 - {'error': {'message': 'You have no credits remaining. "
        "Add credits to continue using the API', 'type': 'insufficient_quota', "
        "'code': 'credit_balance_exhausted'}}"
    )
    result = _run(tmp_path, error)
    assert result.returncode == 1
    assert "TCT editorial API credits exhausted" in result.stdout
    assert "rerun Update Treasure Coast Today" in result.stdout


def test_fails_when_generation_swallowed_error_but_fresh_report_has_it(tmp_path):
    report = {
        "generated_at": "2026-10-28T20:49:30Z",
        "categories": [
            {
                "status": "generation_failed_archive_recovery",
                "failure_summary": "Error code: 429: insufficient_quota",
            },
        ],
    }
    result = _run(tmp_path, "Archive fallback used successfully", report)
    assert result.returncode == 1
    assert "category-generation-report.json" in result.stdout


def test_stale_checked_in_report_cannot_fail_healthy_run(tmp_path):
    report = {"categories": [{"failure_summary": "credit_balance_exhausted"}]}
    result = _run(tmp_path, "Generation succeeded", report, stale=True)
    assert result.returncode == 0


def test_ordinary_rate_limit_and_general_failures_are_not_mislabeled(tmp_path):
    for error in (
        "Error code: 429 rate_limit_exceeded - too many requests",
        "Temporary network timeout",
        "No publishable article sources for county",
        "Category generation failed; archive recovery used",
    ):
        result = _run(tmp_path, error)
        assert result.returncode == 0, error


def test_anthropic_out_of_credits_also_fails(tmp_path):
    result = _run(tmp_path, "API error: insufficient credits to process message")
    assert result.returncode == 1


def test_missing_run_log_is_a_clear_failure(tmp_path):
    started = tmp_path / "generate.start"
    started.touch()
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--log", str(tmp_path / "absent.log"),
         "--started", str(started)],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 1
    assert "Missing per-run generator log" in result.stdout


def test_production_guard_runs_before_commit_and_deploy():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "set -o pipefail" in workflow
    assert 'tee "$RUNNER_TEMP/tct-generate.log"' in workflow
    assert 'tct-generate-start.marker' in workflow
    assert "python scripts/check_editorial_api_credits.py" in workflow
    assert workflow.index("- name: Generate news") < workflow.index(
        "- name: Fail on exhausted editorial API credits"
    )
    assert workflow.index("- name: Fail on exhausted editorial API credits") < workflow.index(
        "- name: Commit and push"
    )
    assert "Save generation cache even when generation fails" in workflow
    assert "needs: update" in workflow
    assert "continue-on-error: true" not in workflow.split(
        "- name: Fail on exhausted editorial API credits", 1
    )[1].split("- name:", 1)[0]
