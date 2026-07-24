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

        class _Messages:
            def create(self, *args, **kwargs):
                raise RuntimeError("AI calls are disabled in publisher regression tests")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = _Messages()

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic

    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def _canonical_entry(generate):
    return {
        "slug": generate.HOARDING_CANONICAL_SLUG,
        "headline": "More than 70 animals found in Stuart home during large-scale hoarding response",
        "teaser": "Martin County authorities removed cats and dogs from a Stuart-area home.",
        "is_custom": True,
        "authoritative_custom": True,
        "article_word_count": 700,
        "date": "2026-07-20",
        "lastmod": "2026-07-21",
    }


def test_known_hoarding_sources_are_upserted_to_permanent_custom_target(tmp_path):
    generate = _load_generate_module()
    articles_dir = tmp_path / "articles"
    articles_dir.mkdir()

    # Include a stale current-run decision that points at a former canonical URL.
    stale_source = next(iter(generate.HOARDING_REDIRECT_SOURCE_SLUGS))
    archive = [
        _canonical_entry(generate),
        {
            "slug": stale_source,
            "headline": "Martin County deputies rescue 80 cats from Stuart home",
            "teaser": "A later article about the same hoarding response.",
            "is_custom": True,
            "authoritative_custom": True,
            "article_word_count": 500,
            "date": "2026-07-21",
            "lastmod": "2026-07-21",
        },
    ]

    cleaned, redirects = generate.apply_canonical_story_cleanup(
        archive, articles_dir, tmp_path
    )

    redirect_by_source = {r["source_slug"]: r for r in redirects}
    assert set(redirect_by_source) == set(generate.HOARDING_REDIRECT_SOURCE_SLUGS)
    assert all(
        record["target_slug"] == generate.HOARDING_CANONICAL_SLUG
        for record in redirect_by_source.values()
    )
    assert all(
        sum(r["source_slug"] == source for r in redirects) == 1
        for source in generate.HOARDING_REDIRECT_SOURCE_SLUGS
    )
    assert not (set(generate.HOARDING_REDIRECT_SOURCE_SLUGS) & {e["slug"] for e in cleaned})
    assert generate.HOARDING_CANONICAL_SLUG in {e["slug"] for e in cleaned}


def test_story_regression_gate_passes_only_when_all_known_sources_target_custom(tmp_path):
    generate = _load_generate_module()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    story = {
        "story_id": "story-hoarding",
        "canonical_is_custom": True,
        "canonical_slug": generate.HOARDING_CANONICAL_SLUG,
        "articles": [
            {
                "headline": "Stuart woman arrested after deputies rescue about 80 cats from hoarding home",
                "teaser": "Martin County deputies said the animals were removed during a large-scale response.",
            }
        ],
    }
    (data_dir / "stories.json").write_text(json.dumps({"stories": [story]}))

    redirects = [
        {
            "source_slug": source,
            "target_slug": generate.HOARDING_CANONICAL_SLUG,
            "source_headline": "Previously published animal-hoarding duplicate",
            "reason": "Permanent regression migration to the authoritative TCT hoarding story.",
        }
        for source in generate.HOARDING_REDIRECT_SOURCE_SLUGS
    ]
    (data_dir / "canonical-redirects.json").write_text(json.dumps({"redirects": redirects}))

    archive = [_canonical_entry(generate)]
    verification = [{"passed": True} for _ in redirects]
    report = generate.write_story_regression_report(
        tmp_path, archive, verification
    )

    assert report["production_gate_passed"] is True
    assert report["checks"]["all_known_duplicate_redirects_exist"] is True
    assert report["checks"]["all_known_duplicate_redirects_target_custom"] is True


def test_story_regression_gate_rejects_stale_known_redirect_target(tmp_path):
    generate = _load_generate_module()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    story = {
        "story_id": "story-hoarding",
        "canonical_is_custom": True,
        "canonical_slug": generate.HOARDING_CANONICAL_SLUG,
        "articles": [
            {
                "headline": "Martin County deputies rescue 80 cats from Stuart hoarding home",
                "teaser": "The same animal-hoarding response.",
            }
        ],
    }
    (data_dir / "stories.json").write_text(json.dumps({"stories": [story]}))

    redirects = []
    for index, source in enumerate(generate.HOARDING_REDIRECT_SOURCE_SLUGS):
        redirects.append({
            "source_slug": source,
            "target_slug": (
                "2026-07-21-obsolete-hoarding-canonical"
                if index == 0 else generate.HOARDING_CANONICAL_SLUG
            ),
            "source_headline": "Previously published animal-hoarding duplicate",
            "reason": "Animal-hoarding migration",
        })
    (data_dir / "canonical-redirects.json").write_text(json.dumps({"redirects": redirects}))

    report = generate.write_story_regression_report(
        tmp_path,
        [_canonical_entry(generate)],
        [{"passed": True} for _ in redirects],
    )

    assert report["production_gate_passed"] is False
    assert report["checks"]["all_known_duplicate_redirects_exist"] is True
    assert report["checks"]["all_known_duplicate_redirects_target_custom"] is False
