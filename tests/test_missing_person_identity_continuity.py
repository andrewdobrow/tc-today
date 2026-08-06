from __future__ import annotations

import importlib
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

from tct_engine import EditorialAction, EditorialEngine
from tct_engine.unified_incident_identity import (
    build_unified_incident_evidence,
    compare_unified_incident_evidence,
    unified_incident_components,
)

CANONICAL = (
    "2026-08-06-martin-county-sheriffs-office-seeks-public-help-finding-"
    "missing-14-year-old-auti"
)
DUPLICATE = (
    "2026-08-06-martin-county-deputies-search-for-missing-autistic-teen-"
    "last-seen-in-palm-city"
)
WPBF_URL = (
    "https://www.wpbf.com/article/florida-palm-city-missing-14-year-old-"
    "autistic-boy/73360714"
)
WPEC_URL = (
    "https://cbs12.com/news/local/martin-county-deputies-seek-autistic-"
    "missing-14-year-old-boy-last-seen-grand-oaks-living-facility-"
    "coquina-cove-florida-news"
)
WPBF_TITLE = (
    "Authorities need help finding 14-year-old autistic boy last seen in "
    "Palm City - WPBF"
)
WPEC_TITLE = (
    "Martin County deputies seek help finding missing autistic teen last "
    "seen in Palm City - WPEC"
)


def _load_generate_module():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")
        anthropic.Anthropic = lambda *args, **kwargs: types.SimpleNamespace(
            messages=types.SimpleNamespace(create=lambda **kwargs: None)
        )
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def _production_evidence(title: str, url: str):
    return build_unified_incident_evidence(
        title=title,
        body=url,
        source_url=url,
        locations=("Palm City",),
        published_at="2026-08-06T00:00:00+00:00",
    )


def test_exact_ethan_boyd_source_framings_share_verified_identity():
    first = _production_evidence(WPBF_TITLE, WPBF_URL)
    second = _production_evidence(WPEC_TITLE, WPEC_URL)

    assert first.family == second.family == "missing_person"
    assert "age_14" in first.concepts
    assert "age_14" in second.concepts
    confidence, trace = compare_unified_incident_evidence(first, second)
    assert confidence >= 0.96
    assert "Identity anchors qualified: True" in trace


def test_missing_person_name_patterns_extract_age_before_and_after_name():
    before = build_unified_incident_evidence(
        title="Deputies search for missing teen",
        body="Authorities are searching for 14-year-old Ethan Boyd, who was last seen Wednesday.",
        locations=("Palm City",),
    )
    after = build_unified_incident_evidence(
        title="Public asked to help find missing boy",
        body="Ethan Boyd, a 14-year-old autistic boy, was last seen near Grand Oaks.",
        locations=("Palm City",),
    )
    assert before.people == ("ethan boyd",)
    assert after.people == ("ethan boyd",)


def test_different_named_missing_teens_in_same_city_do_not_merge():
    ethan = build_unified_incident_evidence(
        title="Deputies search for missing autistic teen last seen in Palm City",
        body="14-year-old Ethan Boyd was last seen near Grand Oaks.",
        locations=("Palm City",),
        published_at="2026-08-06T00:00:00+00:00",
    )
    jordan = build_unified_incident_evidence(
        title="Deputies search for missing autistic teen last seen in Palm City",
        body="14-year-old Jordan Smith was last seen near another neighborhood.",
        locations=("Palm City",),
        published_at="2026-08-06T01:00:00+00:00",
    )
    confidence, trace = compare_unified_incident_evidence(ethan, jordan)
    assert confidence == 0.0
    assert "Missing-person name conflict: True" in trace


def test_different_ages_in_same_city_do_not_merge_without_shared_name():
    fourteen = build_unified_incident_evidence(
        title="Help find missing 14-year-old autistic boy last seen in Palm City",
        locations=("Palm City",),
    )
    fifteen = build_unified_incident_evidence(
        title="Help find missing 15-year-old autistic boy last seen in Palm City",
        locations=("Palm City",),
    )
    confidence, trace = compare_unified_incident_evidence(fourteen, fifteen)
    assert confidence == 0.0
    assert "Missing-person age conflict: True" in trace


def test_editorial_engine_reuses_story_across_sparse_publisher_framings(tmp_path: Path):
    engine = EditorialEngine(
        default_published_at=datetime(2026, 8, 6, tzinfo=timezone.utc),
        registry_path=tmp_path / "registry.json",
    )
    first = engine.process(
        {
            "id": "wpbf-ethan",
            "title": WPBF_TITLE,
            "link": WPBF_URL,
            "summary": (
                "Authorities are asking for help finding a 14-year-old autistic "
                "boy last seen in Palm City."
            ),
        },
        source="WPBF",
        county="Martin",
    )
    second = engine.process(
        {
            "id": "wpec-ethan",
            "title": WPEC_TITLE,
            "link": WPEC_URL,
            "summary": (
                "Deputies are searching for a missing autistic teen last seen in "
                "Palm City."
            ),
        },
        source="WPEC",
        county="Martin",
    )
    assert second.story_id == first.story_id
    assert second.action in {EditorialAction.IGNORE, EditorialAction.UPDATE_EXISTING}
    assert second.relationship == "same_event"


def test_registry_repair_can_join_legacy_unknown_and_missing_person_records():
    stories = {
        "story_002406": {
            "story_id": "story_002406",
            "status": "active",
            "canonical_title": WPBF_TITLE,
            "titles": [WPBF_TITLE],
            "locations": ["Palm City"],
            "timeline": [
                {
                    "title": WPBF_TITLE,
                    "source": WPBF_URL,
                    "published_at": "2026-08-06T00:00:54+00:00",
                }
            ],
            "unified_incident_evidence": [
                {
                    "family": "unknown",
                    "concepts": [],
                    "people": [],
                    "locations": ["palm city"],
                    "agencies": [],
                    "distinctive_tokens": ["autistic", "last", "seen"],
                    "title_tokens": ["autistic", "last", "seen"],
                    "published_at": "2026-08-06T00:00:54+00:00",
                }
            ],
        },
        "story_002374": {
            "story_id": "story_002374",
            "status": "active",
            "canonical_title": WPEC_TITLE,
            "titles": [WPEC_TITLE],
            "locations": ["Palm City"],
            "timeline": [
                {
                    "title": WPEC_TITLE,
                    "source": WPEC_URL,
                    "published_at": "2026-08-05T23:49:33+00:00",
                }
            ],
            "unified_incident_evidence": [
                {
                    "family": "unknown",
                    "concepts": [],
                    "people": [],
                    "locations": ["palm city"],
                    "agencies": [],
                    "distinctive_tokens": ["autistic", "last", "seen"],
                    "title_tokens": ["autistic", "last", "seen"],
                    "published_at": "2026-08-05T23:49:33+00:00",
                }
            ],
        },
    }
    assert unified_incident_components(stories) == [
        {"story_002374", "story_002406"}
    ]


def test_existing_missing_person_duplicate_redirects_to_first_canonical(tmp_path: Path):
    generate = _load_generate_module()
    articles = tmp_path / "articles"
    articles.mkdir()
    archive = [
        {
            "slug": CANONICAL,
            "headline": (
                "Martin County Sheriff's Office seeks public help finding missing "
                "14-year-old autistic boy in Palm City"
            ),
            "teaser": (
                "The Martin County Sheriff's Office is asking for help locating "
                "Ethan Boyd, a 14-year-old autistic boy missing in Palm City."
            ),
            "source_url": WPBF_URL,
            "date": "2026-08-06",
            "first_published": "Wed, 05 Aug 2026 22:33:30 -0400",
        },
        {
            "slug": DUPLICATE,
            "headline": (
                "Martin County deputies search for missing autistic teen last seen "
                "in Palm City"
            ),
            "teaser": (
                "The Martin County Sheriff's Office is seeking assistance locating "
                "14-year-old Ethan Boyd near Grand Oaks and Coquina Cove."
            ),
            "source_url": WPEC_URL,
            "date": "2026-08-06",
            "first_published": "Wed, 05 Aug 2026 22:33:33 -0400",
        },
    ]
    cleaned, redirects = generate.apply_canonical_story_cleanup(
        archive, articles, tmp_path
    )
    assert [row["slug"] for row in cleaned] == [CANONICAL]
    redirect = next(row for row in redirects if row["source_slug"] == DUPLICATE)
    assert redirect["target_slug"] == CANONICAL
    rendered = (articles / f"{DUPLICATE}.html").read_text()
    assert f"/articles/{CANONICAL}.html" in rendered
    assert "noindex,follow" in rendered
