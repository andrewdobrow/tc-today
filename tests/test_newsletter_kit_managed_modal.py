"""Kit owns newsletter popup timing; TCT only loads the official embed.

Regression for the Nov 5 rollout: first-party 50% scroll gate and manual
click created a second trigger that conflicted with Kit's own 50% setting.
Keep the accessible close button and dismissal fallback intact.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _modal_script() -> str:
    js = (ROOT / "main.js").read_text(encoding="utf-8")
    return js.split("// -- SITEWIDE KIT NEWSLETTER MODAL --", 1)[1].split(
        "// -- FIRST-PARTY MOST READ", 1
    )[0]


def test_kit_embed_loads_once_at_initialization_without_firing_popup():
    script = _modal_script()
    assert script.count('uid: "be625cadfe"') == 1
    assert "window.setTimeout(loadSitewideKitModal, 0)" in script
    assert 'document.querySelector(`script[data-uid="${config.uid}"]`)' in script
    assert "script.src = config.src;" in script
    assert "document.body.appendChild(script);" in script
    for obsolete in (
        "SCROLL_THRESHOLD", "maybeLoadSitewideKitModal", "data-formkit-toggle",
        "trigger.click()", "requestAnimationFrame", "scrollableDistance",
    ):
        assert obsolete not in script


def test_existing_easy_to_dismiss_mobile_controls_are_preserved():
    script = _modal_script()
    assert 'const dismissCopy = "No thanks, I’ll keep reading";' in script
    assert 'dismiss.className = "tct-kit-modal-dismiss"' in script
    assert 'Dismiss newsletter signup and continue reading' in script
    assert 'submit.insertAdjacentElement("afterend", dismiss)' in script
    assert "new MutationObserver" in script
    assert "close.click()" in script
    assert 'key: "Escape"' in script


def test_mobile_modal_touch_target_is_unchanged():
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    assert ".tct-kit-modal-dismiss {" in css
    assert "min-height: 44px !important;" in css
    assert "text-decoration: underline !important;" in css


def test_sitewide_script_cache_version_is_refreshed():
    audience = (ROOT / "scripts/build_audience_features.py").read_text(encoding="utf-8")
    home = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'ASSET_VERSION = "1.13.9.120"' in audience
    assert "/main.js?v=1.13.9.120" in home
