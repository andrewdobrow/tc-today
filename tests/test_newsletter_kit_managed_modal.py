"""Sitewide Kit popup uses the official HTML embed, Kit-owned behavior only.

No first-party scroll, timeout, modal close or audience-targeting code.
Inline Kit forms are kept alongside the sitewide popup.
"""
from pathlib import Path

from scripts.replace_header_app_store import (
    KIT_MODAL_EMBED, ensure_kit_modal_embed, replace_header_promo,
    CSS_ASSET_VERSION
)

ROOT = Path(__file__).resolve().parents[1]
POPUP_UID = "be625cadfe"
INLINE_UID = "30e15672d3"


def test_kit_code_is_direct_embed_not_custom_triggers():
    assert KIT_MODAL_EMBED == (
        '<script async data-uid="be625cadfe" '
        'src="https://treasure-coast-today.kit.com/be625cadfe/index.js"></script>'
    )
    js = (ROOT / "main.js").read_text(encoding="utf-8")
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    assert POPUP_UID not in js
    assert "loadSitewideKitModal" not in js
    assert "data-formkit-toggle" not in js
    assert ".formkit-modal" not in css
    assert ".formkit-overlay" not in css


def test_home_events_and_news_tip_have_single_native_kit_embed():
    for path in ("index.html", "events.html", "news-tip.html"):
        page = (ROOT / path).read_text(encoding="utf-8")
        assert page.count(KIT_MODAL_EMBED) == 1, path
        assert page.index(KIT_MODAL_EMBED) < page.index('<script src="/main.js'), path
        assert ensure_kit_modal_embed(page) == page, path
    homepage = (ROOT / "index.html").read_text(encoding="utf-8")
    assert f'data-uid="{INLINE_UID}"' in homepage


def test_reconcile_upgrades_absent_or_duplicate_modal_without_touching_inline():
    inline = '<script async data-uid="30e15672d3" src="https://treasure-coast-today.kit.com/30e15672d3/index.js"></script>'
    before = (
        '<html><body><header class="site-masthead"></header>'
        + inline + f'<script src="/main.js?v={CSS_ASSET_VERSION}"></script></body></html>'
    )
    upgraded = ensure_kit_modal_embed(before)
    assert upgraded.count(KIT_MODAL_EMBED) == 1
    assert upgraded.count(inline) == 1
    assert upgraded.index(KIT_MODAL_EMBED) < upgraded.index('<script src="/main.js')
    assert ensure_kit_modal_embed(upgraded) == upgraded
    duplicated = upgraded.replace(KIT_MODAL_EMBED, KIT_MODAL_EMBED + KIT_MODAL_EMBED)
    deduped = ensure_kit_modal_embed(duplicated)
    assert deduped.count(KIT_MODAL_EMBED) == 1
    assert deduped.count(inline) == 1
    assert replace_header_promo(deduped) == deduped


def test_kit_script_attribute_order_is_deduplicated():
    alt = (
        '<script src="https://treasure-coast-today.kit.com/be625cadfe/index.js" '
        'async data-uid="be625cadfe"></script>'
    )
    page = '<html><body><header class="site-masthead"></header>' + alt + '</body></html>'
    result = ensure_kit_modal_embed(page)
    assert result.count(KIT_MODAL_EMBED) == 1
    assert 'src="https://treasure-coast-today.kit.com/be625cadfe/index.js" async' not in result


def test_generator_and_all_publishing_pipelines_preserve_kit_embed():
    audience = (ROOT / "scripts/build_audience_features.py").read_text(encoding="utf-8")
    assert 'data-uid="be625cadfe"' in audience
    assert "kit_tag" in audience
    for path in (
        ".github/workflows/update.yml",
        ".github/workflows/update-events.yml",
        ".github/workflows/update-missing-persons.yml",
    ):
        workflow = (ROOT / path).read_text(encoding="utf-8")
        assert "python scripts/replace_header_app_store.py" in workflow, path
