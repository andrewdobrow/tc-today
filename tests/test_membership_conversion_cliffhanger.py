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


def test_paywall_fade_matches_strong_vertical_editorial_cliffhanger():
    css = (ROOT / "membership.css").read_text()
    assert ".tct-preview-copy" in css
    assert "-webkit-mask-image: linear-gradient(" in css
    assert "to bottom" in css
    assert "#000 36%" in css
    assert "rgba(0,0,0,.26) 76%" in css
    assert "transparent 100%" in css
    assert "height: 112px" in css
    assert "margin-top: -86px" in css
    assert "rgba(247,250,250,.94) 80%" in css


def test_member_unlock_prefers_full_body_payload_and_keeps_legacy_compatibility():
    js = (ROOT / "membership.js").read_text()
    assert "<!--tct-full-article-v2-->" in js
    assert "preview.innerHTML = protectedBody.slice" in js
    assert "memberOnly?.remove()" in js
    assert "data-tct-first-paragraph-continuation" in js
    assert "data-tct-preview-paragraph" in js


def test_morning_brief_visible_copy_is_owned_by_kit():
    g = _load_generate()
    markup = g._newsletter_inline_embed("article")
    assert 'class="newsletter-inline-intro"' not in markup
    assert 'newsletter-inline-kicker' not in markup
    assert "Subscribe to the Morning Brief for free" not in markup
    assert 'aria-label="Subscribe to the Treasure Coast Morning Brief"' in markup
    assert f'data-uid="{g.KIT_INLINE_FORM_UID}"' in markup
    assert f'src="{g.KIT_INLINE_FORM_SRC}"' in markup


def test_launch_footer_has_distinct_coral_subscription_ask(monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "MEMBERSHIP_UI_ENABLED", True)
    footer = g._page_footer()
    css = (ROOT / "style.css").read_text()
    assert "Support local journalism" in footer
    assert 'class="footer-subscribe-cta"' in footer
    assert "Limited time &middot; $1 first month &middot; then $4.99/mo" in footer
    assert 'href="/subscribe.html"' in footer
    assert "background: #f26445" in css


def test_dark_launch_footer_keeps_existing_connect_cta(monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "MEMBERSHIP_UI_ENABLED", False)
    footer = g._page_footer()
    assert "Connect with TCT" in footer
    assert "footer-subscribe-cta" not in footer
