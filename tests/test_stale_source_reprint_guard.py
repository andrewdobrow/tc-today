from datetime import datetime, timezone

from scripts import generate


def _article(*, headline, body, date, source_identity=None):
    return {
        "headline": headline,
        "teaser": body.split(".", 1)[0] + ".",
        "body": body,
        "date": date,
        "category_key": "martin",
        "category_label": "Martin County",
        "event_identity": source_identity or {},
    }


def test_new_publication_source_hard_age_blocks_48_hour_county_reprint():
    item = {"published": "Fri, 07 Aug 2026 05:39:58 GMT"}
    now = datetime(2026, 8, 9, 5, 44, 8, tzinfo=timezone.utc)
    assert generate.new_publication_source_max_age_hours("martin") == 48
    assert generate._new_publication_source_is_stale(item, "martin", now=now)


def test_source_focus_strips_landing_page_contamination_before_identity():
    unrelated = (
        "Election coverage continues across neighboring counties. "
        "A famous athlete's father died Saturday at a hospital overseas. "
        "Police are investigating a separate shooting in another city. "
    )
    text = (unrelated * 18) + (
        "According to the Stuart Police Department, Harbor Market at 3173 Kanner Highway "
        "experienced an electrical fire that has since been extinguished. "
        "Harbor Market reopened following the electrical fire after temporarily closing Thursday. "
        "The Stuart Police Department said only dry goods are available while refrigeration remains down. "
        "Customers were asked to avoid the area while the store was closed. "
    ) + (unrelated * 8)
    focused = generate._focus_extracted_source_text(
        text,
        {"title": "Harbor Market reopens following electrical fire at Martin County location"},
    )
    assert "Harbor Market" in focused
    assert "electrical fire" in focused.lower()
    assert "famous athlete" not in focused.lower()
    assert "separate shooting" not in focused.lower()
    assert len(focused.split()) < len(text.split()) / 2


def test_final_publication_identity_does_not_inherit_poisoned_source_snapshot():
    body = (
        "Harbor Market at 3173 Kanner Highway in Stuart reopened after an electrical fire. "
        "The Stuart Police Department said refrigeration remains offline and dry goods are available."
    )
    item = _article(
        headline="Harbor Market reopens after electrical fire with limited inventory",
        body=body,
        date="2026-08-09",
        source_identity={
            "schema_version": "1.0",
            "incident_anchor": "named-person-death:unrelated-person",
            "event_families": ["shooting"],
            "locality": ["fort-myers"],
            "agencies": ["unrelated-police"],
        },
    )
    features = generate._final_publication_identity_features(item, include_archive_body=True)
    assert features["incident_anchor"] == ""
    assert "fire" in features["event_families"]
    assert "shooting" not in features["event_families"]
    assert "stuart-police" in features["agencies"]
    assert "fort-myers" not in features["locality"]


def test_late_reprint_matches_same_site_with_directional_address_variant():
    old = _article(
        headline="Harbor Market reopens after electrical fire but refrigeration remains down",
        body=(
            "Harbor Market at 3173 S. Kanner Highway in Stuart reopened Friday after an electrical fire. "
            "The Stuart Police Department said only dry goods are available while refrigeration remains down. "
            "The electrical fire forced the store to close Thursday and shoppers were asked to avoid the area."
        ),
        date="2026-08-06",
    )
    new = _article(
        headline="Harbor Market reopens after electrical fire with limited inventory",
        body=(
            "Harbor Market at 3173 Kanner Highway in Stuart reopened after an electrical fire. "
            "The Stuart Police Department said only dry goods are available because refrigeration is offline. "
            "The store temporarily closed Thursday and shoppers were asked to avoid the area."
        ),
        date="2026-08-09",
        source_identity={
            "schema_version": "1.0",
            "incident_anchor": "named-person-death:sidebar-person",
            "event_families": ["shooting"],
        },
    )
    evidence = generate._late_reprint_same_event_evidence(new, old)
    assert evidence["write_authorized"] is True
    assert evidence["proof_type"] == "late_reprint_strong_same_site_composite"
    assert "3173-kanner-highway" in evidence["shared_precise_locations"]
    assert "stuart-police" in evidence["shared_agencies"]
