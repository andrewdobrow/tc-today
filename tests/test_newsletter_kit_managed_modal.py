"""Kit owns newsletter popup timing; TCT only loads the official embed.

Regression for the Nov 5 rollout: first-party 50% scroll gate and manual
click created a second trigger that conflicted with Kit's own 50% setting.
Do not add first-party dismissal controls or popup triggers.
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


def test_kit_exclusively_controls_modal_ui_and_lifecycle():
    script = _modal_script()
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    for forbidden in (
        "MutationObserver", "tct-kit-modal-dismiss", "dismissCopy",
        "formkit-close", "KeyboardEvent", "addMobileDismissLink",
        "trigger.click()", "scroll", "requestAnimationFrame",
    ):
        assert forbidden not in script
    assert ".tct-kit-modal-dismiss" not in css


def test_sitewide_script_cache_version_is_refreshed():
    audience = (ROOT / "scripts/build_audience_features.py").read_text(encoding="utf-8")
    home = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'ASSET_VERSION = "1.13.9.124"' in audience
    assert "/main.js?v=1.13.9.124" in home


def test_initialization_inserts_only_the_official_kit_embed_once():
    """Exercise the loader: no synthetic popup click and no scroll listener."""
    import json
    import shutil
    import subprocess
    import pytest

    if not shutil.which("node"):
        pytest.skip("Node.js is unavailable for JS behavioral test")
    modal = _modal_script()
    begin = modal.index("  function loadSitewideKitModal() {")
    end = modal.index("\n})();", begin)
    loader = modal[begin:end]
    script = """
const config = { uid: "be625cadfe", src: "https://treasure-coast-today.kit.com/be625cadfe/index.js", mode: "sitewide-modal" };
let inserted = 0;
let popupCommands = 0;
let scheduled;
const document = {
  querySelector(sel) { return inserted ? {} : null; },
  createElement(tag) {
    if (tag !== "script") throw new Error("unexpected element: " + tag);
    return { dataset: {}, setAttribute() { throw new Error("unexpected manual trigger"); } };
  },
  body: { appendChild(node) {
    inserted++;
    if (node.dataset.uid !== config.uid || node.src !== config.src) throw new Error("incorrect embed");
  } }
};
const window = {
  setTimeout(callback, delay) {
    if (delay !== 0) throw new Error("unexpected timeout");
    scheduled = callback;
  },
  addEventListener() { throw new Error("unexpected first-party scroll trigger"); }
};
""" + loader + """
const before = inserted;
scheduled();
scheduled();
console.log(JSON.stringify({before, inserted, popupCommands}));
"""
    result = subprocess.run(
        ["node", "-e", script], cwd=ROOT, capture_output=True, text=True,
        check=False
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "before": 0, "inserted": 1, "popupCommands": 0
    }


def test_native_kit_embed_is_direct_and_deploy_safe():
    """Kit loads independently from main.js; repeated passes cannot duplicate it."""
    from scripts.replace_header_app_store import ensure_official_kit_embed

    embed = (
        '<script async data-uid="be625cadfe" '
        'src="https://treasure-coast-today.kit.com/be625cadfe/index.js"></script>'
    )
    for name in ("index.html", "events.html"):
        page = (ROOT / name).read_text(encoding="utf-8")
        assert page.count(embed) == 1, name
        assert page.index(embed) < page.index('<script src="/main.js'), name
        assert ensure_official_kit_embed(page) == page, name

    old_page = (
        '<html><body><header class="site-masthead"></header>'
        '<script src="/main.js?v=1.13.9.122"></script></body></html>'
    )
    migrated = ensure_official_kit_embed(old_page)
    assert migrated.count(embed) == 1
    assert migrated.index(embed) < migrated.index('<script src="/main.js')
    assert ensure_official_kit_embed(migrated) == migrated


def test_all_deploy_pipelines_install_native_kit_embed():
    for workflow in (
        ".github/workflows/update.yml",
        ".github/workflows/update-events.yml",
        ".github/workflows/update-missing-persons.yml",
    ):
        text = (ROOT / workflow).read_text(encoding="utf-8")
        assert "python scripts/replace_header_app_store.py" in text, workflow
