from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda *args, **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    path = ROOT / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_release_contract_coherence", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_generator_active_release_contracts_survive_together(tmp_path, monkeypatch):
    """Catch stale whole-file overlays that silently roll back newer generator work."""
    g = _load_generate()

    # v1.13.6.2 subscriber chrome must coexist with later editorial hotfixes.
    monkeypatch.setattr(g, "MEMBERSHIP_UI_ENABLED", True)
    header = g._header_primary_cta_html()
    assert "data-membership-welcome" in header
    assert "Welcome, subscriber" in header

    page = tmp_path / "index.html"
    page.write_text(
        '<!doctype html><html><head></head><body><header><div class="header-actions">'
        '<a href="/advertise.html" class="support-btn">Advertise</a>'
        '</div></header></body></html>'
    )
    g._apply_membership_site_chrome(tmp_path)
    rendered = page.read_text()
    assert "data-tct-member-prepaint" in rendered
    assert 'src="/membership.js?v=1.13.7.1b"' in rendered

    # Martin cocaine production regression: a drug seizure is not an animal case,
    # and the deterministic historical fallback remains callable.
    families = g._cross_source_event_families({
        "headline": "17 arrested in Martin County cocaine bust",
        "body": "Deputies seized four kilograms of cocaine during a narcotics investigation.",
    })
    assert "drug-case" in families
    assert "animal-case" not in families
    assert callable(g._repair_verified_martin_cocaine_operation_duplicate)

    # v1.13.6.1e final-surface identity alignment: dedupe receives the full hero
    # object, not only its URL, so canonicalization and validation use one contract.
    source = (ROOT / "scripts" / "generate.py").read_text()
    assert "hero_item=hero" in source
    assert "missing_current_run_persistent_story_id" in source

    # v1.13.6.4 production-continuity boundary: the final rendered homepage is
    # deterministically repaired using the same persisted identity projection as
    # the strict validator before deployment can be aborted for a repairable card.
    assert "def repair_final_canonical_surface_projection(" in source
    repair_call = "repair_final_canonical_surface_projection(\n        index_html, OUTPUT_DIR"
    assert repair_call in source
    assert source.index(repair_call) < source.index(
        "validate_final_canonical_surface_uniqueness(index_html, OUTPUT_DIR)"
    )
