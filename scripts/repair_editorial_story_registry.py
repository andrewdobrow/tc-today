#!/usr/bin/env python3
"""Normalize the persisted editorial story registry before validation/tests.

The production registry can acquire a newly visible duplicate component after one
repair layer merges records. This preflight applies the deterministic repair to a
fixed point, verifies that a second pass is clean, and atomically persists only
when the tracked registry actually changed.
"""
from __future__ import annotations

import argparse
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
    active_before = len(payload.get("stories", {}) or {})

    # A complete deterministic repair can expose another deterministic component
    # only after an earlier pass has combined or moved evidence.  Converge the
    # whole repair pipeline in place instead of requiring every component to be
    # visible during the first top-level call.  Every pass uses the same strict
    # repair_registry_payload() authority contracts; no fuzzy/candidate-only
    # evidence gains write authority here.
    max_passes = 16
    reports = []
    changed_any = False

    for pass_number in range(1, max_passes + 1):
        report = repair_registry_payload(payload)
        reports.append(report)
        changed_any = changed_any or report.changed

        # repair_registry_payload reports every authoritative story mutation in
        # ``changed``.  Once a complete pass is clean, rerunning the same
        # deterministic pipeline against the same identity state cannot expose a
        # new component.  This avoids the old 50+ MiB deepcopy verification, which
        # was both expensive and incorrectly treated a legitimate second-pass
        # merge as a fatal condition.
        if not report.changed:
            break
    else:
        remaining = reports[-1].merged_story_ids if reports else {}
        raise SystemExit(
            "Registry preflight failed: deterministic repair did not converge "
            f"within {max_passes} passes. Last merges: {remaining}"
        )

    if changed_any:
        _atomic_write(path, payload)

    final_report = reports[-1]
    return {
        "changed": changed_any,
        "repair_passes": len(reports),
        "active_stories_before": active_before,
        "active_stories_after": len(payload.get("stories", {}) or {}),
        "records_removed": sum(r.duplicate_story_records_removed for r in reports),
        "source_records_removed": sum(r.source_story_records_removed for r in reports),
        "unified_records_removed": sum(r.unified_incident_story_records_removed for r in reports),
        "incident_records_removed": sum(r.incident_story_records_removed for r in reports),
        "remaining_source_identity_groups": final_report.remaining_source_identity_groups,
        "remaining_unified_incident_groups": final_report.remaining_unified_incident_groups,
        "remaining_incident_identity_groups": final_report.remaining_incident_identity_groups,
        "remaining_timeline_coherence_violations": final_report.remaining_timeline_coherence_violations,
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
