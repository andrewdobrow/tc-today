from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NEW_ALIAS = "2026-10-03-two-miami-women-charged-after-gunfire-chase-at-martin-county-tow-yard"
FIRST_BAD_ALIAS = "2026-10-02-shooting-at-stuart-tow-yard-prompts-murray-middle-lockout-chase-with-pit-maneuve"


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
    spec = importlib.util.spec_from_file_location("generate_tow_yard_regression", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _road_rage_item():
    return {
        "slug": "2026-08-04-fort-myers-man-arrested-after-road-rage-pit-maneuver-crashes-familys-suv-into-fe",
        "headline": "Fort Myers man arrested after road rage PIT maneuver crashes family's SUV into fence on I-95 in Martin County",
        "teaser": (
            "A Fort Myers man is charged with aggravated battery with a deadly weapon and child abuse "
            "after deputies say he performed a PIT maneuver on a North Carolina family's vehicle during "
            "a road rage incident near Stuart."
        ),
        "body": (
            "Martin County deputies arrested a Fort Myers man after a road rage crash. Deputies said "
            "the driver used a PIT maneuver against a family's vehicle on the road. He faces charges."
        ),
        "date": "2026-08-04",
        "source_url": "https://www.wpbf.com/article/florida-pit-maneuver-deputy-car-baby-barbed-wire/73334291",
        "editorial_story_id": "story_002073",
    }


def _tow_yard_item(slug=NEW_ALIAS):
    return {
        "slug": slug,
        "headline": "Two Miami women charged after gunfire, chase at Martin County tow yard",
        "teaser": (
            "Jade Rondon and Valerie Valdes face charges after gunfire at Garry's Towing on Cove Road "
            "near Stuart led to a pursuit and crashes."
        ),
        "body": (
            "The Martin County Sheriff's Office said deputies pursued the vehicle after the shooting at "
            "Garry's Towing. Deputies used a PIT maneuver before a crash. Rondon and Valdes face charges. "
            "Investigators are reviewing video and search warrants involving phones and vehicles."
        ),
        "date": "2026-10-03",
        "source_url": "https://www.wpbf.com/article/florida-2-women-held-jail-shooting-tow-yard-chase-crash-stuart/74004891",
    }


def test_pit_tactic_does_not_classify_tow_yard_shooting_as_road_rage():
    from tct_engine.unified_incident_identity import build_unified_incident_evidence

    road = build_unified_incident_evidence(
        title=_road_rage_item()["headline"], body=_road_rage_item()["body"], published_at="2026-08-04"
    )
    tow = build_unified_incident_evidence(
        title=_tow_yard_item()["headline"], body=_tow_yard_item()["body"], published_at="2026-10-03"
    )
    historical_alias = build_unified_incident_evidence(
        title="Florida man used police maneuver to run North Carolina family off road near Stuart",
        body="Deputies investigated the road rage incident.",
        published_at="2026-08-05",
    )

    assert road.family == "road_rage"
    assert historical_alias.family == "road_rage"
    assert tow.family == "shooting"


def test_legacy_six_shared_words_cannot_merge_tow_yard_with_road_rage():
    g = _load_generate()
    # Regression: the former fallback treated the shared words deputies/crash/
    # maneuver/road/charges/vehicle as sufficient destructive corroboration.
    assert g._same_event_items(_tow_yard_item(), _road_rage_item()) is False


def test_oct2_and_oct3_tow_yard_frames_share_deterministic_event_key():
    g = _load_generate()
    old = _tow_yard_item(g.TOW_YARD_CANONICAL_SLUG)
    old["headline"] = "Two Miami women charged after tow yard shooting near Stuart sparks school lockout"
    old["body"] += " Murray Middle School was placed on lockout during the response."
    old["date"] = "2026-10-02"
    assert g._known_event_key(g._story_text(old)) == "2026-10-martin-garrys-towing-shooting-chase"
    assert g._known_event_key(g._story_text(_tow_yard_item())) == "2026-10-martin-garrys-towing-shooting-chase"
    assert g._same_event_items(old, _tow_yard_item()) is True


def test_redirect_enforcement_repairs_stale_tow_yard_targets(tmp_path):
    g = _load_generate()
    data = tmp_path / "data"
    articles = tmp_path / "articles"
    data.mkdir()
    articles.mkdir()
    old = g.TOW_YARD_CANONICAL_SLUG
    alias = NEW_ALIAS
    assert FIRST_BAD_ALIAS in g.TOW_YARD_REDIRECT_SOURCE_SLUGS
    road = g.ROAD_RAGE_CANONICAL_SLUG
    (data / "canonical-redirects.json").write_text(json.dumps({"redirects": [
        {"source_slug": old, "target_slug": road, "source_headline": "Tow yard"},
        {"source_slug": alias, "target_slug": road, "source_headline": "Tow yard update"},
    ]}), encoding="utf-8")
    archive = [{"slug": old, "headline": "Tow yard canonical"}, {"slug": road, "headline": "Road rage"}]
    cleaned, _ = g.enforce_canonical_redirects(archive, articles, tmp_path, [])
    payload = json.loads((data / "canonical-redirects.json").read_text(encoding="utf-8"))
    by_source = {r["source_slug"]: r for r in payload["redirects"]}

    assert old not in by_source
    assert by_source[alias]["target_slug"] == old
    assert by_source[FIRST_BAD_ALIAS]["target_slug"] == old
    assert any(row.get("slug") == old for row in cleaned)
    rules = (tmp_path / "_redirects").read_text(encoding="utf-8")
    assert f"/articles/{alias}.html /articles/{old}.html 301!" in rules
    assert f"/articles/{old}.html /articles/{road}.html" not in rules
    audit = json.loads((data / "canonical-redirect-safety-audit.json").read_text(encoding="utf-8"))
    assert audit["tow_yard_integrity_passed"] is True


def test_current_run_cannot_destroy_tow_yard_canonical_or_retarget_alias(tmp_path):
    g = _load_generate()
    (tmp_path / "data").mkdir()
    (tmp_path / "articles").mkdir()
    (tmp_path / "data" / "canonical-redirects.json").write_text('{"redirects": []}', encoding="utf-8")
    old = g.TOW_YARD_CANONICAL_SLUG
    alias = NEW_ALIAS
    assert FIRST_BAD_ALIAS in g.TOW_YARD_REDIRECT_SOURCE_SLUGS
    road = g.ROAD_RAGE_CANONICAL_SLUG

    with pytest.raises(RuntimeError, match="established Oct. 2 Garry's Towing permalink"):
        g.enforce_canonical_redirects([], tmp_path / "articles", tmp_path, [
            {"source_slug": old, "target_slug": road}
        ])
    with pytest.raises(RuntimeError, match="Garry's Towing alias"):
        g.enforce_canonical_redirects([], tmp_path / "articles", tmp_path, [
            {"source_slug": alias, "target_slug": road}
        ])


def test_self_heal_recovers_old_permalink_and_rebinds_new_alias_from_git(tmp_path):
    g = _load_generate()
    old = g.TOW_YARD_CANONICAL_SLUG
    alias = NEW_ALIAS
    assert FIRST_BAD_ALIAS in g.TOW_YARD_REDIRECT_SOURCE_SLUGS
    road = g.ROAD_RAGE_CANONICAL_SLUG
    (tmp_path / "articles").mkdir()
    (tmp_path / "data").mkdir()

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "tct@test.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "TCT Test"], cwd=tmp_path, check=True)

    good_html = (
        f'<html><head><link rel="canonical" href="https://treasurecoast.today/articles/{old}.html"></head>'
        '<body><h1>Original tow yard report</h1><div class="article-body"><p>Substantive old article.</p></div></body></html>'
    )
    historical_row = {
        "slug": old,
        "headline": "Two Miami women charged after tow yard shooting near Stuart sparks school lockout",
        "date": "2026-10-02",
        "first_published": "Fri, 02 Oct 2026 21:48:00 -0400",
        "editorial_story_id": "story_tow_yard_good",
    }
    road_row = {"slug": road, "headline": "Road rage", "date": "2026-08-04", "editorial_story_id": "story_road"}
    (tmp_path / "articles" / f"{old}.html").write_text(good_html, encoding="utf-8")
    (tmp_path / "archive.json").write_text(json.dumps([historical_row, road_row]), encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "good tow yard canonical"], cwd=tmp_path, check=True)

    new_html = (
        f'<html><head><link rel="canonical" href="https://treasurecoast.today/articles/{alias}.html"></head>'
        '<body><h1>Two Miami women charged after gunfire chase</h1>'
        '<div class="article-body"><p>Latest substantive follow-up copy.</p></div></body></html>'
    )
    (tmp_path / "articles" / f"{old}.html").write_text(
        g._render_canonical_redirect_page(old, road, "Wrong road rage target"), encoding="utf-8"
    )
    (tmp_path / "articles" / f"{alias}.html").write_text(new_html, encoding="utf-8")
    alias_row = {
        "slug": alias,
        "headline": "Two Miami women charged after gunfire, chase at Martin County tow yard",
        "date": "2026-10-03",
        "editorial_story_id": "story_road",
    }
    (tmp_path / "archive.json").write_text(json.dumps([road_row, alias_row]), encoding="utf-8")
    (tmp_path / "data" / "canonical-redirects.json").write_text(json.dumps({"redirects": [
        {"source_slug": old, "target_slug": road},
        {"source_slug": FIRST_BAD_ALIAS, "target_slug": road},
        {"source_slug": alias, "target_slug": road},
    ]}), encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "corrupted redirects"], cwd=tmp_path, check=True)

    result = g._repair_tow_yard_permalink_regression(tmp_path)
    assert result["repaired"] == 1
    repaired_html = (tmp_path / "articles" / f"{old}.html").read_text(encoding="utf-8")
    assert "Latest substantive follow-up copy." in repaired_html
    assert f"/articles/{old}.html" in repaired_html
    assert f"/articles/{alias}.html" not in repaired_html
    repaired_archive = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    old_rows = [row for row in repaired_archive if row.get("slug") == old]
    assert len(old_rows) == 1
    assert old_rows[0]["date"] == "2026-10-02"
    assert old_rows[0]["first_published"] == "Fri, 02 Oct 2026 21:48:00 -0400"
    assert old_rows[0]["editorial_story_id"] == "story_tow_yard_good"
    assert not any(row.get("slug") == alias for row in repaired_archive)
    manifest = json.loads((tmp_path / "data" / "canonical-redirects.json").read_text(encoding="utf-8"))
    by_source = {row["source_slug"]: row for row in manifest["redirects"]}
    assert old not in by_source
    assert by_source[alias]["target_slug"] == old
    assert by_source[FIRST_BAD_ALIAS]["target_slug"] == old



def test_self_heal_is_idempotent_after_canonical_and_all_aliases_are_healthy(tmp_path):
    g = _load_generate()
    old = g.TOW_YARD_CANONICAL_SLUG
    (tmp_path / "articles").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "articles" / f"{old}.html").write_text(
        '<html><body><h1>Healthy tow yard article</h1><div class="article-body"><p>Copy.</p></div></body></html>',
        encoding="utf-8",
    )
    row = {
        "slug": old,
        "headline": "More Charges Likely After Stuart Tow Yard Shooting, Chase, Crash",
        "date": "2026-10-02",
        "first_published": "Fri, 02 Oct 2026 21:48:00 -0400",
    }
    (tmp_path / "archive.json").write_text(json.dumps([row]), encoding="utf-8")
    (tmp_path / "data" / "canonical-redirects.json").write_text(json.dumps({
        "redirects": [
            {"source_slug": slug, "target_slug": old}
            for slug in sorted(g.TOW_YARD_REDIRECT_SOURCE_SLUGS)
        ]
    }), encoding="utf-8")

    result = g._repair_tow_yard_permalink_regression(tmp_path)
    assert result == {
        "status": "already_healthy",
        "repaired": 0,
        "reason": "canonical_and_aliases_verified",
    }


def test_self_heal_refuses_to_invent_missing_historical_publication_time(tmp_path):
    g = _load_generate()
    old = g.TOW_YARD_CANONICAL_SLUG
    alias = NEW_ALIAS
    road = g.ROAD_RAGE_CANONICAL_SLUG
    (tmp_path / "articles").mkdir()
    (tmp_path / "data").mkdir()
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "tct@test.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "TCT Test"], cwd=tmp_path, check=True)

    # Historical canonical exists, but its publication time is absent. Recovery must
    # stop rather than fabricate one.
    (tmp_path / "articles" / f"{old}.html").write_text(
        '<html><body><h1>Old tow yard report</h1><div class="article-body"><p>Copy.</p></div></body></html>',
        encoding="utf-8",
    )
    (tmp_path / "archive.json").write_text(json.dumps([{
        "slug": old,
        "headline": "Old tow yard report",
        "date": "2026-10-02",
    }]), encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "historical canonical without timestamp"], cwd=tmp_path, check=True)

    (tmp_path / "articles" / f"{old}.html").write_text(
        g._render_canonical_redirect_page(old, road, "Wrong road rage target"), encoding="utf-8"
    )
    (tmp_path / "articles" / f"{alias}.html").write_text(
        '<html><body><h1>Latest follow-up</h1><div class="article-body"><p>Latest.</p></div></body></html>',
        encoding="utf-8",
    )
    (tmp_path / "archive.json").write_text(json.dumps([{
        "slug": alias,
        "headline": "Latest follow-up",
        "date": "2026-10-03",
    }]), encoding="utf-8")
    (tmp_path / "data" / "canonical-redirects.json").write_text(json.dumps({
        "redirects": [{"source_slug": old, "target_slug": road}]
    }), encoding="utf-8")

    with pytest.raises(RuntimeError, match="timestamp could not be recovered"):
        g._repair_tow_yard_permalink_regression(tmp_path)
