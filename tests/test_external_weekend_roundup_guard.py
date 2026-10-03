import json
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
            self.messages = types.SimpleNamespace(create=lambda *a, **k: None)

    anthropic.Anthropic = _Anthropic
    sys.modules["anthropic"] = anthropic

os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")

from scripts import generate


def _roundup_item(**updates):
    body = (
        "Treasure Coast residents have a full slate of events to choose from this weekend, "
        "including a Bahamian Festival in Stuart, Oktoberfest in Port St. Lucie and a market. "
        "Families can attend several unrelated activities across the region. " * 8
    )
    item = {
        "headline": "GreenMarket, Bahamian Festival and Oktoberfest Headline Treasure Coast Weekend",
        "title": "GreenMarket, Bahamian Festival and Oktoberfest Headline Treasure Coast Weekend",
        "source_headline": "Fun things to do on the Treasure Coast and in Palm Beach this weekend - WPBF",
        "source_title": "Fun things to do on the Treasure Coast and in Palm Beach this weekend - WPBF",
        "body": body,
        "article_text": body,
        "summary": body,
        "source_quality": "full",
        "source_word_count": 220,
        "link": "https://www.wpbf.com/article/florida-fun-things-treasure-coast-palm-beach-weekend-county/73991347",
        "feed_url": "https://news.google.com/rss/search?q=treasure+coast+events",
    }
    item.update(updates)
    return item


def test_wpbf_recurring_weekend_roundup_is_detected_and_unpublishable():
    item = _roundup_item()
    assert generate._is_external_weekend_event_roundup(item) is True
    assert generate._publishable_article(item, hero=True) is False
    assessment = generate._category_eligibility_contract_assessment("things_to_do", item)
    assert assessment["eligible"] is False
    assert assessment["reason"] == "publisher_weekend_roundup_reserved_for_tct_guide"


def test_tct_custom_weekend_guide_is_exempt_from_roundup_guard():
    item = _roundup_item(
        headline="Looking for something to do this weekend? Here are the Top 5 local events for Oct. 3-4",
        title="Looking for something to do this weekend? Here are the Top 5 local events for Oct. 3-4",
        source_headline="",
        source_title="",
        is_custom=True,
        authoritative_custom=True,
    )
    assert generate._is_external_weekend_event_roundup(item) is False
    assert generate._publishable_article(item, hero=True) is True


def test_fetch_headlines_drops_generic_publisher_weekend_roundup_before_enrichment(monkeypatch):
    generic = {
        "title": "Fun things to do on the Treasure Coast and in Palm Beach this weekend - WPBF",
        "summary": "A list of several events across the Treasure Coast this weekend.",
        "link": "https://www.wpbf.com/article/florida-fun-things-treasure-coast-palm-beach-weekend-county/73991347",
        "published": "Fri, 02 Oct 2026 13:57:00 GMT",
        "source": {"title": "WPBF", "href": "https://www.wpbf.com"},
    }
    normal = {
        "title": "Fellsmere Rabies Alert Issued After Positive Bat Near Sonrise Apartments",
        "summary": "Health officials issued a 60-day rabies alert after a bat tested positive.",
        "link": "https://www.wpbf.com/article/example-rabies-story/12345678",
        "published": "Fri, 02 Oct 2026 13:58:00 GMT",
        "source": {"title": "WPBF", "href": "https://www.wpbf.com"},
    }

    monkeypatch.setattr(
        generate.feedparser,
        "parse",
        lambda *args, **kwargs: types.SimpleNamespace(entries=[generic, normal]),
    )
    # Avoid live fetches; the test only verifies the ingestion boundary.
    monkeypatch.setattr(generate, "fetch_article_text", lambda *args, **kwargs: "verified source text " * 80)
    rows = generate.fetch_headlines(["https://example.test/rss"], limit=10)
    titles = [row.get("title") for row in rows]
    assert generic["title"] not in titles
    assert normal["title"] in titles


def test_brand_new_permalink_overwrites_inherited_old_first_published(monkeypatch):
    monkeypatch.setattr(generate, "_now_eastern_rfc822", lambda: "Fri, 02 Oct 2026 23:05:00 -0400")
    item = {
        "headline": "A genuinely new article",
        "first_published": "Mon, 27 Jul 2026 23:15:29 -0400",
    }
    stamp = generate._stamp_brand_new_tct_publication_time(item)
    assert stamp == "Fri, 02 Oct 2026 23:05:00 -0400"
    assert item["first_published"] == stamp


def test_oct_2_wpbf_duplicate_cleanup_redirects_to_tct_weekend_guide(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    policy = {
        "schema_version": 1,
        "retirements": [
            {
                "slug": "2026-10-02-greenmarket-bahamian-festival-and-oktoberfest-headline-treasure-coast-weekend",
                "source_domain": "wpbf.com",
                "action": "canonical_redirect",
                "target_slug": "2026-10-02-treasure-coast-weekend-events-oct-3-4",
                "reason": "duplicate weekend roundup",
            }
        ],
    }
    (data_dir / "source-retirement-editor-overrides.json").write_text(json.dumps(policy), encoding="utf-8")
    articles = tmp_path / "articles"
    articles.mkdir()
    duplicate_slug = policy["retirements"][0]["slug"]
    target_slug = policy["retirements"][0]["target_slug"]
    (articles / f"{duplicate_slug}.html").write_text("<html>duplicate</html>", encoding="utf-8")
    (articles / f"{target_slug}.html").write_text("<html>canonical</html>", encoding="utf-8")
    archive = [
        {
            "slug": duplicate_slug,
            "headline": "GreenMarket, Bahamian Festival and Oktoberfest Headline Treasure Coast Weekend",
            "source_url": "https://www.wpbf.com/article/florida-fun-things-treasure-coast-palm-beach-weekend-county/73991347",
            "category_key": "things_to_do",
        },
        {
            "slug": target_slug,
            "headline": "Looking for something to do this weekend? Here are the Top 5 local events for Oct. 3-4",
            "is_custom": True,
            "authoritative_custom": True,
            "category_key": "things_to_do",
        },
    ]
    kept, redirects, report = generate.apply_source_retirement_cleanup_to_archive(
        archive, articles, tmp_path
    )
    assert [row["slug"] for row in kept] == [target_slug]
    assert report["redirect_count"] == 1
    assert redirects[0]["source_slug"] == duplicate_slug
    assert redirects[0]["target_slug"] == target_slug


def test_editor_retirement_overlay_contains_both_known_wpbf_weekend_duplicates():
    from pathlib import Path

    payload = json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "source-retirement-editor-overrides.json").read_text(encoding="utf-8")
    )
    by_slug = {row["slug"]: row for row in payload["retirements"]}
    assert by_slug[
        "2026-10-02-greenmarket-bahamian-festival-and-oktoberfest-headline-treasure-coast-weekend"
    ]["target_slug"] == "2026-10-02-treasure-coast-weekend-events-oct-3-4"
    assert by_slug[
        "2026-09-25-bacon-and-bbq-festival-at-midflorida-event-center-tops-weekend-events"
    ]["target_slug"] == "2026-09-22-treasure-coast-weekend-events-sep-26-27"
