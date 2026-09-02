from __future__ import annotations

import importlib
import json
import os
import sys
import types

import pytest


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


DEBEVEC_SLUG = (
    "2026-08-29-martin-county-sheriffs-office-searches-for-missing-oklahoma-"
    "visitor-last-seen-at-chastain-beach"
)
DEBEVEC_ORIGINAL_HEADLINE = (
    "Martin County Sheriff's Office searches for missing Oklahoma visitor last seen "
    "at Chastain Beach"
)
DEBEVEC_UPDATED_HEADLINE = (
    "Martin County Sheriff's Office investigates body found in Hutchinson Island "
    "mangroves"
)


def _debevec_archive_row():
    return {
        "slug": DEBEVEC_SLUG,
        "canonical_slug": DEBEVEC_SLUG,
        "headline": DEBEVEC_UPDATED_HEADLINE,
        "permalink_origin_headline": DEBEVEC_ORIGINAL_HEADLINE,
        "custom_headline_key": DEBEVEC_ORIGINAL_HEADLINE,
        "teaser": "A body believed to be the missing visitor was found in Martin County mangroves.",
        "body": " ".join(
            [
                "Deputies investigating the disappearance recovered a body near the House of Refuge; "
                "formal identification remained pending."
            ]
            * 45
        ),
        "category_key": "martin",
        "category_label": "Martin County",
        "date": "2026-08-29",
        "first_published": "Sat, 29 Aug 2026 21:48:09 -0400",
        "lastmod": "2026-09-01",
        "canonical_last_material_update_at": "2026-09-02T02:45:31Z",
        "editorial_story_id": "custom:8b07c4ab92b901c1752d49826291ed8a",
        "is_custom": True,
        "authoritative_custom": True,
        "custom_body_hash": "original-manual-payload-hash",
        "meaningful_update_validated": True,
        "meaningful_update_basis": "semantic_material_update_gate",
        "ranking_eligible": True,
    }


def _debevec_live_clone():
    row = dict(_debevec_archive_row())
    row.update(
        {
            "_archived_slug": DEBEVEC_SLUG,
            "canonical_slug": DEBEVEC_SLUG,
            "enriched": True,
            "urgency_score": 2,
            "_semantic_material_update": True,
        }
    )
    # Critical production condition: this is durable custom provenance, not a
    # current custom_articles.json transaction.
    row.pop("_custom_active_queue", None)
    return row


def test_debevec_progressed_headline_reuses_aug29_custom_canonical_and_rss_receipt(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    archive_row = _debevec_archive_row()
    hero = _debevec_live_clone()

    target, forced_slug, story_id = g._resolve_custom_publication_target(
        hero, [archive_row], archive_row, hero["headline"]
    )

    assert target is archive_row
    assert forced_slug is None
    assert story_id == archive_row["editorial_story_id"]
    assert target["slug"] == DEBEVEC_SLUG
    assert hero.get("_superseded_custom_slug") is None

    # A semantic/material update may advance the public headline, but it must not
    # rewrite the immutable manual-queue identity metadata.
    assert g._refresh_current_manual_custom_metadata(
        archive_row, hero, hero["headline"]
    ) is False
    assert archive_row["custom_headline_key"] == DEBEVEC_ORIGINAL_HEADLINE
    assert archive_row["custom_body_hash"] == "original-manual-payload-hash"

    (tmp_path / "archive.json").write_text(
        json.dumps([archive_row]), encoding="utf-8"
    )
    g.CURRENT_RUN_CUSTOM_PUBLICATION_BINDINGS.clear()
    receipt = g._record_current_custom_publication(
        hero,
        target["slug"],
        story_id,
        "martin",
        "updated",
    )
    assert receipt["slug"] == DEBEVEC_SLUG

    category = {
        "category_key": "martin",
        "category_label": "Martin County",
        "hero": hero,
        "cards": [],
    }
    feed = g.render_rss_feed([category], category)
    (tmp_path / "feed.xml").write_text(feed, encoding="utf-8")
    report = g.validate_custom_rss_publication_contract(tmp_path)

    assert report["passed"] is True
    assert report["missing"] == []
    assert report["expected"][0]["slug"] == DEBEVEC_SLUG
    assert "2026-09-02-martin-county-sheriffs-office-investigates-body-found" not in feed


def test_nonqueue_authoritative_custom_cannot_mint_without_established_binding():
    g = _load_generate()
    hero = {
        "headline": "Updated display headline",
        "body": "updated body",
        "is_custom": True,
        "authoritative_custom": True,
    }

    with pytest.raises(RuntimeError, match="lost established permalink binding"):
        g._resolve_custom_publication_target(hero, [], None, hero["headline"])


def test_current_manual_submission_still_uses_exact_headline_new_article_contract():
    g = _load_generate()
    old = {
        "slug": "manual-old",
        "headline": "Manual Headline",
        "custom_headline_key": "Manual Headline",
        "is_custom": True,
        "authoritative_custom": True,
    }
    current = {
        "headline": "Manual Headline Changed",
        "body": "complete new editor payload",
        "is_custom": True,
        "authoritative_custom": True,
        "_custom_active_queue": True,
    }

    target, forced_slug, story_id = g._resolve_custom_publication_target(
        current, [old], old, current["headline"]
    )

    assert target is None
    assert forced_slug is None
    assert story_id.startswith("custom:")
