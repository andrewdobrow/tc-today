import json
import os
import sys
import types
from pathlib import Path

import pytest

if "feedparser" not in sys.modules:
    feedparser = types.ModuleType("feedparser")
    feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
    sys.modules["feedparser"] = feedparser
if "anthropic" not in sys.modules:
    anthropic = types.ModuleType("anthropic")

    class _Anthropic:
        def __init__(self, *args, **kwargs):
            self.messages = types.SimpleNamespace(create=lambda *a, **k: None)

    anthropic.Anthropic = _Anthropic
    sys.modules["anthropic"] = anthropic
os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")

from scripts import generate


def _wptv_promo():
    text = (
        "WPTV will hold a community education meetup at House of Music PSL in Port St. Lucie. "
        "The event is part of WPTV's Let's Hear It series focused on education. "
    ) * 12
    return {
        "title": "WPTV brings 'Let's Hear It' education focus to West Palm Beach and Port St. Lucie Aug. 19-20",
        "headline": "WPTV holds education meetup in Port St. Lucie on August 20",
        "source_title": "WPTV brings 'Let's Hear It' education focus to West Palm Beach and Port St. Lucie Aug. 19-20",
        "source_headline": "WPTV brings 'Let's Hear It' education focus to West Palm Beach and Port St. Lucie Aug. 19-20",
        "source_url": "https://www.wptv.com/community/lets-hear-it/wptv-brings-lets-hear-it-education-focus-to-west-palm-beach-and-port-st-lucie-aug-19-20",
        "link": "https://www.wptv.com/community/lets-hear-it/wptv-brings-lets-hear-it-education-focus-to-west-palm-beach-and-port-st-lucie-aug-19-20",
        "summary": text,
        "article_text": text,
        "source_quality": "full",
        "source_word_count": 150,
    }


def test_exact_wptv_branded_meetup_is_rejected_before_generation():
    item = _wptv_promo()
    assert generate._is_publisher_self_promotion(item) is True
    assert generate._source_candidate_publishable(item) is False


def test_wptv_reporting_on_real_local_news_is_not_blocked():
    item = {
        "title": "Fort Pierce police arrest suspect after armed robbery",
        "source_title": "Fort Pierce police arrest suspect after armed robbery",
        "source_url": "https://www.wptv.com/news/region-st-lucie-county/fort-pierce/armed-robbery-arrest",
        "article_text": ("Fort Pierce police arrested a suspect after an armed robbery investigation. " * 20),
        "source_quality": "full",
        "source_word_count": 180,
    }
    assert generate._is_publisher_self_promotion(item) is False
    assert generate._source_candidate_publishable(item) is True


def test_exact_wptv_meetup_archive_shape_is_publisher_self_promotion():
    # Keep this regression deterministic. Production preflight/generation may have
    # already purged the bad live row before pytest runs, so the test must not depend
    # on mutable archive.json state. This fixture mirrors the published archive row.
    row = {
        "slug": "2026-08-11-wptv-holds-education-meetup-in-port-st-lucie-on-august-20",
        "headline": "WPTV holds education meetup in Port St. Lucie on August 20",
        "teaser": (
            "WPTV will host a community education meetup at House of Music PSL "
            "in Port St. Lucie on Thursday, August 20."
        ),
        "category_key": "st_lucie",
        "source_url": (
            "https://www.wptv.com/community/lets-hear-it/"
            "wptv-brings-lets-hear-it-education-focus-to-west-palm-beach-and-port-st-lucie-aug-19-20"
        ),
        "source_headline": (
            "WPTV brings 'Let's Hear It' education focus to West Palm Beach "
            "and Port St. Lucie Aug. 19-20"
        ),
        "article_word_count": 124,
        "article_paragraph_count": 3,
    }
    assert generate._is_publisher_self_promotion(row) is True
    assert generate._archive_entry_publishable(row) is False


def test_wptv_attribution_suffix_does_not_block_city_hosted_event_reporting():
    item = {
        "title": "Port St. Lucie hosts community safety forum - WPTV",
        "source_title": "Port St. Lucie hosts community safety forum - WPTV",
        "source_headline": "Port St. Lucie hosts community safety forum - WPTV",
        "source_url": "https://www.wptv.com/news/st-lucie-county/port-st-lucie-hosts-community-safety-forum",
        "article_text": (
            "The City of Port St. Lucie will host a community event about emergency "
            "preparedness. City officials and residents will take part in the forum. "
        ) * 10,
        "source_quality": "full",
        "source_word_count": 180,
    }
    assert generate._is_publisher_self_promotion(item) is False
    assert generate._source_candidate_publishable(item) is True


def test_existing_publisher_promo_is_purged_to_noindex_archive_redirect(tmp_path: Path):
    item = _wptv_promo()
    item.update({
        "slug": "2026-08-11-wptv-holds-education-meetup-in-port-st-lucie-on-august-20",
        "category_key": "st_lucie",
        "article_word_count": 150,
        "article_paragraph_count": 3,
    })
    articles = tmp_path / "articles"
    articles.mkdir()
    kept, report = generate._purge_nonstory_archive_entries([item], articles, tmp_path)
    assert kept == []
    assert report["removed_count"] == 1
    assert report["removed"][0]["reason"] == "publisher_self_promotion"
    redirect = (articles / f"{item['slug']}.html").read_text()
    assert 'name="robots" content="noindex,follow"' in redirect
    assert "/archive.html" in redirect


def test_final_live_image_contract_repairs_hero_after_late_reselection(tmp_path: Path, monkeypatch):
    hero = {
        "headline": "Fort Pierce has no legal options to block Causeway Cove development on South Hutchinson Island",
        "category_key": "local_gov",
        "image_url": "",
    }
    categories = [{
        "category_key": "local_gov",
        "category_label": "Local Government",
        "hero": hero,
        "cards": [],
    }]
    top = {"category_key": "all", "hero": hero, "cards": []}
    monkeypatch.setattr(
        generate,
        "get_fallback_image",
        lambda *a, **k: ("https://treasurecoast.today/images/editorial/topics/roads-transportation/traffic.webp", ""),
    )
    report = generate.ensure_final_live_visual_images(categories, top, tmp_path)
    assert report["status"] == "passed"
    assert hero["image_url"].endswith("/traffic.webp")
    saved = json.loads((tmp_path / "data" / "final-live-image-contract.json").read_text())
    assert saved["failure_count"] == 0


def test_final_live_image_contract_fails_closed_when_no_image_can_be_found(tmp_path: Path, monkeypatch):
    hero = {"headline": "Local story", "category_key": "local_gov", "image_url": ""}
    categories = [{"category_key": "local_gov", "hero": hero, "cards": []}]
    top = {"hero": hero}
    monkeypatch.setattr(generate, "get_fallback_image", lambda *a, **k: ("", ""))
    with pytest.raises(RuntimeError, match="Final live image contract FAILED"):
        generate.ensure_final_live_visual_images(categories, top, tmp_path)
