"""Production Horstman regression: custom scoop owns every later feed version."""
import importlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from tct_engine.custom_named_incident_identity import same_named_incident_as_custom

CUSTOM_SLUG = "2026-10-26-st-lucie-detective-tyler-horstman-felony-dui-arrest"
DUP_SLUG = (
    "2026-10-26-st-lucie-county-detective-arrested-on-dui-charge-"
    "after-crash-in-agency-vehicle"
)
IMAGE = "https://treasurecoast.today/images/tyler-horstman.jpg"


def custom():
    return {
        "slug": CUSTOM_SLUG,
        "headline": "St. Lucie County Detective Tyler Horstman Arrested on Felony DUI Charge",
        "teaser": (
            "St. Lucie County Detective Tyler Horstman turned himself in Monday "
            "on a felony DUI warrant tied to a March 2 crash in Vero Beach "
            "involving an agency vehicle, Sheriff Richard Del Toro Jr. said."
        ),
        "date": "2026-10-26",
        "is_custom": True,
        "authoritative_custom": True,
        "image_url": IMAGE,
        "canonical_slug": CUSTOM_SLUG,
        "first_published": "Mon, 26 Oct 2026 20:25:50 -0400",
    }


def duplicate():
    return {
        "slug": DUP_SLUG,
        "headline": (
            "St. Lucie County detective arrested on DUI charge after crash "
            "in agency vehicle"
        ),
        "teaser": (
            "St. Lucie County Sheriff’s Office Detective Tyler A. Horstman was "
            "arrested Monday, Oct. 26, on a charge of DUI causing serious bodily "
            "injury to another after an off-duty crash in Vero Beach."
        ),
        "date": "2026-10-26",
        "is_custom": False,
        "authoritative_custom": False,
        "source_url": (
            "https://www.wpbf.com/article/tyler-horstman-st-lucie-county-"
            "sheriffs-deputy-arrested-dui-charge-off-duty-crash/74254345"
        ),
        "image_url": "https://example.org/feed-copy.jpg",
    }


def test_same_incident_survives_role_only_headline_and_middle_initial():
    match, basis = same_named_incident_as_custom(duplicate(), custom())
    assert match
    assert basis.startswith("named-custom-incident|tyler-horstman|")



def test_incoming_rss_source_without_slug_still_resolves_to_custom():
    # This is the important forward-publication form: no minted permalink yet.
    incoming = duplicate()
    incoming.pop("slug")
    incoming.pop("date")
    incoming["source_published"] = "Tue, 27 Oct 2026 01:08:00 GMT"
    assert same_named_incident_as_custom(incoming, custom())[0]


def test_middle_initial_in_manual_custom_headline_is_supported():
    authority = custom()
    authority["headline"] = authority["headline"].replace(
        "Tyler Horstman", "Tyler A. Horstman"
    )
    assert same_named_incident_as_custom(duplicate(), authority)[0]


def test_no_surname_only_capture():
    incoming = duplicate()
    incoming["teaser"] = incoming["teaser"].replace("Tyler A. Horstman", "Detective Horstman")
    assert not same_named_incident_as_custom(incoming, custom())[0]


def test_unrelated_person_is_not_suppressed():
    incoming = duplicate()
    incoming["teaser"] = incoming["teaser"].replace("Tyler A. Horstman", "Jordan A. Smith")
    assert not same_named_incident_as_custom(incoming, custom())[0]


def test_other_primary_named_person_is_not_redirected():
    incoming = duplicate()
    incoming["headline"] = "Jordan Smith arrested in St. Lucie County DUI crash"
    assert not same_named_incident_as_custom(incoming, custom())[0]


def test_repeated_person_is_not_sufficient_for_a_new_incident():
    incoming = duplicate()
    incoming["headline"] = "St. Lucie County Detective Tyler Horstman honored at agency ceremony"
    incoming["teaser"] = "St. Lucie County Detective Tyler Horstman received an award."
    assert not same_named_incident_as_custom(incoming, custom())[0]


def test_conflicting_crash_date_remains_separate():
    incoming = duplicate()
    incoming["teaser"] = (
        "St. Lucie County Detective Tyler A. Horstman arrested for DUI after "
        "a May 17 crash in an agency vehicle in Vero Beach."
    )
    assert not same_named_incident_as_custom(incoming, custom())[0]


def october_27_production_escape():
    # Exact new URL and lead observed in the Oct 27 green production deploy.
    return {
        "slug": "2026-10-27-st-lucie-county-detective-charged-with-dui-put-on-unpaid-leave-after-vero-beach",
        "headline": (
            "St. Lucie County detective charged with DUI, put on unpaid leave "
            "after Vero Beach crash"
        ),
        "teaser": (
            "St. Lucie County sheriff's detective Tyler Horstman faces charges "
            "including DUI and has been placed on unpaid administrative leave "
            "following a March 1 crash in Vero Beach that seriously injured a woman."
        ),
        "date": "2026-10-27",
        "is_custom": False,
        "authoritative_custom": False,
        "editorial_story_id": "feed:fragmented-oct27",
    }


def test_oct27_real_production_escape_march1_vs_march2_routes_to_original_custom():
    from tct_engine.custom_named_incident_identity import (
        assert_no_unresolved_named_custom_collisions,
        potential_named_custom_collision,
    )
    g = importlib.import_module("scripts.generate")
    original, generated = custom(), october_27_production_escape()
    matched, evidence = same_named_incident_as_custom(generated, original)
    assert matched, "Adjacent reported crash dates cannot publish two URLs for this case"
    assert evidence.startswith("named-custom-incident|tyler-horstman|")
    assert potential_named_custom_collision(generated, original)
    with pytest.raises(RuntimeError, match="Custom canonical publication safety gate"):
        assert_no_unresolved_named_custom_collisions([original, generated])
    identified, confidence, basis = g._find_authoritative_custom_incident_match(
        generated, archived_customs=[original], current_customs=[]
    )
    assert identified and identified["slug"] == CUSTOM_SLUG
    assert confidence == 100
    assert "named-custom-incident" in basis
    with TemporaryDirectory() as td:
        root = Path(td)
        (root / "articles").mkdir()
        cleaned, redirects = g.apply_canonical_story_cleanup(
            [original, generated], root / "articles", root
        )
        assert [item["slug"] for item in cleaned] == [CUSTOM_SLUG]
        assert any(
            redirect["source_slug"] == generated["slug"]
            and redirect["target_slug"] == CUSTOM_SLUG
            and redirect["canonical_is_custom"] is True
            for redirect in redirects
        )
        assert_no_unresolved_named_custom_collisions(cleaned)
        # Retired URL must remain a redirect, not an independently indexed article.
        page = (root / "articles" / f'{generated["slug"]}.html').read_text()
        assert "noindex,follow" in page
        assert f"/articles/{CUSTOM_SLUG}.html" in page
    assert original["image_url"] == IMAGE
    assert original["first_published"] == "Mon, 26 Oct 2026 20:25:50 -0400"


def test_one_day_conflict_does_not_override_person_locality_or_event_checks():
    wrong_person = october_27_production_escape()
    wrong_person["teaser"] = wrong_person["teaser"].replace(
        "Tyler Horstman", "Jordan Smith"
    )
    assert not same_named_incident_as_custom(wrong_person, custom())[0]
    wrong_place = october_27_production_escape()
    wrong_place["headline"] = "Detective charged with DUI after crash in Miami"
    wrong_place["teaser"] = (
        "Miami-Dade detective Tyler Horstman charged with DUI after a "
        "March 1 crash in Miami."
    )
    assert not same_named_incident_as_custom(wrong_place, custom())[0]
    wrong_crash = october_27_production_escape()
    wrong_crash["teaser"] = wrong_crash["teaser"].replace("March 1", "March 5")
    assert not same_named_incident_as_custom(wrong_crash, custom())[0]


def test_unrelated_locality_remains_separate():
    incoming = duplicate()
    incoming["headline"] = "Detective arrested for DUI after crash in agency vehicle"
    incoming["teaser"] = (
        "Miami-Dade Detective Tyler A. Horstman arrested for DUI "
        "after crashing an agency vehicle in Miami."
    )
    assert not same_named_incident_as_custom(incoming, custom())[0]


def test_publication_gap_prevents_conflating_a_new_episode():
    incoming = duplicate()
    incoming["slug"] = "2026-11-11-another-horstman-dui-crash"
    incoming["date"] = "2026-11-11"
    assert not same_named_incident_as_custom(incoming, custom())[0]


def test_noncustom_authority_cannot_take_over():
    authority = custom()
    authority["is_custom"] = False
    authority["authoritative_custom"] = False
    assert not same_named_incident_as_custom(duplicate(), authority)[0]


def test_production_matching_and_final_cleanup_redirects_to_custom():
    # All three production checkpoints use the same durable identity contract.
    g = importlib.import_module("scripts.generate")
    original, copy = custom(), duplicate()
    match, confidence, reason = g._find_authoritative_custom_incident_match(
        copy, archived_customs=[original], current_customs=[]
    )
    assert match["slug"] == CUSTOM_SLUG
    assert confidence == 100
    assert "named-custom-incident" in reason

    match, reason = g._published_skip_canonical(copy, [original])
    assert match and match["slug"] == CUSTOM_SLUG
    assert "named-custom-incident" in reason

    with TemporaryDirectory() as td:
        root = Path(td)
        (root / "articles").mkdir()
        cleaned, redirects = g.apply_canonical_story_cleanup(
            [original, copy], root / "articles", root
        )
    assert [r["slug"] for r in cleaned] == [CUSTOM_SLUG]
    assert original["image_url"] == IMAGE
    assert original["first_published"] == "Mon, 26 Oct 2026 20:25:50 -0400"
    assert any(
        r["source_slug"] == DUP_SLUG
        and r["target_slug"] == CUSTOM_SLUG
        and r["canonical_is_custom"]
        for r in redirects
    )


def test_live_archive_keeps_custom_scoop_identity_and_can_repair_duplicate():
    archive_path = Path("archive.json")
    if not archive_path.exists():
        pytest.skip("No deployed archive fixture")
    archive = json.loads(archive_path.read_text(encoding="utf8"))
    originals = [row for row in archive if row.get("slug") == CUSTOM_SLUG]
    assert len(originals) == 1
    original = originals[0]
    assert original.get("is_custom") and original.get("authoritative_custom")
    assert original.get("canonical_slug") == CUSTOM_SLUG
    assert original.get("image_url") == IMAGE
    copies = [row for row in archive if row.get("slug") == DUP_SLUG]
    if copies:
        assert same_named_incident_as_custom(copies[0], original)[0]
