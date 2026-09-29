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
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tct_engine.editorial_snapshot import stabilize_registry_for_snapshot
from tct_engine.registry_repair import repair_registry_payload

DEFAULT_REGISTRY = ROOT / "data" / "editorial_story_registry.json"


def normalize_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, object]:
    try:
        return stabilize_registry_for_snapshot(
            path, repair_function=repair_registry_payload
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc).replace("Registry stabilization failed", "Registry preflight failed")) from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args()
    result = normalize_registry(args.registry)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
