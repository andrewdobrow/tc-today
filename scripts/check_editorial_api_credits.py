#!/usr/bin/env python3
"""Fail TCT's existing Update job if this run exhausted editorial model credits.

The generator intentionally uses archive recovery when model calls fail. That is
safe for public content, but billing failure must not turn into a green deploy.

Read this run's captured generator log and freshly written diagnostics only.
Do not call a billing API, log secrets, or treat ordinary HTTP 429 throttling
as proof of exhausted credits.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


QUOTA_MARKERS = (
    "credit_balance_exhausted",
    "insufficient_quota",
    "billing_hard_limit_reached",
    "no credits remaining",
    "insufficient credits",
    "not enough credits",
    "exceeded your current quota",
)


def has_exhausted_credits(text: str) -> bool:
    normalized = str(text or "").casefold()
    return any(marker in normalized for marker in QUOTA_MARKERS)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def current_report_has_quota_failure(report: Path, started: Path) -> bool:
    """Ignore any old diagnostics tracked in the repository checkout."""
    if not report.is_file():
        return False
    try:
        if report.stat().st_mtime_ns < started.stat().st_mtime_ns:
            return False
        payload = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # The captured generation log still provides an independent check.
        return False
    return any(has_exhausted_credits(value) for value in _strings(payload))


def evaluate(log: Path, started: Path, reports: list[Path]) -> tuple[bool, list[str]]:
    if not started.is_file():
        raise ValueError("Missing per-run generation start marker; cannot verify diagnostic freshness.")
    if not log.is_file():
        raise ValueError("Missing per-run generator log; cannot verify API credit status.")

    sources = []
    if has_exhausted_credits(log.read_text(encoding="utf-8", errors="replace")):
        sources.append("this run's generator log")
    for report in reports:
        if current_report_has_quota_failure(report, started):
            sources.append(str(report))
    return bool(sources), sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--started", required=True, type=Path)
    parser.add_argument("--report", action="append", default=[], type=Path)
    args = parser.parse_args(argv)

    try:
        exhausted, sources = evaluate(args.log, args.started, args.report)
    except (ValueError, OSError) as exc:
        print(f"::error title=TCT editorial API credit-check failed::{exc}", flush=True)
        return 1

    summary = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if exhausted:
        msg = (
            "Editorial AI API credits are exhausted. TCT's archive fallback "
            "preserved existing articles, but this update will fail rather than "
            "commit/deploy a misleading green run. Add API credits or resolve "
            "the provider's quota, then rerun Update Treasure Coast Today."
        )
        print(f"::error title=TCT editorial API credits exhausted::{msg}", flush=True)
        print("Credit failure confirmed in: " + ", ".join(sources), flush=True)
        if summary:
            with open(summary, "a", encoding="utf-8") as out:
                out.write("### Editorial API credits exhausted\n\n"
                          + msg + "\n\nDetected in: " + ", ".join(sources) + "\n")
        return 1

    print("Editorial API credit check passed: no exhausted-credit signal in this run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
