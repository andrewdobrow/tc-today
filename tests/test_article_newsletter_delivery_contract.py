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


def test_article_template_uses_dormant_paywall_newsletter_slot_not_old_article_embed():
    source = (ROOT / "scripts" / "generate.py").read_text(encoding="utf-8")
    render_source = source[source.index("def render_article_page("):source.index("\ndef ", source.index("def render_article_page(") + 20)]
    assert '{_paywall_newsletter_slot()}' in render_source
    assert '{_newsletter_inline_embed("article")}' not in render_source

    g = _load_generate()
    slot = g._paywall_newsletter_slot()
    assert 'data-tct-paywall-newsletter="true"' in slot
    assert 'newsletter-inline-slot--paywall' in slot
    assert ' hidden' in slot
    assert "30e15672d3" not in slot
    assert "2865b8d821" not in slot  # membership.js hydrates only after full-paywall state is known


def test_sitewide_article_newsletter_contract_replaces_old_bottom_form_only_on_paywalled_pages(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()

    old_slot = (
        '<aside class="newsletter-inline-slot newsletter-inline-slot--article" '
        'aria-label="Subscribe"><script async data-uid="30e15672d3" '
        'src="https://treasure-coast-today.kit.com/30e15672d3/index.js"></script></aside>'
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
        + old_slot
        + '<div class="article-share">share</div></body></html>',
        encoding="utf-8",
    )

    result = g._normalize_article_newsletter_delivery_sitewide(tmp_path)
    assert result == {"scanned": 2, "updated": 2}

    paywalled_html = paywalled.read_text(encoding="utf-8")
    assert "newsletter-inline-slot--article" not in paywalled_html
    assert "30e15672d3" not in paywalled_html
    assert paywalled_html.count("data-tct-paywall-newsletter") == 1
    assert "newsletter-inline-slot--paywall" in paywalled_html
    assert "hidden" in paywalled_html

    public_html = public.read_text(encoding="utf-8")
    assert "newsletter-inline-slot--article" not in public_html
    assert "newsletter-inline-slot--paywall" not in public_html
    assert "data-tct-paywall-newsletter" not in public_html
    assert "30e15672d3" not in public_html


def test_full_paywall_hydrates_same_current_kit_form_used_midarticle():
    browser = (ROOT / "membership.js").read_text(encoding="utf-8")
    assert "const FULL_ARTICLE_NEWSLETTER_UID = '2865b8d821'" in browser
    assert "function showPaywallNewsletter()" in browser
    assert "slot.hidden = false" in browser
    assert "script.setAttribute('data-uid', FULL_ARTICLE_NEWSLETTER_UID)" in browser
    assert "script.src = FULL_ARTICLE_NEWSLETTER_SRC" in browser
    assert "function removePostArticleNewsletter()" in browser
