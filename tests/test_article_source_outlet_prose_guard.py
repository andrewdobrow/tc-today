import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

# The production workflow installs these dependencies. The local regression test
# stubs them only so generate.py can be imported in lightweight test environments.
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
if "json_repair" not in sys.modules:
    json_repair = types.ModuleType("json_repair")
    json_repair.repair_json = lambda value: value
    sys.modules["json_repair"] = json_repair

from scripts import generate
from scripts import prepare_membership_paywall as prepare
from tct_engine.article_prose_policy import (
    sanitize_article_body_html,
    sanitize_article_text,
)
from tct_engine.membership_paywall import FULL_BODY_MARKER


BAD_SENTENCE = "The store owner and manager declined to talk to WPBF News 25."


def test_exact_jensen_beach_outreach_sentence_is_removed_and_substance_survives():
    text = (
        BAD_SENTENCE
        + " Police said the SUV struck the storefront and damaged inventory."
    )
    cleaned = sanitize_article_text(
        text,
        source_url="https://www.wpbf.com/article/jensen-beach-bikes-plus-crash/123",
        source_headline="SUV crashes into Bikes Plus in Jensen Beach - WPBF",
    )
    assert "WPBF" not in cleaned
    assert "declined to talk" not in cleaned
    assert "Police said the SUV struck the storefront and damaged inventory." in cleaned


def test_source_outlet_reporting_attribution_is_removed_but_media_subject_is_preserved():
    attributed = sanitize_article_text(
        "WPBF News 25 reported that the store reopened Friday. Police said no one was hurt.",
        source_url="https://www.wpbf.com/article/example/123",
        source_headline="Store reopens after crash - WPBF",
    )
    assert attributed == "Police said no one was hurt."

    media_is_subject = sanitize_article_text(
        "WPBF's parent company announced a station sale. The deal is expected to close this year."
    )
    assert "WPBF's parent company announced a station sale." in media_is_subject


def test_html_guard_removes_only_the_prohibited_generated_paragraph():
    body = (
        f"<p>{BAD_SENTENCE}</p>"
        "<p>Police said the SUV struck the storefront and damaged inventory.</p>"
    )
    cleaned, changed = sanitize_article_body_html(
        body,
        source_url="https://www.wpbf.com/article/example/123",
        source_headline="SUV crash - WPBF",
    )
    assert changed == 1
    assert "WPBF" not in cleaned
    assert "Police said the SUV struck the storefront and damaged inventory." in cleaned


def test_hero_enrichment_cannot_reintroduce_competitor_or_outreach_language(monkeypatch):
    response = SimpleNamespace(
        content=[
            SimpleNamespace(
                text=(
                    BAD_SENTENCE
                    + " Police said the SUV struck the storefront and damaged inventory. "
                    + "The crash happened in Jensen Beach. " * 35
                )
            )
        ]
    )
    monkeypatch.setattr(
        generate,
        "client",
        SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response)),
    )
    monkeypatch.setattr(
        generate,
        "_publishable_article",
        lambda item, hero=False: "WPBF" not in str(item.get("body") or "") and len(str(item.get("body") or "")) > 120,
    )

    hero = {
        "headline": "SUV crashes into Bikes Plus in Jensen Beach",
        "body": "Short original.",
        "link": "https://www.wpbf.com/article/example/123",
        "source_title": "SUV crashes into Bikes Plus in Jensen Beach - WPBF",
    }
    result = generate.enhance_hero_article(hero, "Verified source material. " * 120)
    assert "WPBF" not in result["body"]
    assert "declined to talk" not in result["body"]
    assert "Police said the SUV struck the storefront" in result["body"]


def test_retained_generated_article_page_is_repaired_sitewide(tmp_path):
    root = tmp_path
    articles = root / "articles"
    articles.mkdir()
    slug = "2026-09-20-suv-crashes-into-bikes-plus-in-jensen-beach-damaging-inventory-and-storefront"
    (root / "archive.json").write_text(
        json.dumps(
            [
                {
                    "slug": slug,
                    "source_url": "https://www.wpbf.com/article/example/123",
                    "source_headline": "SUV crashes into Bikes Plus in Jensen Beach - WPBF",
                    "is_custom": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    page = (
        '<html><body><div class="article-body">'
        f"<p>{BAD_SENTENCE}</p>"
        "<p>Police said the SUV struck the storefront and damaged inventory.</p>"
        '</div><div class="article-share"></div></body></html>'
    )
    article_path = articles / f"{slug}.html"
    article_path.write_text(page, encoding="utf-8")

    report = generate._normalize_article_prose_policy_sitewide(root)
    repaired = article_path.read_text(encoding="utf-8")
    assert report["updated"] == 1
    assert report["paragraphs_changed"] == 1
    assert "WPBF" not in repaired
    assert "Police said the SUV struck the storefront and damaged inventory." in repaired


def test_membership_rehydration_cleans_protected_copy_before_resync(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    articles = root / "articles"
    articles.mkdir(parents=True)
    slug = "2026-09-20-suv-crashes-into-bikes-plus-in-jensen-beach-damaging-inventory-and-storefront"
    (root / "archive.json").write_text(
        json.dumps(
            [
                {
                    "slug": slug,
                    "source_url": "https://www.wpbf.com/article/example/123",
                    "source_headline": "SUV crashes into Bikes Plus in Jensen Beach - WPBF",
                    "is_custom": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    paywalled_page = (
        '<html><head><title>Test</title></head><body>'
        '<div class="article-body tct-member-preview"><p>Existing preview text.</p></div>'
        '<div class="tct-member-only">'
        '<div data-tct-paywall></div><div id="tct-protected-content"></div></div>'
        '<div class="article-share"></div></body></html>'
    )
    (articles / f"{slug}.html").write_text(paywalled_page, encoding="utf-8")

    long_good = (
        "Police said the SUV struck the Jensen Beach storefront and damaged bicycles and other inventory. "
        "No injuries were reported in the crash, and crews worked at the scene afterward. "
    )
    full_body = (
        f"<p>{long_good * 2}</p>"
        f"<p>{BAD_SENTENCE}</p>"
        f"<p>{long_good * 2}</p>"
        f"<p>{long_good * 2}</p>"
    )
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps({"articles": [{"slug": slug, "protected_body": FULL_BODY_MARKER + full_body}]}),
        encoding="utf-8",
    )
    export = tmp_path / "protected-export.json"

    monkeypatch.setattr(prepare, "ROOT", root)
    monkeypatch.setattr(prepare, "ARTICLES", articles)
    monkeypatch.setenv("TCT_MEMBERSHIP_UI_ENABLED", "true")
    monkeypatch.setenv("TCT_PROTECTED_SNAPSHOT_PATH", str(snapshot))
    monkeypatch.setenv("TCT_PROTECTED_EXPORT_PATH", str(export))

    prepare.main()

    public_page = (articles / f"{slug}.html").read_text(encoding="utf-8")
    protected_payload = export.read_text(encoding="utf-8")
    assert "WPBF" not in public_page
    assert "WPBF" not in protected_payload
    assert "declined to talk" not in public_page
    assert "declined to talk" not in protected_payload
