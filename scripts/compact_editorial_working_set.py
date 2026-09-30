#!/usr/bin/env python3
"""Bound TCT's live story registry and editorial replay state before generation."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tct_engine.registry_repair import REPAIR_VERSION
from tct_engine.working_set import (
    DEFAULT_HOT_DAYS,
    compact_editorial_state_working_set,
    compact_registry_working_set,
)

DEFAULT_REGISTRY = ROOT / "data" / "editorial_story_registry.json"
DEFAULT_STATE = ROOT / "data" / "editorial_state.json"
DEFAULT_HISTORY = ROOT / "data" / "editorial_story_history"


def _hot_days_from_env() -> int:
    raw = os.environ.get("TCT_STORY_HOT_DAYS", str(DEFAULT_HOT_DAYS)).strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_HOT_DAYS


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("registry", "state", "all"), default="all")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--hot-days", type=int, default=_hot_days_from_env())
    parser.add_argument("--now", type=str, default="")
    args = parser.parse_args()

    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
    output: dict[str, object] = {}
    if args.phase in {"registry", "all"}:
        output["registry"] = compact_registry_working_set(
            args.registry,
            history_path=args.history,
            now=now,
            hot_days=args.hot_days,
        )
    if args.phase in {"state", "all"}:
        output["state"] = compact_editorial_state_working_set(
            args.state,
            registry_path=args.registry,
            now=now,
            hot_days=args.hot_days,
            repair_version=REPAIR_VERSION,
        )
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
