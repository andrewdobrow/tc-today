from __future__ import annotations

import importlib
import os
import sys
import types


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
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def _canonical(g):
    return {
        "slug": g.WESTMORELAND_ALF_CANONICAL_SLUG,
        "headline": "Residents seek halt to Port St. Lucie assisted living project near petroleum cleanup site",
        "teaser": (
            "Sandpiper Bay residents are asking city and fire officials to intervene in a proposed "
            "assisted-living development next to a known petroleum-contaminated property, citing "
            "engineering records that specifically reference the future senior facility during remediation planning."
        ),
        "body": (
            "Residents raised environmental concerns about the assisted-living development near a known "
            "petroleum-contaminated property. Engineering records discuss remediation planning for the future "
            "senior facility and petroleum vapor concerns in Port St. Lucie."
        ),
        "date": "2026-09-29",
        "first_published": "Tue, 29 Sep 2026 18:24:40 -0400",
        "category_key": "local_gov",
        "category_keys": ["local_gov", "st_lucie"],
        "county_keys": ["st_lucie"],
        "is_custom": True,
        "authoritative_custom": True,
        "custom_id": "2026-09-29-westmoreland-alf-petroleum-cleanup-concerns",
        "custom_publication_key": "id:2026-09-29-westmoreland-alf-petroleum-cleanup-concerns",
        "editorial_story_id": "custom:westmoreland",
    }


def _oct9_re_report():
    return {
        "headline": "Port St. Lucie Residents Question Contamination Near Approved Assisted-Living Site",
        "source_headline": "Port St. Lucie Residents Question Contamination Near Approved Assisted-Living Site",
        "article_text": (
            "The Port St. Lucie City Council approved the major site plan for a 150-unit assisted-living facility "
            "near a property with a history of petroleum contamination. Nearby residents say unresolved environmental "
            "questions remain as the project advances. The development is planned in Port St. Lucie."
        ),
        "source_published": "2026-10-09T06:52:00-04:00",
        "date": "2026-10-09",
        "source_url": "https://cbs12.com/westmoreland-alf",
    }


def test_delayed_publisher_re_report_binds_to_manual_custom_scoop():
    g = _load_generate()
    matched, key = g._durable_custom_extended_subject_identity_match(_oct9_re_report(), _canonical(g))
    assert matched is True
    assert key.startswith("extended-custom-subject|")

    match, confidence, basis = g._find_authoritative_custom_incident_match(
        _oct9_re_report(), archived_customs=[_canonical(g)], current_customs=[]
    )
    assert match["slug"] == g.WESTMORELAND_ALF_CANONICAL_SLUG
    assert confidence == 100
    assert "durable_custom_incident_identity" in basis


def test_same_city_different_assisted_living_project_does_not_merge():
    g = _load_generate()
    unrelated = {
        "headline": "Port St. Lucie approves new assisted-living project near Tradition",
        "article_text": (
            "A separate assisted-living development in Tradition will add 120 senior housing and memory-care beds. "
            "The developer plans a clubhouse, landscaped courtyard and transportation services for residents."
        ),
        "date": "2026-10-09",
    }
    assert g._durable_custom_extended_subject_identity_match(unrelated, _canonical(g))[0] is False


def test_extended_custom_lock_expires_after_45_days():
    g = _load_generate()
    later = _oct9_re_report()
    later["date"] = "2026-11-20"
    later["source_published"] = "2026-11-20T08:00:00-05:00"
    assert g._durable_custom_extended_subject_identity_match(later, _canonical(g))[0] is False


def test_existing_oct9_duplicate_is_permanently_redirected(tmp_path):
    g = _load_generate()
    (tmp_path / "articles").mkdir()
    (tmp_path / "data").mkdir()
    duplicate_slug = next(iter(g.WESTMORELAND_ALF_REDIRECT_SOURCE_SLUGS))
    archive = [
        _canonical(g),
        {
            "slug": duplicate_slug,
            "headline": _oct9_re_report()["headline"],
            "teaser": _oct9_re_report()["article_text"],
            "date": "2026-10-09",
            "category_key": "st_lucie",
            "category_keys": ["st_lucie"],
            "county_keys": ["st_lucie"],
        },
    ]
    cleaned, redirects = g.apply_canonical_story_cleanup(archive, tmp_path / "articles", tmp_path)
    assert duplicate_slug not in {row.get("slug") for row in cleaned}
    redirect = next(row for row in redirects if row.get("source_slug") == duplicate_slug)
    assert redirect["target_slug"] == g.WESTMORELAND_ALF_CANONICAL_SLUG
    assert redirect["canonical_is_custom"] is True
