"""Regression contract: newsroom provenance cleanup must not orphan reporter names."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import prepare_membership_paywall as prepare
from tct_engine.article_prose_policy import _split_sentences, sanitize_article_text
from tct_engine.membership_paywall import FULL_BODY_MARKER


SLUG = "2026-10-09-port-st-lucie-police-seek-help-identifying-critically-injured-man-found-on-roadw"
SOURCE_SENTENCE = (
    "The October 23 police briefing and arrest details were reported by Treasure Coast "
    "Newspapers journalists Laurie K. Blandford and Olivia Franklin."
)
SECOND_SENTENCE = (
    "Earlier reports from WPTV and WFLX documented the October 9 collision and "
    "the October 22 search for two vehicles."
)
FINAL_SENTENCE = "Information about a possible second vehicle remains part of the investigation."
ORPHAN = "Blandford and Olivia Franklin. " + FINAL_SENTENCE


def test_initial_inside_reporter_name_does_not_create_false_sentence():
    sentences = _split_sentences(SOURCE_SENTENCE + " " + SECOND_SENTENCE + " " + FINAL_SENTENCE)
    assert sentences == [SOURCE_SENTENCE, SECOND_SENTENCE, FINAL_SENTENCE]
    cleaned = sanitize_article_text(" ".join(sentences))
    assert cleaned == FINAL_SENTENCE
    assert "Blandford and Olivia Franklin." not in cleaned
    # Multiple initials must also remain inside a personal name.
    assert _split_sentences("A source identified J. R. Smith. The inquiry remains open.") == [
        "A source identified J. R. Smith.",
        "The inquiry remains open.",
    ]


def _override() -> dict:
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "data" / "article-content-overrides.json").read_text(encoding="utf-8"))
    return payload["overrides"][SLUG]


def test_oct23_editorial_override_has_substantive_ending_and_migration_replacements():
    override = _override()
    assert override["body"].rstrip().endswith(
        "Police have not established in the public statements reviewed that the second "
        "vehicle also struck the pedestrian."
    )
    assert "Blandford and Olivia Franklin" not in override["body"]
    replacement_texts = {row["from"] for row in override["body_replacements"]}
    assert "<p>" + SOURCE_SENTENCE + " " + SECOND_SENTENCE + " " + FINAL_SENTENCE + "</p>" in replacement_texts
    assert "<p>" + ORPHAN + "</p>" in replacement_texts


@pytest.mark.parametrize("old_tail", [
    SOURCE_SENTENCE + " " + SECOND_SENTENCE + " " + FINAL_SENTENCE,
    ORPHAN,
])
def test_protected_copy_rehydration_removes_both_corrupt_tail_forms(tmp_path, monkeypatch, old_tail):
    repo = tmp_path / "repo"
    articles = repo / "articles"
    articles.mkdir(parents=True)
    (repo / "data").mkdir()
    override = _override()
    (repo / "data" / "article-content-overrides.json").write_text(
        json.dumps({"overrides": {SLUG: override}}), encoding="utf-8"
    )
    (repo / "archive.json").write_text(
        json.dumps([{"slug": SLUG, "source_url": "https://www.wpbf.com/article/crash/123", "source_headline": "PSL crash - WPBF"}]),
        encoding="utf-8",
    )
    old_page = (
        '<html><head><title>Example</title></head><body>'
        '<div class="article-body tct-member-preview"><p>Old preview.</p></div>'
        '<div class="tct-member-only"><section data-tct-paywall></section>'
        '<div id="tct-protected-content"></div></div>'
        '<aside class="newsletter-inline-slot newsletter-inline-slot--article" '
        'aria-label="Subscribe to the Treasure Coast Morning Brief"></aside>'
        '<div class="article-share"></div></body></html>'
    )
    (articles / (SLUG + ".html")).write_text(old_page, encoding="utf-8")
    first = (
        "Police said a 63-year-old man was critically injured near Northwest University Boulevard "
        "and Northwest California Boulevard. Detectives reviewed evidence and arrested a driver. "
        "The investigation continues, and the victim remained hospitalized at the time of the briefing."
    )
    second = (
        "Detectives are also seeking the driver of a southbound vehicle that may have been near "
        "the October 9 crash. Police have not established that this second vehicle also hit the "
        "pedestrian. Investigators asked anyone with relevant information to contact police."
    )
    full_body = f"<p>{first}</p><p>{second}</p><p>{old_tail}</p>"
    snapshot = tmp_path / "protected-snapshot.json"
    snapshot.write_text(
        json.dumps({"articles": [{"slug": SLUG, "protected_body": FULL_BODY_MARKER + full_body}]}),
        encoding="utf-8",
    )
    export = tmp_path / "protected-export.json"
    monkeypatch.setattr(prepare, "ROOT", repo)
    monkeypatch.setattr(prepare, "ARTICLES", articles)
    monkeypatch.setenv("TCT_MEMBERSHIP_UI_ENABLED", "true")
    monkeypatch.setenv("TCT_PROTECTED_SNAPSHOT_PATH", str(snapshot))
    monkeypatch.setenv("TCT_PROTECTED_EXPORT_PATH", str(export))
    prepare.main()
    output = json.loads(export.read_text(encoding="utf-8"))["articles"][0]["protected_body"]
    assert "Blandford and Olivia Franklin" not in output
    assert "Information about a possible second vehicle remains part of the investigation." not in output
    assert "Detectives are also seeking the driver" in output
    assert output.count("<p>") == 2
    page = (articles / (SLUG + ".html")).read_text(encoding="utf-8")
    assert '<aside class="newsletter-inline-slot newsletter-inline-slot--article"' in page
    assert 'aria-label="Subscribe to the Treasure Coast Morning Brief"' in page
    assert 'slot--article" aria-label' not in page.replace('newsletter-inline-slot--article" aria-label', '')
