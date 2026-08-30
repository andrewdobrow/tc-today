#!/usr/bin/env python3
"""Bound the append-only editorial audit log without touching editorial authority.

``data/editorial_audit.jsonl`` is diagnostic history only.  It is intentionally
append-only during a run, but an unattended site must not allow that history to
outgrow GitHub's repository file limits.  Retention therefore keeps the newest
complete JSONL records and removes only the oldest diagnostic rows.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

EDITORIAL_AUDIT_RETENTION_TRIGGER_BYTES = 64 * 1024 * 1024
EDITORIAL_AUDIT_RETENTION_TARGET_BYTES = 48 * 1024 * 1024
COPY_CHUNK_BYTES = 1024 * 1024


def compact_editorial_audit_log(
    path: Path | str,
    *,
    trigger_bytes: int = EDITORIAL_AUDIT_RETENTION_TRIGGER_BYTES,
    target_bytes: int = EDITORIAL_AUDIT_RETENTION_TARGET_BYTES,
) -> dict[str, Any]:
    """Retain the newest complete JSONL rows once ``path`` crosses the trigger.

    The operation is byte-bounded, line-safe, and atomic.  It does not parse or
    rewrite JSON records, so surviving audit evidence remains byte-for-byte
    unchanged.  ``target_bytes`` must be smaller than ``trigger_bytes`` to leave
    useful hysteresis between compactions.
    """

    audit_path = Path(path)
    trigger = int(trigger_bytes)
    target = int(target_bytes)
    if trigger <= 0 or target <= 0 or target >= trigger:
        raise ValueError("editorial audit retention requires 0 < target < trigger")

    if not audit_path.exists():
        return {
            "compacted": False,
            "reason": "missing",
            "bytes_before": 0,
            "bytes_after": 0,
            "bytes_reclaimed": 0,
            "retained_rows": 0,
        }

    before = audit_path.stat().st_size
    if before <= trigger:
        return {
            "compacted": False,
            "reason": "below_trigger",
            "bytes_before": before,
            "bytes_after": before,
            "bytes_reclaimed": 0,
            "retained_rows": None,
        }

    tmp_path = audit_path.with_name(audit_path.name + ".retention.tmp")
    retained_rows = 0
    try:
        with audit_path.open("rb") as source:
            start = max(0, before - target)
            if start:
                # If the byte boundary lands inside a JSONL record, discard that
                # one partial record and begin at the next complete line.  When it
                # lands exactly on a line boundary, preserve the whole next row.
                source.seek(start - 1)
                previous = source.read(1)
                source.seek(start)
                if previous != b"\n":
                    source.readline()

            with tmp_path.open("wb") as destination:
                while True:
                    chunk = source.read(COPY_CHUNK_BYTES)
                    if not chunk:
                        break
                    destination.write(chunk)
                    retained_rows += chunk.count(b"\n")
                destination.flush()
                os.fsync(destination.fileno())

        os.replace(tmp_path, audit_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    after = audit_path.stat().st_size
    return {
        "compacted": True,
        "reason": "retention_applied",
        "bytes_before": before,
        "bytes_after": after,
        "bytes_reclaimed": before - after,
        "retained_rows": retained_rows,
    }


def _main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "data" / "editorial_audit.jsonl"
    report = compact_editorial_audit_log(path)
    if report["compacted"]:
        print(
            "Editorial audit retention: "
            f"{report['bytes_before'] / (1024 * 1024):.2f} MiB -> "
            f"{report['bytes_after'] / (1024 * 1024):.2f} MiB; "
            f"retained {report['retained_rows']} newest decision(s)"
        )
    else:
        print(
            "Editorial audit retention: no compaction needed "
            f"({report['bytes_after'] / (1024 * 1024):.2f} MiB)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
