#!/usr/bin/env python3
"""Normalize the persisted editorial story registry before validation/tests.

The production registry can acquire a newly visible duplicate component after one
repair layer merges records. This preflight applies the deterministic repair to a
fixed point, verifies that a second pass is clean, and atomically persists only
when the tracked registry actually changed.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tct_engine.registry_repair import repair_registry_payload

DEFAULT_REGISTRY = ROOT / "data" / "editorial_story_registry.json"


def _read_registry(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Registry preflight failed: missing {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Registry preflight failed: invalid JSON in {path} at "
            f"line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Registry preflight failed: {path} must contain a JSON object")
    return payload


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def normalize_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    payload = _read_registry(path)
    report = repair_registry_payload(payload)

    verification_payload = deepcopy(payload)
    verification = repair_registry_payload(verification_payload)
    if verification.changed:
        raise SystemExit(
            "Registry preflight failed: deterministic repair did not reach a fixed "
            "point in one pass. Remaining merges: "
            f"{verification.merged_story_ids}"
        )

    if report.changed:
        _atomic_write(path, payload)

    return {
        "changed": report.changed,
        "active_stories_before": report.active_stories_before,
        "active_stories_after": report.active_stories_after,
        "records_removed": report.duplicate_story_records_removed,
        "source_records_removed": report.source_story_records_removed,
        "unified_records_removed": report.unified_incident_story_records_removed,
        "incident_records_removed": report.incident_story_records_removed,
        "remaining_source_identity_groups": report.remaining_source_identity_groups,
        "remaining_unified_incident_groups": report.remaining_unified_incident_groups,
        "remaining_incident_identity_groups": report.remaining_incident_identity_groups,
        "remaining_timeline_coherence_violations": report.remaining_timeline_coherence_violations,
        "verification_clean": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args()
    result = normalize_registry(args.registry)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
