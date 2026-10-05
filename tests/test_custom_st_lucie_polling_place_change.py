from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUSTOM = ROOT / "custom_articles.json"
HEADLINE = "St. Lucie County changes polling location for Precincts 39 and 52 for Nov. 3 election"


def _article():
    rows = json.loads(CUSTOM.read_text(encoding="utf-8"))
    matches = [row for row in rows if row.get("headline") == HEADLINE]
    assert len(matches) == 1
    return matches[0]


def test_polling_place_custom_article_contract():
    article = _article()
    assert article["slug"] == "2026-10-05-st-lucie-county-changes-polling-location-for-precincts-39-and-52-for-nov-3-election"
    assert article["category"] == "local_gov"
    assert article["category_keys"] == ["local_gov", "st_lucie"]
    assert article["county_keys"] == ["st_lucie"]
    assert article["expires"] == "2026-11-04"
    assert article["force_hero"] is False
    assert article["is_breaking"] is False


def test_polling_place_article_preserves_supplied_election_details():
    article = _article()
    body = article["body"]
    required = [
        "Lakewood Park Church, 5405 Turnpike Feeder Road in Fort Pierce",
        "10 a.m. to 6 p.m. each day from Oct. 19 through Oct. 31",
        "Lakewood Park Branch Library",
        "Renaissance Business Park, Main Office",
        "Zora Neale Hurston Library",
        "MIDFlorida Credit Union Event Center",
        "Port St. Lucie Community Center",
        "Paula A. Lewis Library",
        "Indian River State College Veterans Center of Excellence",
        "Robert E. Minsky Gym",
        "Oct. 22",
        "St. Lucie West South County Annex",
        "Dorothy J. Conrad Administration Annex",
        "Tradition Tax Collector",
        "772-462-1500",
        "https://www.stlucievotes.gov/",
    ]
    for value in required:
        assert value in body


def test_polling_place_article_uses_early_voting_image():
    article = _article()
    assert article["image_url"] == "https://treasurecoast.today/images/early-voting.webp"
