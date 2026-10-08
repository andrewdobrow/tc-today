from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUSTOM = ROOT / "custom_articles.json"
RETIRED_CUSTOM_ID = "st-lucie-precincts-39-52-polling-place-change-2026-11-03"


def test_polling_place_custom_article_is_retired_from_active_queue():
    rows = json.loads(CUSTOM.read_text(encoding="utf-8"))
    assert all(row.get("custom_id") != RETIRED_CUSTOM_ID for row in rows)
