from __future__ import annotations

import importlib
import inspect
import json
import os
import struct
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRIPE_URL = "https://buy.stripe.com/4gM5kw9LWfRb7uV6P34ZG01"
BANNER_URL = "https://treasurecoast.today/images/support-banner.png"
MIGRATION_LIMIT = 50


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


def test_canonical_support_banner_uses_stripe_and_public_asset():
    generate = _load_generate_module()
    html = generate._article_support_banner_html("  ")
    legacy_filename = "advertise" + "-banner.png"

    assert f'href="{STRIPE_URL}"' in html
    assert f'src="{BANNER_URL}"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer external"' in html
    assert 'aria-label="Support Treasure Coast Today"' in html
    assert legacy_filename not in html
    assert "/advertise.html" not in html


def test_article_render_and_shell_repair_share_contextual_banner_contract():
    generate = _load_generate_module()

    render_source = inspect.getsource(generate.render_article_page)
    repair_source = inspect.getsource(generate._repair_article_shells)

    assert "_article_banner_html_for_context(" in render_source
    assert "return _article_banner_html_for_context(article_text)" in repair_source


def _write_legacy_page(path: Path, *, sensitive: bool = False):
    if sensitive:
        banner = (
            '<section class="article-banner-slot article-house-banner" '
            'aria-label="Editorial Notice">\n'
            '  <div class="article-house-mark">TCT</div>\n'
            '  <div class="article-house-copy">Sensitive-topic notice</div>\n'
            '</section>'
        )
    else:
        legacy_filename = "advertise" + "-banner.png"
        banner = (
            '<a href="/advertise.html" class="article-banner-slot article-ad-banner" '
            'aria-label="Advertise with Treasure Coast Today">\n'
            f'  <img src="/images/{legacy_filename}" alt="Advertise with Treasure Coast Today">\n'
            '</a>'
        )
    path.write_text(f'<html><body>\n{banner}\n</body></html>', encoding="utf-8")


def test_legacy_article_banner_migration_is_complete_and_idempotent(tmp_path: Path):
    generate = _load_generate_module()
    articles = tmp_path / "articles"
    articles.mkdir()
    page = articles / "legacy.html"
    _write_legacy_page(page)

    first = generate._migrate_legacy_article_support_banners(tmp_path)
    migrated = page.read_text(encoding="utf-8")
    second = generate._migrate_legacy_article_support_banners(tmp_path)

    assert first == {"checked": 1, "migrated": 1, "limit": MIGRATION_LIMIT}
    assert second == {"checked": 1, "migrated": 0, "limit": MIGRATION_LIMIT}
    assert "advertise-banner.png" not in migrated
    assert "/advertise.html" not in migrated
    assert STRIPE_URL in migrated
    assert BANNER_URL in migrated


def test_retained_page_migration_is_limited_to_newest_50(tmp_path: Path):
    generate = _load_generate_module()
    articles = tmp_path / "articles"
    articles.mkdir()
    archive = []
    for index in range(55):
        slug = f"2026-07-{index + 1:02d}-story-{index:02d}"
        _write_legacy_page(articles / f"{slug}.html", sensitive=index % 2 == 0)
        archive.append({"slug": slug, "date": f"2026-07-{index + 1:02d}"})
    (tmp_path / "archive.json").write_text(json.dumps(archive), encoding="utf-8")

    result = generate._migrate_legacy_article_support_banners(tmp_path)

    assert result == {"checked": MIGRATION_LIMIT, "migrated": MIGRATION_LIMIT, "limit": MIGRATION_LIMIT}
    for index in range(5):
        html = (articles / f"2026-07-{index + 1:02d}-story-{index:02d}.html").read_text()
        assert STRIPE_URL not in html
    for index in range(5, 55):
        html = (articles / f"2026-07-{index + 1:02d}-story-{index:02d}.html").read_text()
        assert STRIPE_URL in html
        assert BANNER_URL in html


def test_support_banner_asset_matches_live_banner_dimensions():
    image = ROOT / "images" / "support-banner.png"
    assert image.exists()

    with image.open("rb") as handle:
        header = handle.read(24)
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", header[16:24])
    assert (width, height) == (940, 234)


def test_reader_support_preflight_is_noop_after_membership_launch(tmp_path: Path, monkeypatch):
    """Launch state must not reconstruct the retired Support TCT article banner.

    This is intentionally synthetic. CI must not make assertions about mutable
    production article files, because those files legitimately differ before and
    after the membership launch switch.
    """
    generate = _load_generate_module()
    monkeypatch.setattr(generate, "ARTICLE_BANNER_MODE", "reader_support")
    monkeypatch.setattr(generate, "MEMBERSHIP_UI_ENABLED", True)

    articles = tmp_path / "articles"
    articles.mkdir()
    page = articles / "2026-08-09-example.html"
    page.write_text(
        '<html><body><div class="article-meta">Local News</div>'
        '<div class="article-body"><p>Example article.</p></div></body></html>',
        encoding="utf-8",
    )

    result = generate._migrate_legacy_article_support_banners(tmp_path, limit=50)
    rendered = page.read_text(encoding="utf-8")

    assert result == {"checked": 0, "migrated": 0, "limit": 50}
    assert STRIPE_URL not in rendered
    assert BANNER_URL not in rendered
    assert "article-banner-slot" not in rendered


def test_reader_support_mode_uses_support_banner_on_sensitive_topics(monkeypatch):
    generate = _load_generate_module()
    monkeypatch.setattr(generate, "ARTICLE_BANNER_MODE", "reader_support")

    for article_text in (
        "Police investigate a fatal shooting in Port St. Lucie",
        "A domestic violence arrest was announced",
        "Officials respond to a sexual assault investigation",
        "A suicide prevention response followed the incident",
    ):
        html = generate._article_banner_html_for_context(article_text)
        assert STRIPE_URL in html
        assert BANNER_URL in html
        assert "article-house-banner" not in html
        assert "/advertise.html" not in html


def test_paid_advertising_mode_retains_sensitive_topic_architecture(monkeypatch):
    generate = _load_generate_module()
    monkeypatch.setattr(generate, "ARTICLE_BANNER_MODE", "paid_advertising")

    ordinary = generate._article_banner_html_for_context("City commission approves a new park")
    fatal = generate._article_banner_html_for_context("Police investigate a fatal shooting")
    sexual = generate._article_banner_html_for_context("Sexual assault investigation continues")
    domestic = generate._article_banner_html_for_context("Domestic violence arrest announced")
    crisis = generate._article_banner_html_for_context("Suicide prevention response")

    assert "/advertise.html" in ordinary
    assert "advertise-banner.png" in ordinary
    assert "article-house-banner" in fatal
    assert "commercial sponsorship" in fatal
    assert "rainn.org" in sexual
    assert "thehotline.org" in domestic
    assert "988lifeline.org" in crisis


def test_sensitive_house_banner_migrates_to_reader_support_and_is_idempotent(
    tmp_path: Path, monkeypatch
):
    generate = _load_generate_module()
    monkeypatch.setattr(generate, "ARTICLE_BANNER_MODE", "reader_support")
    articles = tmp_path / "articles"
    articles.mkdir()
    page = articles / "sensitive.html"
    _write_legacy_page(page, sensitive=True)

    first = generate._migrate_legacy_article_support_banners(tmp_path)
    migrated = page.read_text(encoding="utf-8")
    second = generate._migrate_legacy_article_support_banners(tmp_path)

    assert first == {"checked": 1, "migrated": 1, "limit": MIGRATION_LIMIT}
    assert second == {"checked": 1, "migrated": 0, "limit": MIGRATION_LIMIT}
    assert "article-house-banner" not in migrated
    assert STRIPE_URL in migrated
    assert BANNER_URL in migrated


def test_production_workflow_exposes_reader_support_to_paid_advertising_switch():
    workflow = (ROOT / ".github" / "workflows" / "update.yml").read_text(encoding="utf-8")
    assert "TCT_ARTICLE_BANNER_MODE" in workflow
    assert "vars.TCT_ARTICLE_BANNER_MODE || 'reader_support'" in workflow



def test_preflight_repairs_legacy_sensitive_and_missing_recent_slots(tmp_path: Path):
    generate = _load_generate_module()
    articles = tmp_path / "articles"
    articles.mkdir()

    legacy = articles / "2026-08-01-legacy.html"
    sensitive = articles / "2026-08-02-sensitive.html"
    missing = articles / "2026-08-03-missing.html"
    _write_legacy_page(legacy)
    _write_legacy_page(sensitive, sensitive=True)
    missing.write_text(
        '<html><body>\n  <div class="article-meta">Local News</div>\n</body></html>',
        encoding="utf-8",
    )
    (tmp_path / "archive.json").write_text(
        json.dumps([
            {"slug": legacy.stem},
            {"slug": sensitive.stem},
            {"slug": missing.stem},
        ]),
        encoding="utf-8",
    )

    first = generate._migrate_legacy_article_support_banners(tmp_path, limit=50)
    second = generate._migrate_legacy_article_support_banners(tmp_path, limit=50)

    assert first == {"checked": 3, "migrated": 3, "limit": 50}
    assert second == {"checked": 3, "migrated": 0, "limit": 50}
    for page in (legacy, sensitive, missing):
        html = page.read_text(encoding="utf-8")
        assert html.count('article-banner-slot') == 1
        assert STRIPE_URL in html
        assert BANNER_URL in html
        assert "advertise-banner.png" not in html
        assert "article-house-banner" not in html


def test_both_workflows_run_reader_support_preflight_before_validation_and_pytest():
    for relative in (
        ".github/workflows/test-editorial-engine.yml",
        ".github/workflows/update.yml",
    ):
        workflow = (ROOT / relative).read_text(encoding="utf-8")
        preflight = workflow.index("Normalize recent reader-support banners")
        validate = workflow.index("Validate editorial package")
        pytest_step = workflow.index("Run editorial engine tests")

        assert preflight < validate < pytest_step
        assert "_migrate_legacy_article_support_banners(Path.cwd(), limit=50)" in workflow
        assert "TCT_ARTICLE_BANNER_MODE" in workflow
        assert "TCT_MEMBERSHIP_UI_ENABLED" in workflow
