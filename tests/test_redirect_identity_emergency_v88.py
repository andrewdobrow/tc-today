from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

POND_SLUG = "2026-08-08-port-st-lucie-police-investigate-death-of-77-year-old-man-found-in-pond-near-his"
MISSING_FATHER_SLUG = "2026-10-01-family-still-searching-8-months-after-fort-pierce-man-vanished"
MISSING_WOMAN_SLUG = "2026-08-24-st-lucie-county-sheriffs-office-seeks-help-finding-fort-pierce-woman-missing-sin"
THIRD_TOW_ALIAS = "2026-10-02-miami-woman-jailed-after-tow-yard-shooting-triggers-murray-middle-school-lockout"


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
    spec = importlib.util.spec_from_file_location("generate_redirect_identity_v88", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_missing_person_place_name_cannot_become_shared_person_alias():
    from tct_engine.unified_incident_identity import (
        UNIFIED_INCIDENT_EVIDENCE_VERSION,
        build_unified_incident_evidence,
        compare_unified_incident_evidence,
    )

    father = build_unified_incident_evidence(
        title="Eight Months Later, Family Still Searching for Missing Port St. Lucie Father",
        body=(
            "Robert La Polla, 47, disappeared after leaving a Fort Pierce hospital. "
            "His family continues searching for the missing father."
        ),
    )
    woman = build_unified_incident_evidence(
        title="St. Lucie County Sheriff's Office seeks help finding Fort Pierce woman missing since August 14",
        body="Deputies are asking for help finding Racqueal Annalessa Martin, a missing woman from Fort Pierce.",
    )

    assert UNIFIED_INCIDENT_EVIDENCE_VERSION >= 6
    assert "fort pierce" not in father.people
    assert "fort pierce" not in woman.people
    score, trace = compare_unified_incident_evidence(father, woman)
    assert score == 0.0
    assert not any("Shared person aliases: fort pierce" in line for line in trace)


def test_missing_person_redirect_audit_rejects_conflicting_subjects():
    g = _load_generate()
    assert g._missing_person_redirect_subject_conflict(
        "Eight Months Later, Family Still Searching for Missing Port St. Lucie Father",
        "St. Lucie County Sheriff's Office seeks help finding Fort Pierce woman missing since August 14",
    ) == "gender_conflict"


def test_current_run_missing_person_subject_conflict_fails_before_redirect_write(tmp_path: Path):
    g = _load_generate()
    data = tmp_path / "data"
    articles = tmp_path / "articles"
    data.mkdir()
    articles.mkdir()
    (data / "canonical-redirects.json").write_text('{"redirects": []}', encoding="utf-8")

    source = "2026-10-04-family-searches-for-missing-port-st-lucie-father"
    target = "2026-10-03-sheriff-seeks-help-finding-fort-pierce-woman"
    (articles / f"{target}.html").write_text("<html><body>target</body></html>", encoding="utf-8")
    redirect = {
        "source_slug": source,
        "source_headline": "Family searches for missing Port St. Lucie father",
        "target_slug": target,
        "target_headline": "Sheriff seeks help finding Fort Pierce woman reported missing",
    }
    with pytest.raises(RuntimeError, match="missing-person redirect has conflicting subject identity"):
        g.enforce_canonical_redirects(
            [{"slug": target, "headline": redirect["target_headline"]}],
            articles,
            tmp_path,
            [redirect],
        )


def test_third_tow_yard_alias_is_permanently_target_locked():
    g = _load_generate()
    assert THIRD_TOW_ALIAS in g.TOW_YARD_REDIRECT_SOURCE_SLUGS
    assert g._tow_yard_incident_redirect_source(
        THIRD_TOW_ALIAS,
        "Second Arrest Made in Martin County Tow Yard Shooting Case",
    ) is True


def test_tow_yard_audit_discovers_unlisted_same_incident_alias(tmp_path: Path):
    g = _load_generate()
    articles = tmp_path / "articles"
    data = tmp_path / "data"
    articles.mkdir()
    data.mkdir()
    canonical = g.TOW_YARD_CANONICAL_SLUG
    wrong = g.ROAD_RAGE_CANONICAL_SLUG
    unseen = "2026-10-02-stuart-garrys-towing-shooting-update"
    (articles / f"{canonical}.html").write_text("<html><body>canonical</body></html>", encoding="utf-8")
    (articles / f"{wrong}.html").write_text("<html><body>wrong</body></html>", encoding="utf-8")
    records = [{
        "source_slug": unseen,
        "source_headline": "Stuart Garry's Towing shooting update after chase",
        "target_slug": wrong,
        "target_headline": "Fort Myers man arrested after road rage PIT maneuver",
    }]
    with pytest.raises(RuntimeError, match="Garry's Towing permalink ownership"):
        g._write_canonical_redirect_safety_audit(
            records,
            [{"slug": canonical}, {"slug": wrong}],
            articles,
            tmp_path,
            current_by_source={},
        )


def test_emergency_standalones_include_confirmed_pond_and_missing_father_urls():
    g = _load_generate()
    assert POND_SLUG in g.EMERGENCY_RESTORABLE_STANDALONE_SLUGS
    assert MISSING_FATHER_SLUG in g.EMERGENCY_RESTORABLE_STANDALONE_SLUGS
    assert POND_SLUG in g.PROTECTED_STANDALONE_SLUGS
    assert MISSING_FATHER_SLUG in g.PROTECTED_STANDALONE_SLUGS


def test_emergency_standalone_self_heal_restores_exact_committed_page_and_archive(tmp_path: Path, monkeypatch):
    g = _load_generate()
    slug = "2026-10-01-independent-missing-father-story"
    wrong = "2026-08-24-unrelated-missing-woman-story"
    monkeypatch.setattr(g, "EMERGENCY_RESTORABLE_STANDALONE_SLUGS", frozenset({slug}))

    (tmp_path / "articles").mkdir()
    (tmp_path / "data").mkdir()
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "tct@test.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "TCT Test"], cwd=tmp_path, check=True)

    historical_html = (
        f'<html><head><link rel="canonical" href="https://treasurecoast.today/articles/{slug}.html"></head>'
        '<body><h1>Family still searching for missing father</h1>'
        '<div class="article-body"><p>Original substantive article.</p></div></body></html>'
    )
    historical_row = {
        "slug": slug,
        "headline": "Family still searching for missing father",
        "date": "2026-10-01",
        "first_published": "Thu, 01 Oct 2026 21:30:00 -0400",
        "editorial_story_id": "story_missing_father",
    }
    target_row = {
        "slug": wrong,
        "headline": "Sheriff seeks help finding missing woman",
        "date": "2026-08-24",
        "first_published": "Mon, 24 Aug 2026 10:00:00 -0400",
    }
    (tmp_path / "articles" / f"{slug}.html").write_text(historical_html, encoding="utf-8")
    (tmp_path / "articles" / f"{wrong}.html").write_text("<html><body>target</body></html>", encoding="utf-8")
    (tmp_path / "archive.json").write_text(json.dumps([historical_row, target_row]), encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "good standalone"], cwd=tmp_path, check=True)

    (tmp_path / "articles" / f"{slug}.html").write_text(
        g._render_canonical_redirect_page(slug, wrong, target_row["headline"]), encoding="utf-8"
    )
    (tmp_path / "archive.json").write_text(json.dumps([target_row]), encoding="utf-8")
    (tmp_path / "data" / "canonical-redirects.json").write_text(json.dumps({
        "schema_version": 2,
        "redirects": [{"source_slug": slug, "target_slug": wrong, "target_headline": target_row["headline"]}],
    }), encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "bad redirect"], cwd=tmp_path, check=True)

    result = g._repair_emergency_standalone_permalink_regressions(tmp_path)
    assert result["repaired"] == 1
    restored_html = (tmp_path / "articles" / f"{slug}.html").read_text(encoding="utf-8")
    assert "Original substantive article." in restored_html
    assert "window.location.replace" not in restored_html
    archive = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    restored = next(row for row in archive if row.get("slug") == slug)
    assert restored["first_published"] == "Thu, 01 Oct 2026 21:30:00 -0400"
    assert restored["editorial_story_id"] == "story_missing_father"
    manifest = json.loads((tmp_path / "data" / "canonical-redirects.json").read_text(encoding="utf-8"))
    assert slug not in {row.get("source_slug") for row in manifest["redirects"]}
    assert f"/articles/{slug}.html" not in (tmp_path / "_redirects").read_text(encoding="utf-8")


def test_emergency_standalone_self_heal_fails_closed_without_history(tmp_path: Path, monkeypatch):
    g = _load_generate()
    slug = "2026-10-01-independent-story"
    wrong = "2026-08-24-unrelated-story"
    monkeypatch.setattr(g, "EMERGENCY_RESTORABLE_STANDALONE_SLUGS", frozenset({slug}))
    (tmp_path / "articles").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "archive.json").write_text("[]", encoding="utf-8")
    (tmp_path / "articles" / f"{slug}.html").write_text(
        g._render_canonical_redirect_page(slug, wrong, "Wrong"), encoding="utf-8"
    )
    (tmp_path / "data" / "canonical-redirects.json").write_text(
        json.dumps({"redirects": [{"source_slug": slug, "target_slug": wrong}]}),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="no substantive committed"):
        g._repair_emergency_standalone_permalink_regressions(tmp_path)
