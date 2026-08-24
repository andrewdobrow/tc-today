from __future__ import annotations

import importlib
import os
import sys
import types


def _load_generate_module():
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
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def test_hometown_is_removed_from_live_full_text_and_google_recovery_allowlists():
    generate = _load_generate_module()
    assert "hometownnewstc.com" not in generate.FULL_TEXT_DOMAINS
    assert "hometown news" not in generate.TRUSTED_AGGREGATOR_PUBLISHERS
    assert "hometownnewstc.com" in generate.EXCLUDED_SOURCE_DOMAINS


def test_direct_hometown_entry_is_rejected_by_source_policy():
    generate = _load_generate_module()
    entry = {
        "title": "Indian River County creates Attainable Housing Trust to support development",
        "link": "https://www.hometownnewstc.com/news/indian_river/attainable-housing-trust/article_example.html",
        "source": {"title": "Hometown News", "href": "https://www.hometownnewstc.com"},
    }

    assert generate._is_excluded_source_entry(
        entry,
        title=entry["title"],
        link=entry["link"],
    ) is True


def test_google_news_hometown_wrapper_is_rejected_without_resolving_publisher_url():
    generate = _load_generate_module()
    entry = {
        "title": "Martin County deputy stops $600,000 gold bar scam targeting senior - Hometown News",
        "link": "https://news.google.com/rss/articles/CBMi-hometown-stale?oc=5",
        "source": {"title": "Hometown News Treasure Coast", "href": "https://www.hometownnewstc.com"},
    }

    assert generate._is_excluded_source_entry(
        entry,
        title=entry["title"],
        link=entry["link"],
    ) is True


def test_hometown_is_filtered_before_title_dedupe_so_fresher_duplicate_title_can_survive(monkeypatch):
    generate = _load_generate_module()
    shared_title = "Indian River County creates Attainable Housing Trust to support development"
    hometown = {
        "title": shared_title,
        "summary": "A stale republication of an older local government story.",
        "link": "https://www.hometownnewstc.com/news/indian_river/attainable-housing-trust/article_example.html",
        "published": "Sat, 22 Aug 2026 21:00:00 GMT",
        "source": {"title": "Hometown News", "href": "https://www.hometownnewstc.com"},
    }
    fresher_legitimate_source = {
        "title": shared_title,
        "summary": "Fresh reporting from another publisher on the same headline.",
        "link": "https://example.com/fresh-attainable-housing-trust",
        "published": "Sat, 22 Aug 2026 20:59:00 GMT",
        "source": {"title": "Example Local", "href": "https://example.com"},
    }

    monkeypatch.setattr(
        generate.feedparser,
        "parse",
        lambda *args, **kwargs: types.SimpleNamespace(entries=[hometown, fresher_legitimate_source]),
    )

    rows = generate.fetch_headlines(["https://example.test/rss"], limit=10)

    assert len(rows) == 1
    assert rows[0]["link"] == fresher_legitimate_source["link"]
    assert rows[0]["title"] == shared_title


def test_hometown_reference_in_normal_headline_text_is_not_blocked_without_publisher_identity():
    generate = _load_generate_module()
    entry = {
        "title": "Local museum opens Hometown News exhibit",
        "link": "https://example.com/local-museum-exhibit",
        "source": {"title": "Example Local", "href": "https://example.com"},
    }

    assert generate._is_excluded_source_entry(
        entry,
        title=entry["title"],
        link=entry["link"],
    ) is False


def _write_source_retirement_policy(root):
    import json

    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "source-retirement-cleanup.json").write_text(
        json.dumps({
            "schema_version": 1,
            "retirements": [
                {
                    "slug": "2026-08-22-martin-county-deputy-stops-600000-gold-bar-scam-targeting-senior",
                    "source_domain": "hometownnewstc.com",
                    "action": "canonical_redirect",
                    "target_slug": "2026-08-13-martin-county-deputies-save-senior-from-600000-gold-bar-scam",
                    "reason": "confirmed stale Hometown duplicate",
                },
                {
                    "slug": "2026-08-22-indian-river-county-creates-attainable-housing-trust-to-support-development",
                    "source_domain": "hometownnewstc.com",
                    "action": "retire",
                    "target_path": "/indian_river.html",
                    "reason": "confirmed stale Hometown republication",
                },
                {
                    "slug": "2026-08-22-vero-beach-man-arrested-on-attempted-murder-charge-after-birthday-party-assault",
                    "source_domain": "hometownnewstc.com",
                    "action": "retire_corrected_record",
                    "correction_date": "Aug. 24, 2026",
                    "correction_note": "An earlier version of this article incorrectly identified the accused's residential address. The article has been corrected to reflect the 5000 block of 33rd Avenue in Vero Beach.",
                    "replacements": [
                        {"from": "4900 block of Corsica Square", "to": "5000 block of 33rd Avenue"},
                        {"from": "Corsica Square", "to": "33rd Avenue"},
                    ],
                    "forbidden_terms": ["Corsica Square", "4900 block of Corsica Square"],
                    "reason": "confirmed stale Hometown arrest republication with corrected address",
                },
            ],
        }),
        encoding="utf-8",
    )


def test_legacy_hometown_cleanup_redirects_gold_duplicate_and_retires_stale_housing(tmp_path):
    generate = _load_generate_module()
    _write_source_retirement_policy(tmp_path)
    articles = tmp_path / "articles"
    articles.mkdir()

    gold_canonical = {
        "slug": "2026-08-13-martin-county-deputies-save-senior-from-600000-gold-bar-scam",
        "headline": "Martin County deputies save senior from $600,000 gold bar scam",
        "source_url": "https://cbs12.com/news/example-gold-scam",
        "editorial_story_id": "story_003613",
    }
    gold_stale = {
        "slug": "2026-08-22-martin-county-deputy-stops-600000-gold-bar-scam-targeting-senior",
        "headline": "Martin County deputy stops $600,000 gold bar scam targeting senior",
        "source_url": "https://www.hometownnewstc.com/news/martin/stale-gold.html",
        "editorial_story_id": "story_005316",
    }
    housing_stale = {
        "slug": "2026-08-22-indian-river-county-creates-attainable-housing-trust-to-support-development",
        "headline": "Indian River County creates Attainable Housing Trust to support development",
        "source_url": "https://www.hometownnewstc.com/news/indian_river/stale-housing.html",
        "editorial_story_id": "story_005299",
    }
    valid_old_hometown = {
        "slug": "2026-08-18-port-st-lucie-to-reconsider-led-sign-rules-after-church-request",
        "headline": "Port St. Lucie to reconsider LED sign rules after church request",
        "source_url": "https://www.hometownnewstc.com/news/st_lucie/legitimate-story.html",
        "editorial_story_id": "story_legit",
    }

    cleaned, redirects, report = generate.apply_source_retirement_cleanup_to_archive(
        [gold_canonical, gold_stale, housing_stale, valid_old_hometown],
        articles,
        tmp_path,
    )

    slugs = {row["slug"] for row in cleaned}
    assert gold_canonical["slug"] in slugs
    assert valid_old_hometown["slug"] in slugs
    assert gold_stale["slug"] not in slugs
    assert housing_stale["slug"] not in slugs
    assert report["retired_count"] == 2
    assert report["redirect_count"] == 1
    assert report["mismatch_count"] == 0
    assert redirects == [{
        "source_slug": gold_stale["slug"],
        "source_headline": gold_stale["headline"],
        "target_slug": gold_canonical["slug"],
        "target_headline": gold_canonical["headline"],
        "story_stage": "source-retirement-cleanup",
        "match_confidence": 100,
        "canonical_is_custom": False,
        "editorial_story_id": "story_003613",
        "reason": "confirmed stale Hometown duplicate",
    }]

    housing_page = (articles / f"{housing_stale['slug']}.html").read_text(encoding="utf-8")
    assert 'noindex,nofollow' in housing_page
    assert '/indian_river.html' in housing_page


def test_legacy_hometown_cleanup_is_fail_safe_on_source_domain_mismatch(tmp_path):
    generate = _load_generate_module()
    _write_source_retirement_policy(tmp_path)
    articles = tmp_path / "articles"
    articles.mkdir()
    housing_slug = "2026-08-22-indian-river-county-creates-attainable-housing-trust-to-support-development"
    row = {
        "slug": housing_slug,
        "headline": "Indian River County creates Attainable Housing Trust to support development",
        "source_url": "https://example.com/not-hometown",
    }

    cleaned, redirects, report = generate.apply_source_retirement_cleanup_to_archive(
        [row], articles, tmp_path
    )

    assert cleaned == [row]
    assert redirects == []
    assert report["retired_count"] == 0
    assert report["mismatch_count"] == 1
    assert not (articles / f"{housing_slug}.html").exists()


def test_source_retirement_live_filter_removes_only_explicit_tombstone(tmp_path):
    generate = _load_generate_module()
    _write_source_retirement_policy(tmp_path)
    housing_slug = "2026-08-22-indian-river-county-creates-attainable-housing-trust-to-support-development"
    good_slug = "2026-08-18-port-st-lucie-to-reconsider-led-sign-rules-after-church-request"
    categories = [{
        "category_key": "local_gov",
        "hero": {
            "headline": "Indian River County creates Attainable Housing Trust to support development",
            "_archived_slug": housing_slug,
        },
        "cards": [{
            "headline": "Port St. Lucie to reconsider LED sign rules after church request",
            "_archived_slug": good_slug,
            "source_url": "https://www.hometownnewstc.com/news/st_lucie/legitimate-story.html",
        }],
    }]

    removed = generate.apply_source_retirements_to_live(
        categories, output_root=tmp_path
    )

    assert removed == 1
    assert categories[0]["hero"]["_archived_slug"] == good_slug
    assert categories[0]["cards"] == []


def test_source_retirement_archive_view_never_returns_tombstoned_housing_but_keeps_other_hometown(tmp_path):
    generate = _load_generate_module()
    _write_source_retirement_policy(tmp_path)
    housing_slug = "2026-08-22-indian-river-county-creates-attainable-housing-trust-to-support-development"
    good_slug = "2026-08-18-port-st-lucie-to-reconsider-led-sign-rules-after-church-request"
    archive = [
        {"slug": housing_slug, "source_url": "https://www.hometownnewstc.com/news/indian_river/stale.html"},
        {"slug": good_slug, "source_url": "https://www.hometownnewstc.com/news/st_lucie/good.html"},
    ]

    filtered = generate._filter_source_retirement_archive_view(archive, tmp_path)

    assert [row["slug"] for row in filtered] == [good_slug]


def test_stale_hometown_smith_article_is_corrected_then_retired_as_noindex_record(tmp_path):
    generate = _load_generate_module()
    _write_source_retirement_policy(tmp_path)
    articles = tmp_path / "articles"
    articles.mkdir()
    slug = "2026-08-22-vero-beach-man-arrested-on-attempted-murder-charge-after-birthday-party-assault"
    page = articles / f"{slug}.html"
    page.write_text(
        """<!doctype html>
<html><head><title>Vero Beach man arrested</title></head><body>
<article>
<h1 class=\"article-headline\">Vero Beach man arrested on attempted murder charge after birthday party assault</h1>
<div class=\"article-body\"><p>Collin Ryan Smith, 25, of the 4900 block of Corsica Square in Vero Beach, was arrested.</p>
<p>Neighbors on Corsica Square were not part of the alleged incident.</p></div>
<div class=\"article-share\"></div>
</article></body></html>""",
        encoding="utf-8",
    )
    stale = {
        "slug": slug,
        "headline": "Vero Beach man arrested on attempted murder charge after birthday party assault",
        "source_url": "https://www.hometownnewstc.com/news/indian_river/stale-smith.html",
        "editorial_story_id": "story_stale_smith",
    }

    cleaned, redirects, report = generate.apply_source_retirement_cleanup_to_archive(
        [stale], articles, tmp_path
    )

    assert cleaned == []
    assert redirects == []
    assert report["retired_count"] == 1
    assert report["corrected_record_count"] == 1
    assert report["mismatch_count"] == 0
    corrected = page.read_text(encoding="utf-8")
    assert "5000 block of 33rd Avenue" in corrected
    assert "Corsica Square" not in corrected
    assert "4900 block" not in corrected
    assert "Correction — Aug. 24, 2026:" in corrected
    assert "incorrectly identified the accused&#x27;s residential address" in corrected
    assert 'meta name="robots" content="noindex,follow"' in corrected
    assert "http-equiv=\"refresh\"" not in corrected


def test_corrected_record_retirement_fails_safe_if_wrong_source_domain(tmp_path):
    generate = _load_generate_module()
    _write_source_retirement_policy(tmp_path)
    articles = tmp_path / "articles"
    articles.mkdir()
    slug = "2026-08-22-vero-beach-man-arrested-on-attempted-murder-charge-after-birthday-party-assault"
    page = articles / f"{slug}.html"
    original = '<html><head></head><body><div class="article-body">4900 block of Corsica Square</div></body></html>'
    page.write_text(original, encoding="utf-8")
    row = {
        "slug": slug,
        "headline": "Vero Beach man arrested on attempted murder charge after birthday party assault",
        "source_url": "https://example.com/not-hometown",
    }

    cleaned, redirects, report = generate.apply_source_retirement_cleanup_to_archive(
        [row], articles, tmp_path
    )

    assert cleaned == [row]
    assert redirects == []
    assert report["retired_count"] == 0
    assert report["corrected_record_count"] == 0
    assert report["mismatch_count"] == 1
    assert page.read_text(encoding="utf-8") == original
