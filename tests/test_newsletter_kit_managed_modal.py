"""The Kit popup is deliberately disabled for a temporary SEO experiment.

Inline Morning Brief forms are still enabled. Every workflow's final HTML
reconciliation must remove popup embeds even from old archived pages.
"""
from pathlib import Path

from scripts.replace_header_app_store import remove_kit_popup_embed, replace_header_promo

ROOT = Path(__file__).resolve().parents[1]
POPUP_UID = "be625cadfe"
INLINE_UID = "30e15672d3"
POPUP = (
    '<script async data-uid="be625cadfe" '
    'src="https://treasure-coast-today.kit.com/be625cadfe/index.js"></script>'
)
INLINE = (
    '<script async data-uid="30e15672d3" '
    'src="https://treasure-coast-today.kit.com/30e15672d3/index.js"></script>'
)


def test_main_javascript_does_not_load_sitewide_popup():
    js = (ROOT / "main.js").read_text(encoding="utf-8")
    assert POPUP_UID not in js
    assert "loadSitewideKitModal" not in js


def test_pages_and_generator_do_not_embed_popup():
    for name in ("index.html", "events.html", "news-tip.html"):
        html = (ROOT / name).read_text(encoding="utf-8")
        assert POPUP_UID not in html, name
    audience = (ROOT / "scripts/build_audience_features.py").read_text(encoding="utf-8")
    assert POPUP_UID not in audience
    homepage = (ROOT / "index.html").read_text(encoding="utf-8")
    assert INLINE_UID in homepage


def test_legacy_popup_is_removed_without_touching_inline_kit_forms():
    html = (
        '<html><body><header class="site-masthead"></header>\n'
        + POPUP + '\n' + INLINE +
        '<script src="/main.js?v=1.13.9.124"></script></body></html>'
    )
    cleaned = remove_kit_popup_embed(html)
    assert POPUP_UID not in cleaned
    assert cleaned.count(INLINE_UID) == 2
    assert '/main.js?v=1.13.9.124' in cleaned
    assert remove_kit_popup_embed(cleaned) == cleaned
    reconciled = replace_header_promo(html)
    assert POPUP_UID not in reconciled
    assert INLINE_UID in reconciled
    assert '/main.js?v=1.13.9.125' in reconciled
    assert replace_header_promo(reconciled) == reconciled


def test_both_attribute_orders_are_removed():
    src_first = (
        '<script src="https://treasure-coast-today.kit.com/be625cadfe/index.js" '
        'async data-uid="be625cadfe"></script>'
    )
    assert not remove_kit_popup_embed(src_first).strip()
    assert remove_kit_popup_embed(INLINE) == INLINE


def test_all_deployment_workflows_strip_retired_popup():
    for name in (
        ".github/workflows/update.yml",
        ".github/workflows/update-events.yml",
        ".github/workflows/update-missing-persons.yml",
    ):
        workflow = (ROOT / name).read_text(encoding="utf-8")
        assert "python scripts/replace_header_app_store.py" in workflow, name
