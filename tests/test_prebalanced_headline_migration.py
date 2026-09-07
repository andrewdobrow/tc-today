from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path


def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")
        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda **kwargs: None)
        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    if "json_repair" not in sys.modules:
        json_repair = types.ModuleType("json_repair")
        json_repair.repair_json = lambda value: value
        sys.modules["json_repair"] = json_repair
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    path = Path(__file__).parents[1] / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_prebalanced_headline_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repairs_existing_turnpike_canonical_without_changing_permalink_origin(tmp_path):
    generate = _load_generate()
    slug = "2026-09-07-driver-killed-passenger-hospitalized-after-box-truck-overturns-on-floridas-turnp"
    old = "Driver killed, passenger hospitalized after box truck overturns on Florida's Turnpike near mile marker 166 in St. Lucie County"
    new = "Driver killed, passenger hospitalized in box truck crash on Florida's Turnpike in St. Lucie County"
    (tmp_path / "articles").mkdir()
    (tmp_path / "data").mkdir()
    archive = [{
        "slug": slug,
        "headline": old,
        "permalink_origin_headline": old,
        "teaser": "Body metadata remains untouched.",
    }]
    (tmp_path / "archive.json").write_text(json.dumps(archive), encoding="utf-8")
    page = (
        f'<title>{old} | Treasure Coast Today</title>'
        f'<script type="application/ld+json">'
        + json.dumps({"@context": "https://schema.org", "@type": "NewsArticle", "headline": old[:110]})
        + '</script>'
        f'<h1>{old}</h1><p>Article body stays the same.</p>'
    )
    article_path = tmp_path / "articles" / f"{slug}.html"
    article_path.write_text(page, encoding="utf-8")

    report = generate._repair_prebalanced_overlong_headlines(tmp_path)
    assert report["repaired_count"] == 1
    repaired = json.loads((tmp_path / "archive.json").read_text())
    assert repaired[0]["headline"] == new
    assert repaired[0]["permalink_origin_headline"] == old
    repaired_page = article_path.read_text()
    assert new in repaired_page
    assert old not in repaired_page
    assert "Article body stays the same." in repaired_page
    assert json.loads(
        repaired_page.split('<script type="application/ld+json">', 1)[1].split('</script>', 1)[0]
    )["headline"] == new

    # Exact-old-headline guard makes the migration idempotent.
    second = generate._repair_prebalanced_overlong_headlines(tmp_path)
    assert second["repaired_count"] == 0


def test_repair_map_preserves_meaningful_locations():
    generate = _load_generate()
    for rule in generate._PREBALANCED_OVERLONG_HEADLINE_REPAIRS.values():
        assert len(rule["new"]) <= 110
    turnpike = generate._PREBALANCED_OVERLONG_HEADLINE_REPAIRS[
        "2026-09-07-driver-killed-passenger-hospitalized-after-box-truck-overturns-on-floridas-turnp"
    ]["new"]
    assert "Florida's Turnpike" in turnpike
    assert "St. Lucie County" in turnpike
    dog = generate._PREBALANCED_OVERLONG_HEADLINE_REPAIRS[
        "2026-09-06-st-lucie-county-deputies-investigate-man-who-shot-dog-during-driveway-confrontat"
    ]["new"]
    assert "Fort Pierce" in dog
    assert "St. Lucie County" in dog
