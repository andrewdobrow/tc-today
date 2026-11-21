"""Persist the editor's Preston Lane location correction in the archive.

The archive is too large to rewrite through the GitHub Contents connector.
Apply this exact slug-scoped correction during the next ordinary newsroom run
so regenerated homepage/app teasers retain the published wording.
"""
from __future__ import annotations

import json
from pathlib import Path

SLUG = "2026-11-20-port-st-lucie-road-partially-collapses-after-flooding-as-neighbor-warns-of-growi"
OLD = "A road and nearby property in Port St. Lucie partially collapsed during historic flooding"
NEW = "A road and adjoining property off Preston Lane in Port St. Lucie partially collapsed during historic flooding"


def reconcile_archive(path: Path) -> bool:
    content = path.read_text(encoding="utf-8")
    rows = json.loads(content)
    if not isinstance(rows, list):
        raise ValueError("Archive must contain a JSON list")
    matching = [row for row in rows if isinstance(row, dict) and row.get("slug") == SLUG]
    if len(matching) != 1:
        return False  # Absent or duplicate story: do not edit unrelated content.
    teaser = str(matching[0].get("teaser") or "")
    if NEW in teaser or OLD not in teaser:
        return False  # Already corrected, or its text has evolved.
    if content.count(OLD) != 1:
        return False  # Never replace an identical phrase in another story.
    updated = content.replace(OLD, NEW, 1)
    json.loads(updated)  # Validate the edited document before writing.
    path.write_text(updated, encoding="utf-8")
    return True


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    changed = reconcile_archive(root / "archive.json")
    print("Preston Lane archive correction " + ("applied" if changed else "already handled or not applicable"))
