"""Keep mutable production registry state out of deterministic pytest regressions.

Historical production bugs belong in frozen/synthetic fixtures.  The current
``data/editorial_story_registry.json`` is runtime state and legitimately changes
as deterministic consolidation, compaction, quarantine, and canonical selection
run.  CI verifies that live state is deterministically repairable in a scratch
copy before pytest; production repairs the real registry before generation.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE_REGISTRY_PATH = re.compile(
    r'(?:ROOT|root)\s*/\s*["\']data["\']\s*/\s*["\']editorial_story_registry\.json["\']'
)


def test_pytest_regressions_do_not_read_mutable_live_registry():
    violations = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        source = path.read_text(encoding="utf-8")
        if "editorial_story_registry.json" not in source:
            continue
        tree = ast.parse(source, filename=str(path))
        lines = source.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            segment = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            if LIVE_REGISTRY_PATH.search(segment):
                violations.append({"file": path.name, "test": node.name})

    assert violations == [], (
        "Pytest may not depend on mutable production registry contents. "
        "Capture the production bug in a frozen/synthetic fixture and validate "
        "the live registry only through the workflow repairability preflight: "
        + repr(violations)
    )
