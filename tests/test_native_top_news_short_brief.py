"""Regression: a canonical published short breaking article must be usable in iOS.

The site's upstream publication gate already allows source-constrained reporting
below the generic 120-word archive recovery floor.  The native feed should
respect that vetted publication without accepting invented or retired URLs.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tct_engine.top_news_app_feed import (
    build_top_news_app_feed,
    write_top_news_app_feed,
)

NOW = datetime(2026, 10, 16, 19, 0, tzinfo=timezone.utc)


def published(slug="2026-10-16-turnpike-lanes-reopen", **kwargs):
    result = {
        "slug": slug,
        "canonical_slug": slug,
        "canonical_publication_id": "publication:breaking-brief",
        "ranking_eligible": True,
        "legacy_identity_status": "identified",
        "first_published": "Fri, 16 Oct 2026 12:00:00 -0400",
        "headline": "Turnpike Lanes Reopen in Martin County After Semi Jackknifes",
        "date": "2026-10-16",
        "source_url": "https://example.com/martin-county/turnpike-lanes-reopen",
        "article_word_count": 89,
        "article_paragraph_count": 2,
    }
    result.update(kwargs)
    return result


def write_page(root, row, text="<html><head></head><body>Two real paragraphs</body></html>"):
    article = root / "articles" / (row["slug"] + ".html")
    article.parent.mkdir(parents=True, exist_ok=True)
    article.write_text(text, encoding="utf-8")


def _archive_entry_publishable(entry):
    # Mirrors the generator's generic archive recovery floor for short articles.
    return entry["article_word_count"] >= 120 and (
        entry["article_paragraph_count"] >= 2 or entry["article_word_count"] >= 180
    )


def mirror(root, row):
    return write_top_news_app_feed(
        root,
        hero_slug=row["slug"],
        top_story_slugs=[],
        homepage_other_slugs=[],
        archive=[row],
        now=NOW,
        is_publishable=_archive_entry_publishable,
    )


class NativeShortBriefParityTests(unittest.TestCase):
    def test_canonical_short_published_hero_is_accepted(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = published()
            write_page(root, row)
            feed = mirror(root, row)
            self.assertEqual(feed["hero"], {"slug": row["slug"]})
            written = json.loads((root / "data" / "top-news-app-feed.json").read_text())
            self.assertEqual(written["hero"], {"slug": row["slug"]})

    def test_missing_article_file_still_fails_closed(self):
        with TemporaryDirectory() as tmp:
            row = published()
            with self.assertRaisesRegex(ValueError, "canonical publishable archive"):
                mirror(Path(tmp), row)

    def test_absent_archive_hero_still_fails_closed(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "canonical publishable archive"):
                write_top_news_app_feed(
                    Path(tmp), hero_slug="2026-10-16-ghost", top_story_slugs=[],
                    homepage_other_slugs=[], archive=[published()], now=NOW,
                    is_publishable=_archive_entry_publishable,
                )

    def test_quarantine_retired_alias_or_redirect_cannot_bypass(self):
        bad = (
            {"identity_quarantine_reason": "identity_conflict"},
            {"exclude_from_live_recovery": True},
            {"retired_custom": True},
            {"canonical_slug": "another"},
            {"ranking_eligible": False},
            {"legacy_identity_status": "unresolved"},
            {"canonical_publication_id": ""},
            {"article_word_count": 45},
            {"article_paragraph_count": 1},
            {"source_url": ""},
        )
        for change in bad:
            with self.subTest(change=change), TemporaryDirectory() as tmp:
                root = Path(tmp)
                row = published(**change)
                write_page(root, row)
                with self.assertRaises(ValueError):
                    mirror(root, row)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = published()
            write_page(root, row, '<html><meta http-equiv="refresh" content="0;url=/other"></html>')
            with self.assertRaises(ValueError):
                mirror(root, row)

    def test_normal_prepublication_checker_still_controls_full_articles(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = published(article_word_count=200)
            write_page(root, row)
            feed = mirror(root, row)
            self.assertEqual(feed["hero"]["slug"], row["slug"])
            feed = write_top_news_app_feed(
                root, hero_slug=row["slug"], top_story_slugs=[],
                homepage_other_slugs=[], archive=[row], now=NOW,
                is_publishable=lambda e: True,
            )
            self.assertEqual(feed["hero"]["slug"], row["slug"])

    def test_other_callers_custom_checker_is_not_bypassed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = published()
            write_page(root, row)
            with self.assertRaises(ValueError):
                write_top_news_app_feed(
                    root, hero_slug=row["slug"], top_story_slugs=[],
                    homepage_other_slugs=[], archive=[row], now=NOW,
                    is_publishable=lambda e: False,
                )

    def test_pure_builder_retains_explicit_callback_contract(self):
        row = published()
        with self.assertRaises(ValueError):
            build_top_news_app_feed(
                hero_slug=row["slug"], top_story_slugs=[],
                homepage_other_slugs=[], archive=[row], now=NOW,
                is_publishable=lambda e: False,
            )


if __name__ == "__main__":
    unittest.main()
