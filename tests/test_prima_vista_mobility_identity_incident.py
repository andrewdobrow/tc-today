import importlib
import json
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLUG = "2026-09-21-port-st-lucie-advances-22-billion-2050-mobility-plan-with-phased-fee-hikes"
GOOD = "Port St. Lucie's $2.2 billion mobility plan aims to tackle traffic and keep up with growth"

def load_generate():
    if "feedparser" not in sys.modules:
        module = types.ModuleType("feedparser")
        module.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = module
    if "anthropic" not in sys.modules:
        module = types.ModuleType("anthropic")
        module.Anthropic = lambda *args, **kwargs: None
        sys.modules["anthropic"] = module
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")

def test_prima_vista_followup_cannot_overwrite_mobility_plan():
    g = load_generate()
    incoming = {
        "headline": "Port St. Lucie Residents Push Back on Prima Vista Boulevard Safety Plan",
        "date": "2026-10-15",
        "source_url": "https://cbs12.com/news/local/port-st-lucie-residents-weigh-in-on-proposed-prima-vista-boulevard-safety-changes",
    }
    canonical = {
        "slug": SLUG,
        "headline": GOOD,
        "date": "2026-09-21",
        "editorial_story_id": "story_014367",
    }
    evidence = g._cross_source_same_event_evidence(incoming, canonical)
    assert evidence["matched"] is False
    assert evidence["write_authorized"] is False
    assert evidence["reason"] == "contradictory_named_transport_projects"

def test_prima_vista_match_not_rejected_as_different_project():
    g = load_generate()
    incoming = {
        "headline": "Port St. Lucie Residents Push Back on Prima Vista Boulevard Safety Plan",
        "date": "2026-10-15",
    }
    canonical = {
        "slug": "2026-10-15-st-lucie-county-proposes-raised-median-for-prima-vista-boulevard-after-578-crash",
        "headline": "St. Lucie County Proposes Raised Median for Prima Vista Boulevard After 578 Crashes",
        "date": "2026-10-15",
    }
    evidence = g._cross_source_same_event_evidence(incoming, canonical)
    assert evidence["reason"] != "contradictory_named_transport_projects"

def test_september_article_and_archive_identity_restored():
    page = (ROOT / "articles" / (SLUG + ".html")).read_text()
    archive = json.loads((ROOT / "archive.json").read_text())
    rows = [row for row in archive if row.get("slug") == SLUG]
    assert len(rows) == 1
    assert rows[0]["headline"] == GOOD
    assert rows[0]["editorial_story_id"] == "story_014367"
    assert "mobility-plan-for-future-growth" in rows[0]["source_url"]
    import html
    import re
    match = re.search(r"<h1\b[^>]*>(.*?)</h1>", page, re.I | re.S)
    assert match is not None
    headline = html.unescape(re.sub(r"<[^>]+>", "", match.group(1)))
    assert " ".join(headline.split()) == GOOD
    assert "Residents Push Back on Prima Vista Boulevard Safety Plan" not in page.split("</h1>")[0]


def test_actual_corrupted_slug_routes_to_correct_project():
    g = load_generate()
    incoming = {
        "slug": SLUG,
        "headline": "Port St. Lucie Residents Push Back on Prima Vista Boulevard Safety Plan",
        "source_url": (
            "https://cbs12.com/news/local/"
            "port-st-lucie-residents-weigh-in-on-proposed-"
            "prima-vista-boulevard-safety-changes"
        ),
        "editorial_story_id": "story_021559",
        "date": "2026-09-21",
    }
    mobility = {
        "slug": SLUG,
        "headline": GOOD,
        "source_url": (
            "https://cbs12.com/newsletter/"
            "port-st-lucie-weighs-mobility-plan-for-future-growth"
        ),
        "editorial_story_id": "story_014367",
        "date": "2026-09-21",
    }
    prima = {
        "slug": "2026-10-15-st-lucie-county-proposes-raised-median-for-prima-vista-boulevard-after-578-crash",
        "headline": "St. Lucie County Proposes Raised Median for Prima Vista Boulevard After 578 Crashes",
        "date": "2026-10-15",
    }
    wrong = g._cross_source_same_event_evidence(incoming, mobility)
    correct = g._cross_source_same_event_evidence(incoming, prima)
    assert wrong["write_authorized"] is False
    assert wrong["reason"] == "contradictory_named_transport_projects"
    assert correct["reason"] != "contradictory_named_transport_projects"
