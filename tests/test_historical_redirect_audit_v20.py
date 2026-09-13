from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


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
    path = ROOT / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_redirect_audit_v20", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _manifest():
    return json.loads((ROOT / "data" / "canonical-redirects.json").read_text(encoding="utf-8"))


def test_redirect_audit_static_manifest_has_expected_repair_shape():
    g = _load_generate()
    payload = _manifest()
    redirects = payload["redirects"]
    by_source = {row["source_slug"]: row for row in redirects}

    # v1.13.9.20 established a post-audit baseline of 204 cumulative redirects:
    # sixteen independently valid permalinks were restored, while thirteen genuine
    # aliases remained as repaired 301s. The global redirect ledger is intentionally
    # cumulative, so later production runs may add newly verified redirects. Do not
    # freeze the total count at the release-time baseline; validate ledger integrity
    # and the audited repair invariants instead.
    assert payload["redirect_count"] == len(redirects)
    assert payload["redirect_count"] >= 204
    assert len(payload["verification"]) == len(redirects)
    assert payload["all_redirect_pages_verified"] is True
    assert len({row["source_slug"] for row in redirects}) == len(redirects)

    standalone = set(g.HISTORICAL_REDIRECT_STANDALONE_SLUGS)
    assert not (standalone & set(by_source))
    for source, target in g.HISTORICAL_REDIRECT_ALIAS_TARGETS.items():
        assert by_source[source]["target_slug"] == target
        assert by_source[source]["story_stage"] == "historical-redirect-audit-repair"


def test_two_suspicious_but_verified_redirects_are_intentionally_retained():
    by_source = {row["source_slug"]: row for row in _manifest()["redirects"]}
    assert by_source[
        "2026-08-09-st-lucie-county-sheriffs-office-warns-against-using-social-media-to-report-crime"
    ]["target_slug"] == (
        "2026-08-08-port-st-lucie-man-arrested-after-video-shows-him-kicking-small-dog"
    )
    assert by_source[
        "2026-09-01-body-found-in-martin-county-mangroves-believed-to-be-missing-port-st-lucie-man"
    ]["target_slug"] == (
        "2026-08-29-martin-county-sheriffs-office-searches-for-missing-oklahoma-visitor-last-seen-at-chastain-beach"
    )


def test_restored_standalones_are_substantive_self_canonical_articles():
    g = _load_generate()
    for slug in sorted(set(g.HISTORICAL_REDIRECT_STANDALONE_SLUGS)):
        path = ROOT / "articles" / f"{slug}.html"
        assert path.exists(), slug
        page = path.read_text(encoding="utf-8")
        assert 'noindex,follow' not in page, slug
        assert 'window.location.replace' not in page, slug
        assert f'https://treasurecoast.today/articles/{slug}.html' in page, slug
        assert '<h1' in page and 'article-body' in page, slug


def test_shared_persistent_story_id_alone_cannot_destroy_permalink():
    g = _load_generate()
    left = {
        "slug": "2026-08-09-horse-story",
        "headline": "Horse stolen from Port St. Lucie pasture",
        "source_url": "https://example.com/horse",
        "editorial_story_id": "story_contaminated",
        "category_key": "st_lucie",
        "date": "2026-08-09",
    }
    right = {
        "slug": "2026-08-08-pond-death",
        "headline": "Man found dead in pond near Port St. Lucie home",
        "source_url": "https://example.com/pond",
        "editorial_story_id": "story_contaminated",
        "category_key": "crime",
        "date": "2026-08-08",
    }
    authorized, evidence = g._published_pair_can_share_permalink(left, right)
    assert authorized is False
    assert evidence.get("write_authorized") is not True


def test_stale_stored_incident_anchor_alone_cannot_destroy_permalink():
    g = _load_generate()
    stale_anchor = "named-person-death:geoffrey-lang"
    left = {
        "slug": "2026-08-09-horse-story",
        "headline": "Horse stolen from Port St. Lucie pasture",
        "teaser": "Deputies are searching for a stolen stallion.",
        "incident_anchor_key": stale_anchor,
    }
    right = {
        "slug": "2026-08-08-pond-death",
        "headline": "Man found dead in pond near Port St. Lucie home",
        "teaser": "Police are investigating the death of a 77-year-old man.",
        "incident_anchor_key": stale_anchor,
    }
    authorized, evidence = g._published_pair_can_share_permalink(left, right)
    assert authorized is False
    assert evidence.get("write_authorized") is not True


def test_recomputed_write_authoritative_incident_anchor_can_authorize_true_pair():
    g = _load_generate()
    left = {
        "slug": "lang-one",
        "headline": "Indian River County Fire Rescue mourns death of firefighter Geoffrey Lang who dedicated his life to service",
        "teaser": "Fire Rescue announced the death of firefighter Geoffrey Lang.",
    }
    right = {
        "slug": "lang-two",
        "headline": "Sebastian Police Department mourns death of Indian River County firefighter",
        "teaser": "Sebastian police mourned the death of firefighter Geoffrey Lang.",
    }
    authorized, evidence = g._published_pair_can_share_permalink(left, right)
    assert authorized is True
    assert evidence["proof_type"] == "direct_recomputed_incident_identity"
    assert evidence["incident_anchor_key"] == "named-person-death:geoffrey-lang"


def test_direct_exact_source_identity_still_authorizes_true_duplicate_alias():
    g = _load_generate()
    source = "https://www.wpbf.com/article/same-story/12345678"
    left = {"slug":"old-slug", "headline":"Story headline one", "source_url":source}
    right = {"slug":"new-slug", "headline":"Story headline two", "source_url":source}
    authorized, evidence = g._published_pair_can_share_permalink(left, right)
    assert authorized is True
    assert evidence["proof_type"] == "direct_deterministic_identity"


def test_current_run_cannot_redirect_audited_standalone(tmp_path):
    g = _load_generate()
    (tmp_path / "data").mkdir()
    (tmp_path / "articles").mkdir()
    (tmp_path / "data" / "canonical-redirects.json").write_text(
        json.dumps({"redirects": []}), encoding="utf-8"
    )
    source = "2026-08-06-flood-advisory-issued-for-western-martin-county-through-730-pm-thursday"
    with pytest.raises(RuntimeError, match="audited standalone permalink"):
        g.enforce_canonical_redirects(
            [{"slug": source, "headline": "Flood Advisory"}],
            tmp_path / "articles",
            tmp_path,
            [{"source_slug": source, "target_slug": "unrelated-story", "target_headline": "Wrong"}],
        )


def test_current_run_cannot_retarget_audited_alias_to_another_story(tmp_path):
    g = _load_generate()
    (tmp_path / "data").mkdir()
    (tmp_path / "articles").mkdir()
    (tmp_path / "data" / "canonical-redirects.json").write_text(
        json.dumps({"redirects": []}), encoding="utf-8"
    )
    source = next(iter(g.HISTORICAL_REDIRECT_ALIAS_TARGETS))
    with pytest.raises(RuntimeError, match="audited alias permalink"):
        g.enforce_canonical_redirects(
            [], tmp_path / "articles", tmp_path,
            [{"source_slug": source, "target_slug": "unrelated-story", "target_headline": "Wrong"}],
        )


def test_redirect_audit_report_documents_all_29_corrections():
    report = (ROOT / "REDIRECT_AUDIT_2026-09-13.md").read_text(encoding="utf-8")
    assert "**29 redirects were confirmed erroneous.**" in report
    assert "Sixteen had sacrificed independent article permalinks" in report
    assert "Thirteen were genuine duplicate aliases" in report
    assert "**2 suspicious-looking redirects were reviewed and intentionally retained**" in report
