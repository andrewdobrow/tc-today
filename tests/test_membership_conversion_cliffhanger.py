from __future__ import annotations

import os
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]


def _load_generate():
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
    import importlib
    return importlib.import_module("scripts.generate")


def test_paywall_fade_is_deliberately_strong_and_teaser_text_itself_fades():
    css = (ROOT / "membership.css").read_text()
    assert ".tct-preview-fade-text" in css
    assert "height: 156px" in css
    assert "margin-top: -122px" in css
    assert "rgba(41,47,43,0) 100%" in css
    assert "rgba(247,250,250,.90) 73%" in css


def test_member_unlock_reassembles_first_paragraph_before_showing_remainder():
    js = (ROOT / "membership.js").read_text()
    assert "data-tct-first-paragraph-continuation" in js
    assert "data-tct-preview-paragraph" in js
    assert "previewParagraph.textContent" in js
    assert "continuation.remove()" in js


def test_morning_brief_cta_is_explicitly_free():
    g = _load_generate()
    markup = g._newsletter_inline_embed("article")
    assert "Subscribe to the Morning Brief for free" in markup
    assert "Free newsletter" in markup
    assert "aria-label=\"Subscribe to the Treasure Coast Morning Brief for free\"" in markup


def test_launch_footer_has_distinct_coral_subscription_ask(monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "MEMBERSHIP_UI_ENABLED", True)
    footer = g._page_footer()
    css = (ROOT / "style.css").read_text()
    assert "Support local journalism" in footer
    assert 'class="footer-subscribe-cta"' in footer
    assert "$4.99/mo &middot; $49/yr" in footer
    assert 'href="/subscribe.html"' in footer
    assert "background: #f26445" in css


def test_dark_launch_footer_keeps_existing_connect_cta(monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "MEMBERSHIP_UI_ENABLED", False)
    footer = g._page_footer()
    assert "Connect with TCT" in footer
    assert "footer-subscribe-cta" not in footer
