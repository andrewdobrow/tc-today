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
        anthropic.Anthropic = lambda *args, **kwargs: types.SimpleNamespace(
            messages=types.SimpleNamespace(create=lambda **kwargs: None)
        )
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def test_membership_ui_is_dark_by_default_and_current_reader_ctas_remain_advertising(monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "MEMBERSHIP_UI_ENABLED", False)

    assert ">Advertise</a>" in g._header_primary_cta_html()
    assert "Subscribe" not in g._header_primary_cta_html()
    card = g._homepage_support_card_html()
    assert "/advertise.html" in card
    assert "Reach readers across the Treasure Coast." in card
    assert "Comprehensive local coverage" not in card


def test_membership_ui_prebuild_has_locked_subscribe_copy_but_only_when_enabled(monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "MEMBERSHIP_UI_ENABLED", True)
    monkeypatch.setattr(g, "MEMBERSHIP_SUBSCRIBE_URL", "/subscribe.html")

    header = g._header_primary_cta_html()
    card = g._homepage_support_card_html()
    assert 'href="/subscribe.html"' in header
    assert ">Subscribe</a>" in header
    assert "tct-membership-card" in card
    assert "Comprehensive local coverage. No ads. Less than $5 a month." in card
    assert "$4.99 monthly" in card
    assert "$49 annually" in card
    assert "Completely ad-free" in card
    assert "Martin, St. Lucie and Indian River counties" in card
