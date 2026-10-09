from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from tct_engine.membership_paywall import FULL_BODY_MARKER, is_paywall_exempt_slug

ROOT = Path(__file__).resolve().parents[1]
PACKARD_SLUG = "2026-10-04-three-generations-later-packard-roofing-remains-rooted-on-the-treasure-coast"


def _load_script(name: str, filename: str):
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def _long_body() -> str:
    return (
        "<p>Packard Roofing has served Treasure Coast homeowners for decades, with the family business now led by a third generation that continues the company’s local operations.</p>"
        "<p>This sponsored feature includes the company history, leadership transition, service area and the long-term employees who helped build the business across Martin, St. Lucie and Indian River counties.</p>"
        "<p>The final section contains enough additional reporting and sponsor information to make this article long enough for the ordinary membership splitter, which is exactly why the explicit public-access exemption must be deterministic.</p>"
    )


def _free_page(body: str) -> str:
    return (
        '<!doctype html><html><head><script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"NewsArticle","isAccessibleForFree":true}'
        '</script></head><body>'
        '<h1 class="article-headline">Three generations later, Packard Roofing remains rooted on the Treasure Coast</h1>'
        f'<div class="article-body">{body}</div>'
        '<p class="article-sponsored-partnership">This article was produced in partnership with Packard Roofing &amp; Waterproofing.</p>'
        '<div class="article-share">share</div></body></html>'
    )


def test_packard_slug_is_explicitly_paywall_exempt():
    assert is_paywall_exempt_slug(PACKARD_SLUG)
    assert not is_paywall_exempt_slug("ordinary-editorial-story")


def test_prepare_membership_leaves_packard_fully_public(tmp_path, monkeypatch):
    module = _load_script("prepare_membership_packard_free", "prepare_membership_paywall.py")
    articles = tmp_path / "articles"
    articles.mkdir()
    body = _long_body()
    article = articles / f"{PACKARD_SLUG}.html"
    article.write_text(_free_page(body), encoding="utf-8")
    export = tmp_path / "protected.json"

    monkeypatch.setattr(module, "ARTICLES", articles)
    monkeypatch.setenv("TCT_MEMBERSHIP_UI_ENABLED", "true")
    monkeypatch.setenv("TCT_PROTECTED_EXPORT_PATH", str(export))
    monkeypatch.delenv("TCT_PROTECTED_SNAPSHOT_PATH", raising=False)
    module.main()

    public = article.read_text(encoding="utf-8")
    payload = json.loads(export.read_text(encoding="utf-8"))
    assert "data-tct-paywall" not in public
    assert "tct-member-preview" not in public
    assert "explicit public-access exemption" in public
    assert '"isAccessibleForFree":true' in public
    assert payload == {"articles": []}


def test_prepare_rehydrates_previously_paywalled_packard_and_keeps_it_free(tmp_path, monkeypatch):
    module = _load_script("prepare_membership_packard_rehydrate", "prepare_membership_paywall.py")
    articles = tmp_path / "articles"
    articles.mkdir()
    body = _long_body()
    preview = "Packard Roofing has served Treasure Coast homeowners for decades."
    old_page = (
        '<!doctype html><html><head><script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"NewsArticle","isAccessibleForFree":false,'
        '"hasPart":{"@type":"WebPageElement","isAccessibleForFree":false,"cssSelector":".tct-paywalled-content"}}'
        '</script></head><body>'
        f'<div class="article-body tct-member-preview"><p>{preview}</p></div>'
        f'<div class="tct-member-only"><section class="tct-paywall" data-tct-paywall data-slug="{PACKARD_SLUG}"></section>'
        '<div id="tct-protected-content" class="article-body tct-protected-content tct-paywalled-content"></div></div>'
        '<div class="article-share">share</div></body></html>'
    )
    article = articles / f"{PACKARD_SLUG}.html"
    article.write_text(old_page, encoding="utf-8")
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps({"articles": [{"slug": PACKARD_SLUG, "protected_body": FULL_BODY_MARKER + body}]}),
        encoding="utf-8",
    )
    export = tmp_path / "protected.json"

    monkeypatch.setattr(module, "ARTICLES", articles)
    monkeypatch.setenv("TCT_MEMBERSHIP_UI_ENABLED", "true")
    monkeypatch.setenv("TCT_PROTECTED_EXPORT_PATH", str(export))
    monkeypatch.setenv("TCT_PROTECTED_SNAPSHOT_PATH", str(snapshot))
    module.main()

    public = article.read_text(encoding="utf-8")
    payload = json.loads(export.read_text(encoding="utf-8"))
    assert "data-tct-paywall" not in public
    assert "tct-member-preview" not in public
    assert "explicit public-access exemption" in public
    assert '"isAccessibleForFree":true' in public
    assert '"hasPart"' not in public
    assert payload == {"articles": []}


def test_fallback_protected_scan_skips_packard(tmp_path, monkeypatch):
    module = _load_script("sync_protected_packard_free", "sync_protected_articles.py")
    articles = tmp_path / "articles"
    articles.mkdir()
    body = _long_body()
    (articles / f"{PACKARD_SLUG}.html").write_text(_free_page(body), encoding="utf-8")
    ordinary_slug = "ordinary-long-editorial-story"
    (articles / f"{ordinary_slug}.html").write_text(
        '<html><body><div class="article-body">' + body + '</div></body></html>', encoding="utf-8"
    )
    monkeypatch.setattr(module, "ROOT", tmp_path)

    rows = module.scan_public_articles()
    assert [row["slug"] for row in rows] == [ordinary_slug]
