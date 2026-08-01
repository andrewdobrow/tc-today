from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_STICKY_UID = "4edef44197"
MODAL_UID = "be625cadfe"
MODAL_SRC = "https://treasure-coast-today.kit.com/be625cadfe/index.js"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_shared_footer_delegates_kit_loading_to_main_javascript():
    source = _read("scripts/generate.py")
    assert '<script src="/main.js"></script>' in source
    assert f'data-uid="{LEGACY_STICKY_UID}"' not in source
    assert f'data-uid="{MODAL_UID}"' not in source


def test_main_javascript_loads_sitewide_modal_and_not_sticky_bar():
    js = _read("main.js")
    assert f'uid: "{MODAL_UID}"' in js
    assert f'src: "{MODAL_SRC}"' in js
    assert 'mode: "sitewide-modal"' in js
    assert LEGACY_STICKY_UID not in js
    assert "KIT STICKY BAR LAYERING" not in js
    assert "kit-sticky-visible" not in js


def test_sitewide_modal_loader_initializes_exactly_once():
    js = _read("main.js")
    assert 'document.querySelector(`script[data-uid="${config.uid}"]`)' in js
    assert 'script.dataset.tctNewsletterMode = config.mode' in js
    assert 'document.body.appendChild(script)' in js
    assert "window.setTimeout(loadSitewideKitModal, 0)" in js
