from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_modal_is_not_hardcoded_into_generated_page_footer():
    source = (ROOT / "scripts" / "generate.py").read_text(encoding="utf-8")
    assert "be625cadfe" not in source


def test_same_modal_is_loaded_for_desktop_and_mobile():
    js = (ROOT / "main.js").read_text(encoding="utf-8")
    assert js.count('uid: "be625cadfe"') == 1
    assert 'mode: "sitewide-modal"' in js
    assert "matchMedia" not in js[js.index("// -- SITEWIDE KIT NEWSLETTER MODAL --"):]
    assert "4edef44197" not in js


def test_mobile_modal_keeps_generous_dismissible_border():
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    assert "width: calc(100vw - 48px) !important" in css
    assert "max-height: calc(100dvh - 64px) !important" in css
    assert "margin: 32px auto !important" in css
