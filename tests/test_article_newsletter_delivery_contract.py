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
    spec = importlib.util.spec_from_file_location("generate_article_newsletter_contract", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_article_template_restores_requested_kit_form_immediately_after_article_body():
    source = (ROOT / "scripts" / "generate.py").read_text(encoding="utf-8")
    render_source = source[source.index("def render_article_page("):source.index("\ndef ", source.index("def render_article_page(") + 20)]
    assert '{_newsletter_inline_embed("article")}' in render_source
    assert '{_paywall_newsletter_slot()}' not in render_source
    assert render_source.index('<div class="article-body">{body}</div>') < render_source.index('{_newsletter_inline_embed("article")}')


def test_sitewide_article_newsletter_contract_puts_same_requested_form_on_all_articles(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()

    old_slot = (
        '<aside class="newsletter-inline-slot newsletter-inline-slot--paywall" '
        'data-tct-paywall-newsletter="true" hidden></aside>'
    )
    paywalled = articles / "paywalled.html"
    paywalled.write_text(
        '<html><body><div class="article-body"><p>One.</p><p>Two.</p></div>'
        '<section class="tct-paywall" data-tct-paywall data-slug="paywalled"></section>'
        + old_slot
        + '<div class="article-share">share</div></body></html>',
        encoding="utf-8",
    )
    public = articles / "public.html"
    public.write_text(
        '<html><body><div class="article-body"><p>One.</p><p>Two.</p></div>'
        '<div class="article-share">share</div></body></html>',
        encoding="utf-8",
    )

    result = g._normalize_article_newsletter_delivery_sitewide(tmp_path)
    assert result == {"scanned": 2, "updated": 2}

    for path in (paywalled, public):
        rendered = path.read_text(encoding="utf-8")
        assert rendered.count("newsletter-inline-slot--article") == 1
        assert rendered.count('data-uid="30e15672d3"') == 1
        assert rendered.count("https://treasure-coast-today.kit.com/30e15672d3/index.js") == 1
        assert "data-tct-paywall-newsletter" not in rendered
        assert rendered.index('newsletter-inline-slot--article') < rendered.index('<div class="article-share">')


def test_membership_runtime_preserves_or_falls_back_to_same_requested_article_end_form():
    browser = (ROOT / "membership.js").read_text(encoding="utf-8")
    assert "const FULL_ARTICLE_NEWSLETTER_UID = '30e15672d3'" in browser
    assert "function showPaywallNewsletter()" in browser
    assert "if (qs('.newsletter-inline-slot--article', articleRoot)) return true" in browser
    assert "script.setAttribute('data-uid', FULL_ARTICLE_NEWSLETTER_UID)" in browser
    assert "script.src = FULL_ARTICLE_NEWSLETTER_SRC" in browser
    assert "function removePostArticleNewsletter()" in browser
