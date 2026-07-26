from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path


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


def _guide():
    return {
        "article_type": "product_guide",
        "headline": "Responsive disclosure test",
        "category": "florida",
        "intro": "Prepare early.",
        "affiliate_disclosure": (
            "Treasure Coast Today may earn a commission from qualifying purchases "
            "made through links in this article."
        ),
        "products": [
            {
                "name": "Emergency Radio",
                "image_url": "https://images.example/radio.jpg",
                "affiliate_url": "https://www.amazon.com/dp/ABC?tag=tct-20",
            }
        ],
    }


def test_affiliate_disclosure_uses_nonshrinking_grid_and_mobile_stack():
    g = _load_generate()
    guide = _guide()
    g._normalize_product_guide(guide)
    html = g._render_product_guide_body(guide)

    assert "grid-template-columns:max-content minmax(0,1fr)" in html
    assert ".pg-disclosure strong { color:var(--pg-green); white-space:nowrap;" in html
    assert ".pg-disclosure span { min-width:0; overflow-wrap:anywhere; }" in html
    assert ".pg-disclosure { grid-template-columns:1fr; gap:5px;" in html
    assert ".pg-disclosure strong { white-space:normal; }" in html


def test_product_guide_template_version_changes_publication_signature(monkeypatch):
    g = _load_generate()
    guide = _guide()
    g._normalize_product_guide(guide)

    original = g._product_guide_hash(guide)
    monkeypatch.setattr(g, "PRODUCT_GUIDE_TEMPLATE_VERSION", "next-template-version")
    changed = g._product_guide_hash(guide)

    assert original != changed


def test_generator_source_keeps_disclosure_css_scoped_to_product_guides():
    source = (Path(__file__).resolve().parents[1] / "scripts" / "generate.py").read_text(
        encoding="utf-8"
    )
    assert '<style class="product-guide-styles">' in source
    assert '.pg-disclosure' in source
