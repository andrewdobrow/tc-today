"""October 28 fourth Horstman duplicate after the custom headline was rewritten.

This regression must protect the original manual scoop when an authoritative
material update changes its headline (not its immutable slug/custom_id).
The queue has legitimately rotated to the October 30-November 1 weekend guide.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tct_engine.custom_named_incident_identity import (
    same_named_incident_as_custom,
    potential_named_custom_collision,
    assert_no_unresolved_named_custom_collisions,
)

ROOT = Path(__file__).resolve().parents[1]
CUSTOM = "2026-10-26-st-lucie-detective-tyler-horstman-felony-dui-arrest"
ESCAPE = "2026-10-28-st-lucie-county-deputy-charged-with-dui-after-vero-beach-crash-placed-on-unpaid"

# Independently frozen exact information from the escape, so the protection
# continues to be tested after the cleanup removes the duplicate from archive.
ESCAPED_ARTICLE = {
    "slug": ESCAPE,
    "date": "2026-10-28",
    "headline": "St. Lucie County deputy charged with DUI after Vero Beach crash, placed on unpaid leave",
    "teaser": (
        "St. Lucie County sheriff's detective Tyler Horstman has been charged "
        "with DUI and placed on unpaid administrative leave following a March 1 "
        "crash in Vero Beach that seriously injured a woman."
    ),
    "is_custom": False,
    "authoritative_custom": False,
    "source_url": "https://www.wpbf.com/article/florida-vero-beach-dui-deputy-crash-arrest/74264470",
}


def authoritative_custom():
    archive = json.loads((ROOT / "archive.json").read_text(encoding="utf8"))
    matches = [row for row in archive if row.get("slug") == CUSTOM]
    assert len(matches) == 1, "Original Horstman custom canonical must survive queue rotation"
    return matches[0]


def rewritten_headline_custom():
    a = dict(authoritative_custom())
    a["headline"] = "Arrest report details speeding, 0.246 blood-alcohol level in deputy's Vero Beach crash"
    assert "Tyler Horstman" in a["teaser"]
    assert "Tyler Horstman" not in a["headline"]
    assert "tyler-horstman" in a["custom_id"]
    return a


def test_original_custom_is_still_authoritative_after_material_headline_update():
    original = rewritten_headline_custom()
    candidate = dict(ESCAPED_ARTICLE)
    matched, key = same_named_incident_as_custom(candidate, original)
    assert matched
    assert "tyler-horstman" in key
    assert potential_named_custom_collision(candidate, original)


def test_forward_identity_and_final_cleanup_both_redirect_october_28_copy():
    from scripts import generate as g

    original = rewritten_headline_custom()
    copy = dict(ESCAPED_ARTICLE)

    target, confidence, reason = g._find_authoritative_custom_incident_match(
        copy, archived_customs=[original], current_customs=[]
    )
    assert target is original
    assert confidence == 100
    assert "named-custom-incident" in reason

    target, reason = g._published_skip_canonical(copy, [original])
    assert target is original
    assert "named-custom-incident" in reason

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        cleaned, redirects = g.apply_canonical_story_cleanup(
            [original, copy], root / "articles", root
        )
    assert [row["slug"] for row in cleaned] == [CUSTOM]
    assert any(
        row["source_slug"] == ESCAPE and row["target_slug"] == CUSTOM
        and row["canonical_is_custom"] and row["match_confidence"] == 100
        for row in redirects
    )


def test_final_publication_guard_blocks_duplicate_even_if_prior_gates_fail():
    original = rewritten_headline_custom()
    candidate = dict(ESCAPED_ARTICLE)
    import pytest

    with pytest.raises(RuntimeError, match="Custom canonical publication safety gate FAILED"):
        assert_no_unresolved_named_custom_collisions([original, candidate])


def test_recovery_does_not_merge_different_person_or_different_crash():
    original = rewritten_headline_custom()
    different_person = dict(ESCAPED_ARTICLE)
    different_person["teaser"] = different_person["teaser"].replace(
        "Tyler Horstman", "Jordan Smith"
    )
    assert not same_named_incident_as_custom(different_person, original)[0]
    assert not potential_named_custom_collision(different_person, original)

    new_incident = dict(ESCAPED_ARTICLE)
    new_incident["teaser"] = new_incident["teaser"].replace(
        "March 1 crash", "May 17 crash"
    )
    assert not same_named_incident_as_custom(new_incident, original)[0]
    assert not potential_named_custom_collision(new_incident, original)

    removed_authority = dict(original, is_custom=False, authoritative_custom=False)
    assert not same_named_incident_as_custom(ESCAPED_ARTICLE, removed_authority)[0]


def test_no_new_custom_article_is_queued_to_fix_past_incident():
    queue = json.loads((ROOT / "custom_articles.json").read_text(encoding="utf8"))
    assert all(row.get("slug") != ESCAPE for row in queue)
    assert all(row.get("slug") != CUSTOM for row in queue)
