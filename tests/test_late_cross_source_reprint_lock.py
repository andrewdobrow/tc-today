from __future__ import annotations

import importlib
import os
import sys
import types


def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


OLD_SOURCE_HEADLINE = (
    "Road rage crash in Port St. Lucie leaves motorcyclist seriously injured, "
    "driver arrested"
)
OLD_TCT_HEADLINE = (
    "Port St. Lucie road rage crash leaves motorcyclist with brain bleed, "
    "driver arrested"
)
NEW_TCT_HEADLINE = (
    "Road rage ends in four-vehicle crash on US 1 in Port St. Lucie, man arrested"
)
FULL_SOURCE = (
    "A road rage incident escalated into a four-vehicle crash at the intersection "
    "of South U.S. Highway 1 and Southeast Lyngate Drive in Port St. Lucie. "
    "Kevin Lonergan, 54, was driving a black Ford Super Duty pickup while pursuing "
    "a red Harley-Davidson motorcycle northbound on U.S. Highway 1, according to "
    "Port St. Lucie Police. The motorcycle entered the intersection against a red "
    "light and collided with a Chevrolet Silverado. Lonergan then ran the red light, "
    "struck the motorcycle rider and collided head-on with a blue Toyota RAV4. "
    "The rider suffered a brain bleed and facial fractures and was taken to Lawnwood "
    "Medical Center. Police arrested Lonergan on reckless driving charges."
)
THIN_SUMMARY = (
    "A man was arrested after a four-vehicle crash during a road rage incident in "
    "Port St. Lucie."
)


def _canonical(g):
    source = {
        "source_headline": OLD_SOURCE_HEADLINE,
        "article_text": FULL_SOURCE,
        "source_url": "https://publisher-a.example/road-rage-crash",
        "source_published": "2026-08-06T13:47:55Z",
        "date": "2026-08-06",
    }
    return {
        "slug": "2026-08-06-port-st-lucie-road-rage-crash-leaves-motorcyclist-with-brain-bleed-driver-arrest",
        "headline": OLD_TCT_HEADLINE,
        "teaser": FULL_SOURCE[:220],
        "body": FULL_SOURCE,
        "date": "2026-08-06",
        "first_published": "2026-08-06T13:47:55Z",
        "source_url": source["source_url"],
        "source_headline": OLD_SOURCE_HEADLINE,
        "event_identity": g._event_identity_snapshot(source),
        "editorial_story_id": "story_old_fragment",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
        "category_key": "crime",
    }


def _incoming():
    return {
        "title": NEW_TCT_HEADLINE,
        "headline": NEW_TCT_HEADLINE,
        "source_headline": NEW_TCT_HEADLINE,
        # This field intentionally exists and is intentionally thin. It reproduced
        # the production escape: before v1.13.3.5 it hid article_text completely.
        "source_summary": THIN_SUMMARY,
        "summary": THIN_SUMMARY,
        "teaser": THIN_SUMMARY,
        "article_text": FULL_SOURCE,
        "body": FULL_SOURCE,
        "published": "2026-08-09T00:20:00Z",
        "date": "2026-08-09",
        "source_url": "https://publisher-b.example/road-rage-four-vehicle-crash",
        "link": "https://publisher-b.example/road-rage-four-vehicle-crash",
        "editorial_story_id": "story_new_fragment",
        "_editorial_story_id": "story_new_fragment",
        "_editorial_route": "generate_new",
        "_editorial_relationship": "new_story",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
        "category_key": "crime",
    }


def test_full_publisher_article_cannot_be_hidden_by_thin_rss_summary():
    g = _load_generate()
    snapshot = g._event_identity_snapshot(_incoming())

    assert "kevin lonergan" in snapshot["people"]
    assert "south-us-highway" in snapshot["precise_locations"]
    assert "southeast-lyngate-drive" in snapshot["precise_locations"]
    assert "port-st-lucie-police" in snapshot["agencies"]
    assert "crash" in snapshot["event_families"]
    assert len(snapshot["distinctive_tokens"]) >= 20


def test_delayed_cross_publisher_reprint_binds_before_generation_despite_fragmented_story_id():
    g = _load_generate()
    canonical = _canonical(g)
    incoming = _incoming()
    ledger = g._build_canonical_publication_ledger([canonical])

    target, basis, _keys = g._canonical_publication_ledger_target(incoming, ledger)

    assert target is not None
    assert target["slug"] == canonical["slug"]
    assert basis.startswith("event-identity-authority:")
    assert incoming["_editorial_route"] == "update_existing"
    assert incoming["editorial_story_id"] == canonical["editorial_story_id"]
    evidence = incoming["_cross_source_identity_match"]
    assert evidence["write_authorized"] is True
    assert "shared_named_people" in evidence["evidence_dimensions"]
    assert "shared_precise_location" in evidence["evidence_dimensions"]


def test_final_copy_late_reprint_lock_proves_same_incident_without_story_id_authority():
    g = _load_generate()
    old = _canonical(g)
    later = _incoming()
    later.pop("event_identity", None)
    later["slug"] = "2026-08-09-road-rage-ends-in-four-vehicle-crash-on-us-1-in-port-st-lucie-man-arrested"

    evidence = g._late_reprint_same_event_evidence(later, old)

    assert evidence["matched"] is True
    assert evidence["write_authorized"] is True
    assert evidence["proof_type"] == "late_reprint_participant_incident_composite"
    assert "kevin lonergan" in evidence["shared_named_people"]
    assert "south-us-highway" in evidence["shared_precise_locations"]
    assert "port-st-lucie-police" in evidence["shared_agencies"]


def test_late_reprint_lock_rejects_unrelated_same_city_crash():
    g = _load_generate()
    old = _canonical(g)
    unrelated = {
        "slug": "2026-08-08-port-st-lucie-crash-on-crosstown-parkway",
        "headline": "Driver arrested after separate crash on Crosstown Parkway in Port St. Lucie",
        "teaser": "A separate crash in Port St. Lucie led to an arrest.",
        "body": (
            "Port St. Lucie Police said Maria Lopez, 37, was arrested after a two-car "
            "crash on Crosstown Parkway near Southwest Bayshore Boulevard. Officers "
            "said a white Honda struck a sedan. No motorcycle or U.S. 1 collision was "
            "involved."
        ),
        "date": "2026-08-08",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }

    evidence = g._late_reprint_same_event_evidence(unrelated, old)

    assert evidence["matched"] is False
    assert evidence["write_authorized"] is False


def test_existing_late_reprint_is_removed_from_archive_and_redirected_to_earlier_canonical(tmp_path):
    g = _load_generate()
    old = _canonical(g)
    later = _incoming()
    later["slug"] = "2026-08-09-road-rage-ends-in-four-vehicle-crash-on-us-1-in-port-st-lucie-man-arrested"
    later["event_identity"] = {
        # Simulate the already-published thin legacy snapshot. Retrospective repair
        # must use final copy without rewriting this immutable source record.
        "schema_version": "1.0",
        "origin": "source_derived",
        "source_url": later["source_url"],
        "source_headline": later["source_headline"],
        "source_published": later["published"],
        "incident_anchor": "",
        "known_event_key": "",
        "locality": ["port-st-lucie", "st-lucie"],
        "event_families": ["crash"],
        "people": [],
        "precise_locations": [],
        "agencies": [],
        "subject_phrases": [],
        "headline_topic_tokens": ["crash", "rage", "road"],
        "distinctive_tokens": ["crash", "rage", "road", "four", "vehicle"],
    }

    cleaned, redirects, report = g._repair_recent_late_reprint_archive_duplicates(
        [old, later], tmp_path, phase="regression"
    )

    assert [row["slug"] for row in cleaned] == [old["slug"]]
    assert len(redirects) == 1
    assert redirects[0]["source_slug"] == later["slug"]
    assert redirects[0]["target_slug"] == old["slug"]
    assert redirects[0]["story_stage"] == "late-cross-source-reprint-lock"
    assert report["redirected_count"] == 1
    assert later["event_identity"]["people"] == []
    assert (tmp_path / "data" / "late-reprint-identity-lock-regression.json").exists()
