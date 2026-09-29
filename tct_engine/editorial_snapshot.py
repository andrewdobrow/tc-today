"""Safe end-of-run registry stabilization for editorial snapshot reuse."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .registry_repair import repair_registry_payload


def _read_registry(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Registry stabilization failed: missing {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Registry stabilization failed: invalid JSON in {path} at "
            f"line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(
            f"Registry stabilization failed: {path} must contain a JSON object"
        )
    return payload


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def stabilize_registry_for_snapshot(
    path: str | Path,
    *,
    max_passes: int = 16,
    repair_function=None,
) -> dict[str, Any]:
    """Converge deterministic registry repair before snapshot fingerprinting.

    This is intentionally the same fixed-point repair contract used by production's
    pre-generation registry normalization.  Persist only when authoritative repair
    actually changes the registry.  A clean second invocation therefore leaves the
    exact bytes unchanged, allowing the snapshot's strict SHA-256 registry check to
    succeed on the next run without weakening identity safety.
    """
    target = Path(path)
    payload = _read_registry(target)
    active_repair = repair_function or repair_registry_payload
    active_before = len(payload.get("stories", {}) or {})
    reports = []
    changed_any = False

    for _pass_number in range(1, max(1, int(max_passes)) + 1):
        report = active_repair(payload)
        reports.append(report)
        changed_any = changed_any or report.changed
        if not report.changed:
            break
    else:
        remaining = reports[-1].merged_story_ids if reports else {}
        raise RuntimeError(
            "Registry stabilization failed: deterministic repair did not converge "
            f"within {max_passes} passes. Last merges: {remaining}"
        )

    if changed_any:
        _atomic_write(target, payload)

    final_report = reports[-1]
    return {
        "changed": changed_any,
        "repair_passes": len(reports),
        "active_stories_before": active_before,
        "active_stories_after": len(payload.get("stories", {}) or {}),
        "records_removed": sum(r.duplicate_story_records_removed for r in reports),
        "source_records_removed": sum(r.source_story_records_removed for r in reports),
        "unified_records_removed": sum(
            r.unified_incident_story_records_removed for r in reports
        ),
        "incident_records_removed": sum(r.incident_story_records_removed for r in reports),
        "remaining_source_identity_groups": final_report.remaining_source_identity_groups,
        "remaining_unified_incident_groups": final_report.remaining_unified_incident_groups,
        "remaining_incident_identity_groups": final_report.remaining_incident_identity_groups,
        "remaining_timeline_coherence_violations": (
            final_report.remaining_timeline_coherence_violations
        ),
        "verification_clean": True,
    }
