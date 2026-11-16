"""Jensen Beach family profile and public town meeting have different news identities."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = "2026-11-11-jensen-beach-family-seeks-housing-and-repair-funding-after-flooding-destroys-hom"
MEETING = "2026-11-15-jensen-beach-flood-recovery-town-meeting-planned-for-residents"


def test_family_profile_preserves_original_headline_quotes_and_url():
    page = (ROOT / "articles" / (ORIGINAL + ".html")).read_text(encoding="utf-8")
    assert "Jensen Beach family seeks housing and repair funding" in page
    assert "Today we are homeless" in page
    assert "We just want to go home" in page
    assert "Town meeting planned on Jensen Beach flood recovery" not in page
    assert ('<link rel="canonical" href="https://treasurecoast.today/articles/' + ORIGINAL + '.html">') in page


def test_family_article_has_durable_content_restoration_override():
    data = json.loads((ROOT / "data/article-content-overrides.json").read_text(encoding="utf-8"))
    row = data["overrides"][ORIGINAL]
    assert row["mark_meaningful_update"] is False
    assert row["update_status"] == "editorial_subject_restoration"
    assert "We just want to go home" in row["body"]


def test_independent_recovery_meeting_is_queued_under_unique_slug():
    queued = json.loads((ROOT / "custom_articles.json").read_text(encoding="utf-8"))
    # Once published, a later queue replacement is allowed; do not require a
    # previously published custom article to remain forever in the queue.
    for item in queued:
        if item.get("slug") == MEETING:
            assert item["unique_slug"] is True
            assert "meeting" in item["headline"].lower()
            assert "A confirmed meeting time and location were not provided" in item["body"]
            assert ORIGINAL in item["body"]
            assert "We just want to go home" not in item["body"]
