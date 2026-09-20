from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda *args, **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    path = ROOT / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_article_newsletter_retained_repair", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_retained_article_with_share_attributes_is_repaired_instead_of_blocking_deploy(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    page = articles / "retained.html"
    page.write_text(
        '<html><body><div class="article-body tct-member-preview"><p>Preview.</p></div>'
        '<aside class="newsletter-inline-slot newsletter-inline-slot--article" aria-label="Old">'
        '<script async data-uid="30e15672d3" src="https://treasure-coast-today.kit.com/30e15672d3/index.js"></script>'
        '</aside>'
        '<div class="article-share" data-shell-version="legacy">share</div></body></html>',
        encoding="utf-8",
    )

    result = g._normalize_article_newsletter_delivery_sitewide(tmp_path)
    assert result == {"scanned": 1, "updated": 1}
    rendered = page.read_text(encoding="utf-8")
    assert rendered.count("newsletter-inline-slot--article") == 1
    assert rendered.count('data-uid="30e15672d3"') == 1
    assert rendered.index("newsletter-inline-slot--article") < rendered.index('class="article-share"')


def test_retained_article_keeps_existing_slot_if_legacy_boundary_is_unrecognized(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    page = articles / "legacy-boundary.html"
    page.write_text(
        '<html><body><div class="article-body tct-member-preview"><p>Preview.</p></div>'
        '<aside class="newsletter-inline-slot newsletter-inline-slot--article">'
        '<script async data-uid="30e15672d3" src="https://treasure-coast-today.kit.com/30e15672d3/index.js"></script>'
        '</aside>'
        '<section class="legacy-share-shell">share</section></body></html>',
        encoding="utf-8",
    )

    result = g._normalize_article_newsletter_delivery_sitewide(tmp_path)
    assert result == {"scanned": 1, "updated": 1}
    rendered = page.read_text(encoding="utf-8")
    assert rendered.count("newsletter-inline-slot--article") == 1
    assert rendered.index("newsletter-inline-slot--article") < rendered.index("legacy-share-shell")


def test_article_newsletter_contract_validates_kit_embed_inside_article_slot_only(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    page = articles / "two-kit-surfaces.html"
    page.write_text(
        '<html><body><div class="article-body"><p>One.</p><p>Two.</p></div>'
        '<div class="article-share">share</div>'
        '<footer><script async data-uid="30e15672d3" '
        'src="https://treasure-coast-today.kit.com/30e15672d3/index.js"></script></footer>'
        '</body></html>',
        encoding="utf-8",
    )

    result = g._normalize_article_newsletter_delivery_sitewide(tmp_path)
    assert result == {"scanned": 1, "updated": 1}
    rendered = page.read_text(encoding="utf-8")
    assert rendered.count("newsletter-inline-slot--article") == 1
    assert rendered.count('data-uid="30e15672d3"') == 2


def test_article_without_slot_or_safe_boundary_still_fails_closed(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    page = articles / "broken.html"
    page.write_text(
        '<html><body><div class="article-body"><p>Story.</p></div>'
        '<section class="unknown-tail">tail</section></body></html>',
        encoding="utf-8",
    )

    try:
        g._normalize_article_newsletter_delivery_sitewide(tmp_path)
    except RuntimeError as exc:
        assert "newsletter insertion boundary missing" in str(exc)
    else:
        raise AssertionError("unsafe article shell should fail closed")
