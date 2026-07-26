from __future__ import annotations

import importlib
import json
import os
import sys
import types
from pathlib import Path

import pytest


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


def test_malformed_custom_queue_fails_closed(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    (tmp_path / "custom_articles.json").write_text(
        '[{"headline":"One","body":"copy","category":"florida"}\n'
        '{"headline":"Two","body":"copy","category":"florida"}]',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match=r"invalid JSON at line 2, column 1"):
        g.load_custom_articles()


def test_wrong_top_level_custom_queue_fails_closed(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    (tmp_path / "custom_articles.json").write_text("{}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="top-level JSON array"):
        g.load_custom_articles()


def test_invalid_custom_item_fails_instead_of_disappearing(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    (tmp_path / "custom_articles.json").write_text(
        json.dumps([{"headline": "Missing body", "category": "florida"}]),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="missing non-empty body"):
        g.load_custom_articles()


def test_duplicate_exact_headline_fails_closed(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    item = {"headline": "Same headline", "body": "copy", "category": "florida"}
    (tmp_path / "custom_articles.json").write_text(
        json.dumps([item, item]), encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match="exact headline more than once"):
        g.load_custom_articles()


def test_package_validator_reports_queue_parse_location(tmp_path):
    from scripts.validate_package import validate_custom_queue

    path = tmp_path / "custom_articles.json"
    path.write_text('[{"headline":"One"}\n{"headline":"Two"}]', encoding="utf-8")

    errors = validate_custom_queue(path)
    assert errors == [
        "custom_articles.json invalid JSON at line 2, column 1: "
        "Expecting ',' delimiter"
    ]


def test_repository_queue_contains_both_active_custom_articles():
    queue = json.loads(Path("custom_articles.json").read_text(encoding="utf-8"))
    headlines = {item["headline"] for item in queue}
    assert headlines == {
        "Hurricane Season Ready: 12 Treasure Coast Essentials to Stock Up On",
        "Port St. Lucie Police Unveil New $28 Million Training Facility",
    }
