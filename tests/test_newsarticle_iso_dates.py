"""Regression tests for Google-compatible article structured-data dates."""
import json
import re
from datetime import datetime

import pytest

from scripts.build_audience_features import (
    _ensure_newsarticle_schema,
    _iso8601_article_date,
)


def _article_jsonld(html):
    return json.loads(re.search(
        r'<script type="application/ld\\+json">([^<]+)</script>', html
    ).group(1))


@pytest.mark.parametrize("source,expected", [
    ("Wed, 11 Nov 2026 14:47:39 -0500", "2026-11-11T14:47:39-05:00"),
    ("2026-11-11T14:47:39-05:00", "2026-11-11T14:47:39-05:00"),
    ("2026-11-11T19:47:39+00:00", "2026-11-11T14:47:39-05:00"),
    ("2026-07-01", "2026-07-01T00:00:00-04:00"),
])
def test_article_timestamp_preserves_instant_and_is_iso8601(source, expected):
    actual = _iso8601_article_date(source)
    assert actual == expected
    assert datetime.fromisoformat(actual).utcoffset() is not None


def test_existing_newsarticle_dates_are_rewritten_without_changing_other_schema():
    old = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": "Test",
        "datePublished": "Wed, 11 Nov 2026 14:47:39 -0500",
        "dateModified": "Wed, 11 Nov 2026 15:00:01 -0500",
        "isAccessibleForFree": True,
    }
    page = '<html><head><script type="application/ld+json">' + json.dumps(old) + '</script></head><body></body></html>'
    entry = {"slug": "test-story", "headline": "Test", "teaser": "Summary", "date": "2026-11-11"}
    updated = _ensure_newsarticle_schema(page, entry)
    schema = _article_jsonld(updated)
    assert schema["datePublished"] == "2026-11-11T14:47:39-05:00"
    assert schema["dateModified"] == "2026-11-11T15:00:01-05:00"
    assert schema["isAccessibleForFree"] is True
    assert _ensure_newsarticle_schema(updated, entry) == updated


def test_new_newsarticle_schema_dates_are_iso8601():
    entry = {
        "slug": "new-test-story",
        "headline": "New story",
        "teaser": "Summary",
        "first_published": "Wed, 11 Nov 2026 14:47:39 -0500",
        "canonical_last_material_update_at": "2026-11-11T15:05:00-05:00",
    }
    page = _ensure_newsarticle_schema("<html><head></head><body></body></html>", entry)
    schema = _article_jsonld(page)
    assert schema["datePublished"] == "2026-11-11T14:47:39-05:00"
    assert schema["dateModified"] == "2026-11-11T15:05:00-05:00"
