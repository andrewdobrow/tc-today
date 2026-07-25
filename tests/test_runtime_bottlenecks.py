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

        class _Feed:
            def __init__(self, entries=None, feed=None):
                self.entries = entries or []
                self.feed = feed or {}

        feedparser.parse = lambda *args, **kwargs: _Feed()
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


def _feed(entries=None, title="Test feed"):
    return types.SimpleNamespace(entries=entries or [], feed={"title": title})


def test_image_and_content_banks_reuse_shared_prefetch(monkeypatch):
    generate = _load_generate_module()
    documents = {
        url: _feed() for url in set(generate.IMAGE_BANK_FEEDS) | set(generate.CONTENT_BANK_FEEDS)
    }
    image_url = generate.IMAGE_BANK_FEEDS[0]
    content_url = generate.CONTENT_BANK_FEEDS[0]
    documents[image_url] = _feed([{"title": "Stuart council update", "image": "present"}])
    documents[content_url] = _feed([{
        "title": "Martin County budget workshop",
        "summary": "Verified local summary " * 12,
    }], title="Local publisher")

    monkeypatch.setattr(
        generate,
        "_fetch_feed_document",
        lambda url: (_ for _ in ()).throw(AssertionError("bank attempted a second network fetch")),
    )
    monkeypatch.setattr(generate, "extract_image", lambda entry: "https://example.com/image.jpg")

    image_bank = generate.build_image_bank(documents)
    content_bank = generate.build_content_bank(documents)

    assert any(item["image_url"] == "https://example.com/image.jpg" for item in image_bank)
    assert any(item["source"] == "Local publisher" for item in content_bank)


def test_shared_prefetch_deduplicates_urls(monkeypatch):
    generate = _load_generate_module()
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return _feed([{"title": url}])

    monkeypatch.setattr(generate, "_fetch_feed_document", fake_fetch)
    documents = generate._prefetch_feed_documents([
        "https://example.com/a.xml",
        "https://example.com/a.xml",
        "https://example.com/b.xml",
    ])

    assert set(documents) == {"https://example.com/a.xml", "https://example.com/b.xml"}
    assert sorted(calls) == ["https://example.com/a.xml", "https://example.com/b.xml"]


def test_stable_registry_membership_skips_all_pairs_reclustering(tmp_path: Path, monkeypatch):
    generate = _load_generate_module()
    archive = [
        {"slug": "alpha", "headline": "Stuart approves waterfront plan", "date": "2026-07-20", "category_key": "local_gov"},
        {"slug": "bravo", "headline": "Fort Pierce opens neighborhood park", "date": "2026-07-21", "category_key": "st_lucie"},
        {"slug": "charlie", "headline": "Vero Beach hosts summer concert", "date": "2026-07-22", "category_key": "things_to_do"},
    ]
    stories = []
    for index, item in enumerate(archive, 1):
        stories.append({
            "story_id": f"story-{index}",
            "title": item["headline"],
            "articles": [{"slug": item["slug"]}],
            "historical_slugs": [item["slug"]],
            "article_count": 1,
            "created_at": "2026-07-20T00:00:00Z",
        })
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "story-registry.json").write_text(
        json.dumps({"schema_version": 7.1, "stories": stories}), encoding="utf-8"
    )

    monkeypatch.setattr(
        generate,
        "_same_story_topic",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("stable registered stories were compared again")
        ),
    )

    report = generate.build_story_shadow(archive, current_customs=[], output_dir=tmp_path)

    assert report["summary"]["articles_analyzed"] == 3
    assert report["summary"]["stories_identified"] == 3


def test_reconcile_compares_only_groups_touched_by_new_articles(monkeypatch):
    generate = _load_generate_module()
    calls = []

    def fake_reconcile(left, right):
        calls.append((left[0]["headline"], right[0]["headline"]))
        return False, 0

    monkeypatch.setattr(generate, "_groups_should_reconcile", fake_reconcile)
    groups = [
        [{"headline": "stable one"}],
        [{"headline": "stable two"}],
        [{"headline": "new group"}],
    ]

    generate._reconcile_topic_groups(groups, [False, False, True])

    assert ("stable one", "stable two") not in calls
    assert len(calls) == 2
