from __future__ import annotations

import importlib
import json
import os
import sys
import types
from pathlib import Path

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


def _archive_row(headline: str, slug: str, first_published: str, **updates):
    row = {
        "headline": headline,
        "slug": slug,
        "teaser": f"Teaser for {headline}",
        "category_key": "st_lucie",
        "date": first_published[:10],
        "first_published": first_published,
        "image_url": "/images/story.png",
    }
    row.update(updates)
    return row


def test_rss_includes_custom_archive_article_even_when_not_on_live_surfaces(tmp_path: Path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(g, "CURRENT_RUN_CUSTOM_PUBLICATION_BINDINGS", [])
    custom = _archive_row(
        "Port St. Lucie Police Unveil New Training Facility",
        "2026-07-25-port-st-lucie-police-training-facility",
        "Sat, 25 Jul 2026 14:00:00 -0400",
        is_custom=True,
        authoritative_custom=True,
    )
    live = _archive_row(
        "County commission approves drainage work",
        "2026-07-25-county-commission-drainage-work",
        "Sat, 25 Jul 2026 15:00:00 -0400",
    )
    (tmp_path / "archive.json").write_text(json.dumps([custom, live]), encoding="utf-8")
    category = {
        "category_key": "st_lucie",
        "category_label": "St. Lucie County",
        "hero": {"headline": live["headline"], "slug": live["slug"], "teaser": live["teaser"]},
        "cards": [],
    }

    rss = g.render_rss_feed([category], category)

    assert custom["headline"] in rss
    assert f"/articles/{custom['slug']}.html" in rss
    assert live["headline"] in rss


def test_new_custom_publication_is_prioritized_at_top_of_rss(tmp_path: Path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    custom = _archive_row(
        "Original TCT custom article",
        "2026-07-25-original-tct-custom-article",
        "Sat, 25 Jul 2026 12:00:00 -0400",
        is_custom=True,
        authoritative_custom=True,
    )
    newer_feed = _archive_row(
        "Newer external feed article",
        "2026-07-25-newer-external-feed-article",
        "Sat, 25 Jul 2026 16:00:00 -0400",
    )
    (tmp_path / "archive.json").write_text(json.dumps([custom, newer_feed]), encoding="utf-8")
    monkeypatch.setattr(g, "CURRENT_RUN_CUSTOM_PUBLICATION_BINDINGS", [{
        "headline": custom["headline"],
        "slug": custom["slug"],
        "action": "created",
    }])
    category = {
        "category_key": "st_lucie",
        "category_label": "St. Lucie County",
        "hero": newer_feed,
        "cards": [],
    }

    rss = g.render_rss_feed([category], category)

    assert rss.index(custom["headline"]) < rss.index(newer_feed["headline"])
    assert '<media:content url="https://treasurecoast.today/images/story.png" medium="image" />' in rss


def test_custom_rss_publication_contract_passes_for_current_receipt(tmp_path: Path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    slug = "2026-07-25-custom-story"
    url = f"{g.SITE_URL}/articles/{slug}.html"
    (tmp_path / "feed.xml").write_text(
        f"<rss><channel><item><guid isPermaLink=\"true\">{url}</guid></item></channel></rss>",
        encoding="utf-8",
    )
    monkeypatch.setattr(g, "CURRENT_RUN_CUSTOM_PUBLICATION_BINDINGS", [{
        "headline": "Custom story",
        "slug": slug,
        "action": "created",
    }])

    report = g.validate_custom_rss_publication_contract(tmp_path)

    assert report["passed"] is True
    assert report["checked_current_custom_publications"] == 1
    assert json.loads((tmp_path / "data" / "rss-publication-contract.json").read_text())["passed"] is True


def test_custom_rss_publication_contract_fails_closed_when_receipt_is_missing(tmp_path: Path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    (tmp_path / "feed.xml").write_text("<rss><channel></channel></rss>", encoding="utf-8")
    monkeypatch.setattr(g, "CURRENT_RUN_CUSTOM_PUBLICATION_BINDINGS", [{
        "headline": "Missing custom story",
        "slug": "2026-07-25-missing-custom-story",
        "action": "created",
    }])

    with pytest.raises(RuntimeError, match="Custom RSS publication contract FAILED"):
        g.validate_custom_rss_publication_contract(tmp_path)

    report = json.loads((tmp_path / "data" / "rss-publication-contract.json").read_text())
    assert report["passed"] is False
    assert report["missing"][0]["slug"] == "2026-07-25-missing-custom-story"


def test_new_publication_slug_never_reuses_retired_custom_permalink(tmp_path: Path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    retired_slug = "2026-09-05-treasure-coast-weekly-traffic-report-i-95-ramp-closures"
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "custom-retirements.json").write_text(
        json.dumps({"slugs": [{"slug": retired_slug, "action": "purge"}]}),
        encoding="utf-8",
    )

    allocated = g._allocate_new_publication_slug(retired_slug, [], tmp_path)

    assert allocated == retired_slug + "-1"


def test_current_custom_publication_is_in_rss_even_if_live_recovery_excluded(tmp_path: Path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    custom = _archive_row(
        "Treasure Coast Weekly Traffic Report",
        "2026-09-05-treasure-coast-weekly-traffic-report",
        "Sat, 05 Sep 2026 03:00:00 -0400",
        is_custom=True,
        authoritative_custom=True,
        exclude_from_live_recovery=True,
        identity_quarantine_reason="recurring_custom_edition_superseded",
    )
    (tmp_path / "archive.json").write_text(json.dumps([custom]), encoding="utf-8")
    monkeypatch.setattr(g, "CURRENT_RUN_CUSTOM_PUBLICATION_BINDINGS", [{
        "headline": custom["headline"],
        "slug": custom["slug"],
        "action": "created",
    }])

    rss = g.render_rss_feed([], None)

    assert custom["headline"] in rss
    assert f"/articles/{custom['slug']}.html" in rss


def test_explicitly_retired_current_custom_publication_stays_out_of_rss(tmp_path: Path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    custom = _archive_row(
        "Retired custom story",
        "2026-09-05-retired-custom-story",
        "Sat, 05 Sep 2026 03:00:00 -0400",
        is_custom=True,
        authoritative_custom=True,
        retired_custom=True,
        exclude_from_live_recovery=True,
        identity_quarantine_reason="editor_retired_custom_article",
    )
    (tmp_path / "archive.json").write_text(json.dumps([custom]), encoding="utf-8")
    monkeypatch.setattr(g, "CURRENT_RUN_CUSTOM_PUBLICATION_BINDINGS", [{
        "headline": custom["headline"],
        "slug": custom["slug"],
        "action": "created",
    }])

    rss = g.render_rss_feed([], None)

    assert custom["headline"] not in rss
