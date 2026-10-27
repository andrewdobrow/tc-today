"""Last-resort no-duplicate invariant for authoritative custom article output."""
import pytest
import ast
from pathlib import Path

from tct_engine.custom_named_incident_identity import (
    assert_no_unresolved_named_custom_collisions,
    potential_named_custom_collision,
)

CUSTOM = "2026-10-26-st-lucie-detective-tyler-horstman-felony-dui-arrest"
DUP = "2026-10-26-st-lucie-county-detective-arrested-on-dui-charge-after-crash-in-agency-vehicle"


def _custom():
    return {
        "slug": CUSTOM, "date": "2026-10-26",
        "headline": "St. Lucie County Detective Tyler Horstman Arrested on Felony DUI Charge",
        "teaser": (
            "St. Lucie County Detective Tyler Horstman turned himself in Monday "
            "on a felony DUI warrant tied to a March 2 crash in Vero Beach involving "
            "an agency vehicle."
        ),
        "is_custom": True, "authoritative_custom": True,
        "image_url": "https://treasurecoast.today/images/tyler-horstman.jpg",
        "first_published": "Mon, 26 Oct 2026 20:25:50 -0400",
    }


def _feed():
    return {
        "slug": DUP, "date": "2026-10-26",
        "headline": "St. Lucie County detective arrested on DUI charge after crash in agency vehicle",
        "teaser": (
            "St. Lucie County Sheriff’s Office Detective Tyler A. Horstman "
            "arrested Monday, Oct. 26, after an off-duty DUI crash "
            "in an agency vehicle in Vero Beach."
        ),
        "is_custom": False,
    }


def test_final_barrier_blocks_precise_production_duplicate_if_cleanup_fails():
    assert potential_named_custom_collision(_feed(), _custom())
    with pytest.raises(RuntimeError, match="Custom canonical publication safety gate FAILED") as exc:
        assert_no_unresolved_named_custom_collisions([_custom(), _feed()])
    assert CUSTOM in str(exc.value)
    assert DUP in str(exc.value)


def test_final_barrier_blocks_ambiguous_two_fact_copy_instead_of_minting_url():
    feed = _feed()
    feed["headline"] = "St. Lucie County detective arrested on DUI charge"
    feed["teaser"] = (
        "St. Lucie County Detective Tyler A. Horstman was arrested on a DUI "
        "charge in Vero Beach."
    )
    assert potential_named_custom_collision(feed, _custom())
    with pytest.raises(RuntimeError, match="unresolved possible duplicate"):
        assert_no_unresolved_named_custom_collisions([_custom(), feed])


def test_after_canonical_cleanup_one_original_custom_passes():
    original = _custom()
    assert assert_no_unresolved_named_custom_collisions([original]) is True
    assert original["image_url"].endswith("/images/tyler-horstman.jpg")
    assert original["first_published"] == "Mon, 26 Oct 2026 20:25:50 -0400"


def test_new_person_and_unrelated_subject_do_not_block_publication():
    feed = _feed()
    feed["teaser"] = feed["teaser"].replace("Tyler A. Horstman", "Jordan A. Smith")
    assert not potential_named_custom_collision(feed, _custom())
    assert assert_no_unresolved_named_custom_collisions([_custom(), feed])


def test_different_named_headline_subject_cannot_be_silently_suppressed():
    feed = _feed()
    feed["headline"] = "Jordan Smith arrested after DUI crash in St. Lucie County"
    assert not potential_named_custom_collision(feed, _custom())


def test_different_incident_date_does_not_create_false_collision():
    feed = _feed()
    feed["date"] = "2026-11-07"
    feed["slug"] = "2026-11-07-detective-tyler-horstman-arrested-after-another-incident"
    assert not potential_named_custom_collision(feed, _custom())


def test_distinct_crash_dates_remain_separate():
    feed = _feed()
    feed["teaser"] = (
        "St. Lucie County Detective Tyler A. Horstman was arrested for DUI "
        "after a May 17 crash involving an agency vehicle in Vero Beach."
    )
    assert not potential_named_custom_collision(feed, _custom())


def test_other_custom_articles_are_never_redirect_candidates():
    second = _custom()
    second["slug"] = "2026-10-26-second-custom"
    assert not potential_named_custom_collision(second, _custom())
    assert assert_no_unresolved_named_custom_collisions([_custom(), second])


def test_final_gate_is_wired_into_production_archive_writer():
    # Prevent a future refactor from leaving this safety rule as a tested-but-
    # unused helper. The AST check avoids fragile line-number assertions.
    source = Path("scripts/generate.py").read_text(encoding="utf8")
    module = ast.parse(source)
    writer = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "write_archives"
    )
    calls = [
        node.func.id for node in ast.walk(writer)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "assert_no_unresolved_named_custom_collisions" in calls
    assert "apply_canonical_story_cleanup" in calls
