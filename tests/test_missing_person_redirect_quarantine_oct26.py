"""Regression: reject contradictory missing-person identities before redirect writes."""
import json
from pathlib import Path

from tests.test_redirect_identity_emergency_v88 import _load_generate


def test_cross_person_duplicate_is_quarantined_before_destructive_redirect(tmp_path: Path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    father = "2026-10-01-family-searches-for-missing-port-st-lucie-father"
    woman = "2026-10-02-sheriff-searches-for-missing-fort-pierce-woman"
    source_url = "https://example.com/news/same-source-article"
    father_row = {
        "slug": father,
        "headline": "Family searches for missing Port St. Lucie father",
        "teaser": "Relatives are seeking information about a missing father.",
        "source_url": source_url,
        "date": "2026-10-01",
    }
    woman_row = {
        "slug": woman,
        "headline": "Sheriff seeks help finding Fort Pierce woman reported missing",
        "teaser": "Deputies are searching for a missing woman.",
        "source_url": source_url,
        "date": "2026-10-02",
    }
    father_html = "<html><body>Original father report remains.</body></html>"
    woman_html = "<html><body>Original woman report remains.</body></html>"
    (articles / f"{father}.html").write_text(father_html, encoding="utf-8")
    (articles / f"{woman}.html").write_text(woman_html, encoding="utf-8")
    archive, redirects = g.apply_canonical_story_cleanup(
        [father_row, woman_row], articles, tmp_path
    )
    assert {row["slug"] for row in archive} == {father, woman}
    assert not any(row.get("source_slug") == woman for row in redirects)
    assert (articles / f"{father}.html").read_text(encoding="utf-8") == father_html
    assert (articles / f"{woman}.html").read_text(encoding="utf-8") == woman_html
    report = json.loads(
        (tmp_path / "data" / "canonical-redirect-rejections.json").read_text(encoding="utf-8")
    )
    assert report["rejected_redirects"]
    assert report["rejected_redirects"][0]["subject_conflict"] == "gender_conflict"
    assert not (tmp_path / "_redirects").exists()
