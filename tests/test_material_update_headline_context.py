"""A material update headline must identify the incident behind a suspect."""
from pathlib import Path

from tct_engine.semantic_material_update import (
    _headline_missing_original_event_context,
    _prompt,
    validate_material_update,
)
from scripts.repair_headline_copyedits import repair

ORIGINAL = "Cape Coral man arrested over alleged threats against Martin County student, school"
AMBIGUOUS = "Suspect released on $100,000 bond; Martin County schools to get more deputies"
SPECIFIC = "Martin County school threat suspect released on $100,000 bond; extra deputies planned"


def test_vague_suspect_material_update_is_invalid():
    assert _headline_missing_original_event_context(AMBIGUOUS, ORIGINAL)
    result = validate_material_update(
        {"headline": AMBIGUOUS, "teaser": "", "body": ""},
        canonical={"headline": ORIGINAL}, incoming={"headline": "Deputy presence increased"},
        decision={},
    )
    assert "headline_missing_original_incident_context" in result["validation_errors"]


def test_standalone_specific_update_is_allowed_by_context_check():
    assert not _headline_missing_original_event_context(SPECIFIC, ORIGINAL)
    assert not _headline_missing_original_event_context(
        "Suspect arrested in Stuart shooting; victim identified",
        "Manhunt launched after shooting in Stuart",
    )
    assert not _headline_missing_original_event_context(
        "Cape Coral man accused of threatening school released", ORIGINAL,
    )
    assert not _headline_missing_original_event_context(
        "Suspect released after hearing", "Martin County council approves parking plan",
    )


def test_prompt_says_new_headline_must_stand_alone():
    prompt = _prompt({"headline": ORIGINAL}, {"headline": "More deputies"}, {"novel_facts": []})
    assert "Every refreshed headline must stand alone" in prompt
    assert "Never start with a generic label" in prompt


def test_exact_copyedit_repair_is_idempotent_and_allows_new_developments(tmp_path):
    root = tmp_path
    (root / "data").mkdir()
    (root / "articles").mkdir()
    slug = "test-case"
    old = "Suspect released on bond; deputies assigned"
    new = "School threat suspect released on bond; deputies assigned"
    (root / "data/headline-copyedits.json").write_text(
        '{"corrections":[{"slug":"test-case","from":' +
        __import__("json").dumps(old) + ',"to":' + __import__("json").dumps(new) + '}]}' )
    page = root / "articles/test-case.html"
    page.write_text("<h1>" + old + "</h1>")
    archive = root / "archive.json"
    archive.write_text('[{"headline":' + __import__("json").dumps(old) + '}]')
    assert repair(root)["updated"] == 2
    assert new in page.read_text()
    assert new in archive.read_text()
    assert repair(root)["updated"] == 0
    page.write_text("<h1>Suspect found guilty in school threats case</h1>")
    assert repair(root)["updated"] == 0
    assert "found guilty" in page.read_text()


def test_current_article_and_news_surfaces_are_consistently_corrected():
    root = Path(__file__).resolve().parents[1]
    headline = "Man accused of threatening Martin County school released on $100,000 bond; deputies to increase presence"
    for path in [
        "index.html",
        "data.json",
        "feed.xml",
        "news-sitemap.xml",
        "articles/2026-11-08-cape-coral-man-arrested-over-alleged-threats-against-martin-county-student-schoo.html",
    ]:
        assert headline in (root / path).read_text(encoding="utf-8"), path
