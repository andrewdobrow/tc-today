"""Regression: St. Lucie's Wednesday closure and flood-review response are not duplicate news."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.repair_headline_copyedits import repair

ROOT = Path(__file__).resolve().parents[1]
OLD = "St. Lucie County schools close Wednesday as superintendent pledges flood review"
NEW = "St. Lucie schools superintendent pledges review after bus flooding incident"
SLUG = "2026-11-18-st-lucie-county-schools-close-wednesday-as-superintendent-pledges-flood-review"
CLOSURE_SLUG = "2026-11-17-st-lucie-county-schools-releasing-students-two-hours-early-ahead-of-flood-watch"
OLD_LEAD = "St. Lucie County Schools canceled Wednesday classes with heavy rain in the forecast"


def test_nov18_article_leads_with_review_not_repeated_closure():
    page = (ROOT / "articles" / f"{SLUG}.html").read_text(encoding="utf-8")
    closure = (ROOT / "articles" / f"{CLOSURE_SLUG}.html").read_text(encoding="utf-8")
    assert f"<h1 class=\"article-headline\">{NEW}</h1>" in page
    assert NEW in page
    assert OLD not in page
    assert OLD_LEAD not in page
    assert "St. Lucie school superintendent Jon Prince pledges to review district decisions" in page
    assert 'class="article-body"><p>St. Lucie Public Schools Superintendent' in page
    assert "review its policies and decisions" in page
    assert "St. Lucie County schools to close Wednesday after early dismissal" in closure
    assert f"<title>{NEW} | Treasure Coast Today</title>" in page


def test_nov18_persistent_framing_correction_is_reapplied_after_generation(tmp_path):
    original = (ROOT / "data" / "headline-copyedits.json").read_text(encoding="utf-8")
    payload = json.loads(original)
    corrections = [row for row in payload["corrections"] if row["slug"] == SLUG]
    assert len(corrections) >= 4
    assert any(row["from"] == OLD and row["to"] == NEW for row in corrections)
    (tmp_path / "data").mkdir()
    (tmp_path / "articles").mkdir()
    (tmp_path / "data" / "headline-copyedits.json").write_text(original, encoding="utf-8")
    outdated = (
        f"<h1>{OLD}</h1>"
        "<div class='article-body'><p>"
        "St. Lucie County Schools canceled Wednesday classes with heavy rain in the forecast, "
        "and Superintendent Dr. Jon Prince promised to review the district’s decisions during the Nov. 2 flooding. "
        "The review follows criticism over a video showing a boy wading through chest-high water after getting off "
        "a school bus in Port St. Lucie."
        "</p></div>"
    )
    target = tmp_path / "articles" / f"{SLUG}.html"
    target.write_text(outdated, encoding="utf-8")
    first = repair(tmp_path)
    assert first["updated"] == 1
    after = target.read_text(encoding="utf-8")
    assert NEW in after and OLD not in after
    assert "review its policies and decisions" in after
    assert repair(tmp_path)["updated"] == 0


def test_home_hero_and_data_api_use_review_framing():
    for path in ("index.html", "data.json"):
        content = (ROOT / path).read_text(encoding="utf-8")
        assert OLD not in content
        # Current homepage/API selections are temporary; older stories rotate out.
        # When the corrected story is featured, ensure its updated headline is used.
        if SLUG in content:
            assert NEW in content
