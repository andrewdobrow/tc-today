"""Nov 11 production regression: coalesced quiet-zone update was context-held.

Two independently selected publisher URLs were consolidated into one final
canonical write. A real UPDATE CONTEXT HOLD must account for both selected
sources represented by that one transaction, without waiving unrelated updates.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


def _load_generate():
    if "feedparser" not in sys.modules:
        stub = types.ModuleType("feedparser")
        stub.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = stub
    if "anthropic" not in sys.modules:
        stub = types.ModuleType("anthropic")
        stub.Anthropic = lambda *args, **kwargs: types.SimpleNamespace(
            messages=types.SimpleNamespace(create=lambda *args, **kwargs: None)
        )
        sys.modules["anthropic"] = stub
    path = Path(__file__).parents[1] / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("quiet_zone_coalesced_hold_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SLUG = "2026-11-10-martin-county-commissioners-to-review-safety-requirements-for-train-quiet-zones"
WFLX = "https://www.wflx.com/2026/11/10/martin-county-approves-quiet-zones-three-crossings"
WPTV = "https://www.wptv.com/news/treasure-coast/region-martin-county/martin-county-to-establish-some-quiet-zones-to-combat-train-noise"


def _setup(g, tmp_path):
    g.CURRENT_RUN_SELECTED_MATERIAL_UPDATE_TARGETS = {
        SLUG: {
            "canonical_slug": SLUG,
            "canonical_headline": "Martin County commissioners to review quiet-zone safety Tuesday",
            "selected_headlines": ["Martin County approves quiet zones at three crossings"],
            "source_headlines": ["WFLX quiet zones", "WPTV quiet zones"],
            "source_urls": [WFLX, WPTV],
        }
    }
    g.CURRENT_RUN_MATERIAL_UPDATE_WAIVERS = {}
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "semantic-publication-gate.json").write_text(
        json.dumps({"material_updates": []}), encoding="utf-8",
    )


def _selected_item():
    return {
        "source_url": WFLX,
        "_pre_generation_material_update_canonical_slug": SLUG,
        "headline": "Martin County approves quiet zones at three crossings",
    }


def test_one_final_context_held_copy_waives_both_coalesced_sources(monkeypatch, tmp_path):
    g = _load_generate()
    _setup(g, tmp_path)
    monkeypatch.setattr(
        g, "_has_self_consistent_pre_generation_material_update_authority",
        lambda item: True,
    )
    final_item = _selected_item()
    assert g._stamp_final_coalesced_material_update_sources(final_item)
    assert final_item["_final_coalesced_material_update_source_urls"] == sorted([WFLX, WPTV])
    assert g._waive_selected_material_update_target(
        final_item, SLUG, "contextless_update_preserve_existing"
    )
    result = g._validate_promoted_material_updates_committed(tmp_path)
    assert result["passed"] is True
    assert result["waived_canonical_count"] == 1
    assert result["missing_target_slugs"] == []
    assert sorted(result["waived"][0]["waived_source_urls"]) == sorted([WFLX, WPTV])


def test_unrecorded_coalescing_still_fails_closed(monkeypatch, tmp_path):
    g = _load_generate()
    _setup(g, tmp_path)
    monkeypatch.setattr(g, "_has_self_consistent_pre_generation_material_update_authority", lambda item: True)
    item = _selected_item()
    # An arbitrary selected-source waiver cannot excuse the other source.
    assert g._waive_selected_material_update_target(item, SLUG, "contextless_update_preserve_existing")
    with pytest.raises(RuntimeError, match="MATERIAL UPDATE PUBLICATION INVARIANT FAILED"):
        g._validate_promoted_material_updates_committed(tmp_path)
    report = json.loads((tmp_path / "data/material-update-publication-invariant.json").read_text())
    assert report["partial_waiver_count"] == 1
    assert WPTV in report["partial_waivers"][0]["remaining_source_urls"]


def test_incorrect_target_or_unapproved_reason_cannot_waive_other_source(monkeypatch, tmp_path):
    g = _load_generate()
    _setup(g, tmp_path)
    monkeypatch.setattr(g, "_has_self_consistent_pre_generation_material_update_authority", lambda item: True)
    item = _selected_item()
    assert g._stamp_final_coalesced_material_update_sources(item)
    g._waive_selected_material_update_target(item, SLUG, "unexplained_missing_commit")
    assert g.CURRENT_RUN_MATERIAL_UPDATE_WAIVERS[SLUG]["source_urls"] == [WFLX]
    with pytest.raises(RuntimeError, match="MATERIAL UPDATE PUBLICATION INVARIANT FAILED"):
        g._validate_promoted_material_updates_committed(tmp_path)
    # A source from an unrelated canonical cannot receive this grouping stamp.
    other = {**item, "source_url": "https://example.com/unrelated"}
    other.pop("_final_coalesced_material_update_source_urls", None)
    assert not g._stamp_final_coalesced_material_update_sources(other)
    assert "_final_coalesced_material_update_source_urls" not in other


def test_unvalidated_final_copy_receives_no_grouping(monkeypatch, tmp_path):
    g = _load_generate()
    _setup(g, tmp_path)
    monkeypatch.setattr(g, "_has_self_consistent_pre_generation_material_update_authority", lambda item: False)
    item = _selected_item()
    assert not g._stamp_final_coalesced_material_update_sources(item)
    assert "_final_coalesced_material_update_source_urls" not in item
