import os
import sys
import types


if "feedparser" not in sys.modules:
    feedparser = types.ModuleType("feedparser")
    feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
    sys.modules["feedparser"] = feedparser

if "anthropic" not in sys.modules:
    anthropic = types.ModuleType("anthropic")

    class _Anthropic:
        def __init__(self, *args, **kwargs):
            self.messages = types.SimpleNamespace(
                create=lambda *a, **k: (_ for _ in ()).throw(
                    RuntimeError("offline test")
                )
            )

    anthropic.Anthropic = _Anthropic
    sys.modules["anthropic"] = anthropic

os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")

from scripts import generate


def _item(headline: str, body: str = "") -> dict:
    return {
        "title": headline,
        "headline": headline,
        "source_title": headline,
        "body": body,
        "summary": body,
        "source_quality": "full",
        "feed_url": "https://www.wptv.com/news/region-indian-river-county.rss",
    }


def test_sports_gate_rejects_local_museum_exhibition():
    item = _item(
        "Vero Beach Museum of Art opens new Jill Nathanson exhibition",
        "The Vero Beach museum will open an exhibition for visitors.",
    )
    assert generate._sports_relevance_evidence(item) is False
    assert generate._hero_eligible("sports", item) is False


def test_sports_gate_rejects_police_back_to_school_event():
    item = _item(
        "Sebastian Police to host Back To School Fun Day at Riverview Park",
        "The Sebastian Police Department will distribute school supplies at the community event.",
    )
    assert generate._sports_relevance_evidence(item) is False
    assert generate._hero_eligible("sports", item) is False


def test_sports_gate_accepts_mets_pitching_award():
    item = _item(
        "St. Lucie Mets pitcher Conner Ware named FSL Pitcher of the Week",
        "The Florida State League honored the pitcher after seven scoreless innings and 12 strikeouts.",
    )
    assert generate._sports_relevance_evidence(item) is True
    assert generate._hero_eligible("sports", item) is True


def test_sports_gate_accepts_local_high_school_result():
    item = _item(
        "Vero Beach wins district football championship",
        "The Vero Beach football team won the championship game Friday night.",
    )
    assert generate._sports_relevance_evidence(item) is True
    assert generate._hero_eligible("sports", item) is True


def test_category_hero_prefers_tct_first_published_time():
    item = {
        "headline": "New Treasure Coast story",
        "link": "https://publisher.example/story",
        "published": "12:00 AM ET",
        "published_raw": "Mon, 27 Jul 2026 00:00:00 -0400",
    }
    archive = [
        {
            "headline": "New Treasure Coast story",
            "slug": "2026-07-27-new-treasure-coast-story",
            "source_url": "https://publisher.example/story",
            "first_published": "Mon, 27 Jul 2026 15:45:00 -0400",
        }
    ]
    display = generate._format_category_hero_timestamp(item, archive)
    assert "3:45 PM ET" in display
    assert "12:00 AM" not in display


def test_category_hero_date_only_value_never_claims_midnight():
    item = {
        "headline": "Legacy story",
        "published_raw": "2026-07-27",
        "published": "12:00 AM ET",
    }
    display = generate._format_category_hero_timestamp(item, [])
    assert display == "Jul 27, 2026"
    assert "12:00 AM" not in display


def test_category_hero_synthetic_midnight_becomes_date_label():
    item = {
        "headline": "Feed date placeholder",
        "published_raw": "Mon, 27 Jul 2026 00:00:00 -0400",
        "published": "12:00 AM ET",
    }
    display = generate._format_category_hero_timestamp(item, [])
    assert display == "Jul 27, 2026"
