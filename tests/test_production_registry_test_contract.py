"""Guard against coupling live-registry regressions to mutable story IDs."""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORY_ID = re.compile(r"\bstory_\d{6}\b")
LIVE_REGISTRY_PATH = re.compile(
    r'(?:ROOT|root)\s*/\s*["\']data["\']\s*/\s*["\']editorial_story_registry\.json["\']'
)

# This migration test intentionally verifies that one historically corrupted ID
# remains quarantined. Quarantine identity is an audit artifact, not an active
# canonical-story contract.
ALLOWLIST = {
    (
        "test_persistent_story_identity_integrity.py",
        "test_repository_migration_separates_and_restores_all_three_incidents",
    )
}


def test_live_registry_tests_do_not_pin_mutable_active_story_ids():
    violations = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        if "editorial_story_registry.json" not in source:
            continue
        tree = ast.parse(source, filename=str(path))
        lines = source.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            segment = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            if not LIVE_REGISTRY_PATH.search(segment):
                continue
            ids = sorted(set(STORY_ID.findall(segment)))
            if not ids:
                continue
            if (path.name, node.name) in ALLOWLIST:
                continue
            violations.append({"file": path.name, "test": node.name, "story_ids": ids})

    assert violations == [], (
        "Tests that read the live persistent registry must assert semantic/source "
        "invariants, not mutable numeric story IDs: " + repr(violations)
    )
