from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path


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


def test_modern_article_shell_is_not_rewritten(tmp_path: Path):
    generate = _load_generate_module()
    articles = tmp_path / "articles"
    articles.mkdir()
    page = articles / "modern.html"
    original = """<html><head></head><body>
<div class=\"newsroom-strip\"></div>
<div class=\"article-wrap\">
<a class=\"article-banner-slot article-ad-banner\"></a>
<div class=\"article-meta\"></div><h1>Modern page</h1>
<div class=\"article-editorial-grid\"><div class=\"article-main-column\">
<div class=\"article-body\">Body</div></div><aside class=\"article-side-rail\"></aside></div>
</div></body></html>"""
    page.write_text(original, encoding="utf-8")

    report = generate._repair_article_shells(tmp_path)

    assert report["checked"] == 1
    assert report["skipped_modern"] == 1
    assert report["repaired"] == 0
    assert page.read_text(encoding="utf-8") == original
