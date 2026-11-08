"""The retired sticky bar and popup must not return through main.js."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_generator_retains_main_script_without_sitewide_kit_popup():
    source = (ROOT / "scripts/generate.py").read_text(encoding="utf-8")
    assert re.search(r'<script\s+src=["\']/main\.js(?:\?v=[^"\']+)?["\']\s*></script>', source)
    assert "be625cadfe" not in source


def test_sitewide_kit_popup_and_sticky_bar_are_both_disabled():
    js = (ROOT / "main.js").read_text(encoding="utf-8")
    assert "be625cadfe" not in js
    assert "4edef44197" not in js
    assert "loadSitewideKitModal" not in js
    assert "kit-sticky-visible" not in js
