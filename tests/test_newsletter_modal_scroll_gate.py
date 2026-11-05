"""Behavioral regression for sitewide newsletter modal's 50% scroll gate.

Kit controls the modal once its embed is loaded. The first-party site must not
load that embed before a user has traveled half the available scroll distance.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS_FILE = ROOT / "main.js"


def _gate_source() -> str:
    source = JS_FILE.read_text(encoding="utf-8")
    beginning = source.index("  // Kit can display its own modal immediately")
    ending = source.index("\n})();", beginning)
    return source[beginning:ending]


def _simulate(initial_y=0, page_height=2000, viewport_height=1000, later_y=(499, 500, 850)):
    if not shutil.which("node"):
        pytest.skip("Node.js unavailable for JS behavioral regression")
    js = """
const callbacks = {};
const window = {
  innerHeight: __VIEWPORT__,
  scrollY: __INITIAL__,
  addEventListener(type, fn) { callbacks[type] = fn; },
  removeEventListener(type, fn) {
    if (callbacks[type] === fn) delete callbacks[type];
  }
};
const document = {
  documentElement: { scrollHeight: __PAGE__, scrollTop: 0 },
  body: { scrollHeight: __PAGE__ }
};
let kitLoads = 0;
function loadSitewideKitModal() { kitLoads++; }
""" 
    js = (js.replace("__VIEWPORT__", str(viewport_height))
            .replace("__INITIAL__", str(initial_y))
            .replace("__PAGE__", str(page_height)))
    js += _gate_source()
    js += "\nconst observed = [kitLoads];\n"
    for y in later_y:
        js += f"window.scrollY = {y}; callbacks.scroll?.(); observed.push(kitLoads);\n"
    js += "console.log(JSON.stringify(observed));"
    run = subprocess.run(["node", "-e", js], text=True, capture_output=True, check=False, cwd=ROOT)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_no_modal_on_page_load_or_at_49_percent_scroll():
    assert _simulate() == [0, 0, 1, 1]


def test_reader_arriving_at_half_page_has_gate_triggered_once():
    assert _simulate(initial_y=500, later_y=(500, 900)) == [1, 1, 1]


def test_short_page_does_not_auto_trigger_a_newsletter_modal():
    assert _simulate(page_height=800, viewport_height=1000, later_y=(0, 100, 500)) == [0, 0, 0, 0]


def test_no_timer_or_exit_intent_can_bypass_the_gate():
    source = JS_FILE.read_text(encoding="utf-8")
    section = source[source.index("// -- SITEWIDE KIT NEWSLETTER MODAL --"):
                     source.index("// -- FIRST-PARTY MOST READ")]
    assert "window.setTimeout(loadSitewideKitModal, 0)" not in section
    assert 'window.addEventListener("scroll", maybeLoadSitewideKitModal' in section
    assert 'window.addEventListener("load", maybeLoadSitewideKitModal' in section
    assert 'script.dataset.uid = config.uid' in section
    assert 'No thanks, I’ll keep reading' in section


def test_asset_version_is_bumped_to_prevent_cached_immediate_modal():
    builder = (ROOT / "scripts/build_audience_features.py").read_text(encoding="utf-8")
    homepage = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'ASSET_VERSION = "1.13.9.119"' in builder
    assert '/main.js?v=1.13.9.119' in homepage
