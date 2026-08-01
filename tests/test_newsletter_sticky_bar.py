from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_UID = "4edef44197"
DESKTOP_SRC = "https://treasure-coast-today.kit.com/4edef44197/index.js"
MOBILE_UID = "be625cadfe"
MOBILE_SRC = "https://treasure-coast-today.kit.com/be625cadfe/index.js"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_shared_footer_delegates_responsive_kit_loading_to_main_javascript():
    source = _read("scripts/generate.py")
    assert '<script src="/main.js"></script>' in source
    assert f'data-uid="{DESKTOP_UID}"' not in source
    assert f'data-uid="{MOBILE_UID}"' not in source


def test_main_javascript_contains_desktop_sticky_and_mobile_modal_embeds():
    js = _read("main.js")
    assert f'uid: "{DESKTOP_UID}"' in js
    assert f'src: "{DESKTOP_SRC}"' in js
    assert 'mode: "desktop-sticky"' in js
    assert f'uid: "{MOBILE_UID}"' in js
    assert f'src: "{MOBILE_SRC}"' in js
    assert 'mode: "mobile-modal"' in js


def test_responsive_loader_selects_exactly_one_kit_presentation():
    js = _read("main.js")
    assert 'const config = mobileQuery.matches ? embeds.mobile : embeds.desktop' in js
    assert 'document.querySelector(`script[data-uid="${config.uid}"]`)' in js
    assert 'script.dataset.tctNewsletterMode = config.mode' in js
    assert 'document.body.appendChild(script)' in js


def test_breakpoint_crossing_reloads_to_cleanly_swap_kit_presentations():
    js = _read("main.js")
    assert 'const initialMobileState = mobileQuery.matches' in js
    assert 'if (event.matches !== initialMobileState) window.location.reload()' in js
