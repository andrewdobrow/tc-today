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


def test_mediavine_loader_is_exactly_before_head_close():
    generate = _load_generate_module()
    html = "<html><head><title>TCT</title></head><body></body></html>"
    normalized = generate._normalize_mediavine_script_in_html(html)

    assert normalized.count(generate.MEDIAVINE_SCRIPT_SRC) == 1
    assert normalized.replace("\r\n", "\n").endswith("</body></html>")
    assert (
        generate.MEDIAVINE_SCRIPT_TAG + "\n</head>"
        in normalized.replace("\r\n", "\n")
    )


def test_mediavine_loader_normalization_is_idempotent_and_relocates_existing_copy():
    generate = _load_generate_module()
    html = (
        "<html><head>"
        + generate.MEDIAVINE_SCRIPT_TAG
        + "<title>TCT</title></head><body></body></html>"
    )
    once = generate._normalize_mediavine_script_in_html(html)
    twice = generate._normalize_mediavine_script_in_html(once)

    assert once == twice
    assert once.count(generate.MEDIAVINE_SCRIPT_SRC) == 1
    head_close = once.lower().index("</head>")
    assert once[:head_close].rstrip().endswith(generate.MEDIAVINE_SCRIPT_TAG)


def test_mediavine_loader_sitewide_covers_nested_html(tmp_path: Path):
    generate = _load_generate_module()
    (tmp_path / "articles").mkdir()
    (tmp_path / "index.html").write_text(
        "<html><head><title>Home</title></head><body></body></html>", encoding="utf-8"
    )
    (tmp_path / "articles" / "story.html").write_text(
        "<html><head><meta charset='utf-8'></head><body></body></html>", encoding="utf-8"
    )

    report = generate._apply_mediavine_script_sitewide(tmp_path)

    assert report == {"scanned": 2, "updated": 2}
    for path in (tmp_path / "index.html", tmp_path / "articles" / "story.html"):
        text = path.read_text(encoding="utf-8")
        assert text.count(generate.MEDIAVINE_SCRIPT_SRC) == 1
        head_close = text.lower().index("</head>")
        assert text[:head_close].rstrip().endswith(generate.MEDIAVINE_SCRIPT_TAG)
