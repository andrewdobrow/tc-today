from __future__ import annotations

import importlib
import json
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
                self.messages = types.SimpleNamespace(
                    create=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("unexpected Claude call"))
                )

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


class _Response:
    def __init__(self, text: str):
        self.status_code = 200
        self.text = text
        self.content = [types.SimpleNamespace(text=text)]


def _article_text() -> str:
    sentences = []
    for index in range(20):
        sentences.append(
            f"Sentence {index} contains enough verified local reporting words to survive the article extraction cleanup filter today."
        )
    return " ".join(sentences)


def _publishable_body(words: int) -> str:
    first = " ".join(["verified"] * (words // 2)) + "."
    second = " ".join(["reported"] * (words - words // 2)) + "."
    return first + "\n\n" + second


def test_source_text_cache_avoids_second_network_fetch(tmp_path: Path, monkeypatch):
    generate = _load_generate_module()
    cache = generate.PersistentGenerationCache(tmp_path / "generation-cache.json")
    monkeypatch.setattr(generate, "GENERATION_CACHE", cache)

    calls = []
    html = f'<script type="application/ld+json">{json.dumps({"articleBody": _article_text()})}</script>'

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        return _Response(html)

    monkeypatch.setattr(generate.requests, "get", fake_get)
    first = generate.fetch_article_text(
        "https://example.com/story?utm_source=rss",
        content_hint="stable-feed-fingerprint",
    )
    second = generate.fetch_article_text(
        "https://example.com/story",
        content_hint="stable-feed-fingerprint",
    )

    assert len(first.split()) >= 140
    assert second == first
    assert len(calls) == 1


def test_source_hint_change_invalidates_cached_text(tmp_path: Path, monkeypatch):
    generate = _load_generate_module()
    cache = generate.PersistentGenerationCache(tmp_path / "generation-cache.json")
    monkeypatch.setattr(generate, "GENERATION_CACHE", cache)

    calls = []

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        html = f'<script type="application/ld+json">{json.dumps({"articleBody": _article_text()})}</script>'
        return _Response(html)

    monkeypatch.setattr(generate.requests, "get", fake_get)
    generate.fetch_article_text("https://example.com/story", content_hint="version-one")
    generate.fetch_article_text("https://example.com/story", content_hint="version-two")

    assert len(calls) == 2


def test_classification_only_sends_cache_misses_to_claude(tmp_path: Path, monkeypatch):
    generate = _load_generate_module()
    cache = generate.PersistentGenerationCache(tmp_path / "generation-cache.json")
    monkeypatch.setattr(generate, "GENERATION_CACHE", cache)

    cached_story = {"title": "Cached Stuart council story", "summary": "A Stuart council vote affected residents."}
    cached_key = generate._classification_cache_key(cached_story)
    cache.put(
        "classifications",
        cached_key,
        {"title": cached_story["title"], "categories": ["local_gov", "martin"]},
    )

    calls = []

    class _Messages:
        def create(self, **kwargs):
            calls.append(kwargs)
            return _Response('{"1": ["crime", "st_lucie"]}')

    monkeypatch.setattr(generate, "client", types.SimpleNamespace(messages=_Messages()))
    feed_cache = {
        "feed": [
            {"title": cached_story["title"], "summary": cached_story["summary"]},
            {"title": "New Fort Pierce arrest story", "summary": "Police announced an arrest in Fort Pierce."},
        ]
    }

    result = generate.classify_stories(feed_cache)

    assert result[cached_story["title"].lower()] == {"local_gov", "martin"}
    assert result["new fort pierce arrest story"] == {"crime", "st_lucie"}
    assert len(calls) == 1
    prompt = calls[0]["messages"][0]["content"]
    assert "New Fort Pierce arrest story" in prompt
    assert "Cached Stuart council story" not in prompt


def test_publishable_second_passes_skip_claude(monkeypatch):
    generate = _load_generate_module()

    class _Messages:
        def create(self, **kwargs):
            raise AssertionError("publishable copy must not trigger a second Claude rewrite")

    monkeypatch.setattr(generate, "client", types.SimpleNamespace(messages=_Messages()))
    source = {
        "title": "Local source",
        "link": "https://example.com/local",
        "source_type": "full_source",
        "source_quality": "full",
        "article_text": _article_text(),
        "summary": _article_text(),
    }
    card = {
        "headline": "Local card headline",
        "body": _publishable_body(100),
        "source_index": 1,
        "source_quality": "full",
        "source_word_count": 160,
    }
    hero = {
        "headline": "Local hero headline",
        "body": _publishable_body(140),
        "source_quality": "full",
        "source_word_count": 160,
    }

    assert generate.enhance_card(card, [], [source])["enriched"] is True
    assert generate.enhance_hero_article(hero, _article_text())["enriched"] is True


def test_category_generation_key_changes_with_source_content():
    generate = _load_generate_module()
    base = [{
        "title": "Martin County meeting",
        "link": "https://example.com/meeting?utm_source=rss",
        "published": "Fri, 24 Jul 2026 10:00:00 GMT",
        "source_type": "full_source",
        "source_quality": "full",
        "hero_eligible": "yes",
        "category_match_score": 10,
        "article_text": "Original source body",
    }]
    same = [dict(base[0], link="https://example.com/meeting")]
    changed = [dict(base[0], article_text="Materially updated source body")]

    assert generate._category_generation_cache_key("martin", base) == generate._category_generation_cache_key("martin", same)
    assert generate._category_generation_cache_key("martin", base) != generate._category_generation_cache_key("martin", changed)


def test_production_workflow_restores_incremental_cache():
    workflow = Path(".github/workflows/update.yml").read_text(encoding="utf-8")
    assert "actions/cache@v4" in workflow
    assert "data/generation-cache.json" in workflow
    assert "timeout-minutes: 90" in workflow
    assert "ACTIVE_WORKFLOW=tct-incremental-generation-v1.9.4" in workflow


def test_generation_cache_persists_across_process_runs(tmp_path: Path):
    generate = _load_generate_module()
    path = tmp_path / "generation-cache.json"
    first = generate.PersistentGenerationCache(path)
    first.put("classifications", "story-key", {"categories": ["martin"]})
    first.save()

    second = generate.PersistentGenerationCache(path)
    cached = second.get("classifications", "story-key")

    assert cached == {"categories": ["martin"]}
    assert path.exists()
    assert not path.with_suffix(".json.tmp").exists()
