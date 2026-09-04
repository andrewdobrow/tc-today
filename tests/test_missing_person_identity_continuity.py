from __future__ import annotations

import importlib
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

from tct_engine import EditorialAction, EditorialEngine
from tct_engine.incident_identity import incident_anchor_key
from tct_engine.unified_incident_identity import (
    build_unified_incident_evidence,
    compare_unified_incident_evidence,
    unified_incident_components,
)

CANONICAL = (
    "2026-08-06-martin-county-sheriffs-office-seeks-public-help-finding-"
    "missing-14-year-old-auti"
)
DUPLICATE = (
    "2026-08-06-martin-county-deputies-search-for-missing-autistic-teen-"
    "last-seen-in-palm-city"
)
WPBF_URL = (
    "https://www.wpbf.com/article/florida-palm-city-missing-14-year-old-"
    "autistic-boy/73360714"
)
WPEC_URL = (
    "https://cbs12.com/news/local/martin-county-deputies-seek-autistic-"
    "missing-14-year-old-boy-last-seen-grand-oaks-living-facility-"
    "coquina-cove-florida-news"
)
WPBF_TITLE = (
    "Authorities need help finding 14-year-old autistic boy last seen in "
    "Palm City - WPBF"
)
WPEC_TITLE = (
    "Martin County deputies seek help finding missing autistic teen last "
    "seen in Palm City - WPEC"
)


def _load_generate_module():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")
        anthropic.Anthropic = lambda *args, **kwargs: types.SimpleNamespace(
            messages=types.SimpleNamespace(create=lambda **kwargs: None)
        )
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def _production_evidence(title: str, url: str):
    return build_unified_incident_evidence(
        title=title,
        body=url,
        source_url=url,
        locations=("Palm City",),
        published_at="2026-08-06T00:00:00+00:00",
    )


def test_exact_ethan_boyd_source_framings_share_verified_identity():
    first = _production_evidence(WPBF_TITLE, WPBF_URL)
    second = _production_evidence(WPEC_TITLE, WPEC_URL)

    assert first.family == second.family == "missing_person"
    assert "age_14" in first.concepts
    assert "age_14" in second.concepts
    confidence, trace = compare_unified_incident_evidence(first, second)
    assert confidence >= 0.96
    assert "Identity anchors qualified: True" in trace


def test_missing_person_name_patterns_extract_age_before_and_after_name():
    before = build_unified_incident_evidence(
        title="Deputies search for missing teen",
        body="Authorities are searching for 14-year-old Ethan Boyd, who was last seen Wednesday.",
        locations=("Palm City",),
    )
    after = build_unified_incident_evidence(
        title="Public asked to help find missing boy",
        body="Ethan Boyd, a 14-year-old autistic boy, was last seen near Grand Oaks.",
        locations=("Palm City",),
    )
    assert before.people == ("ethan boyd",)
    assert after.people == ("ethan boyd",)


def test_different_named_missing_teens_in_same_city_do_not_merge():
    ethan = build_unified_incident_evidence(
        title="Deputies search for missing autistic teen last seen in Palm City",
        body="14-year-old Ethan Boyd was last seen near Grand Oaks.",
        locations=("Palm City",),
        published_at="2026-08-06T00:00:00+00:00",
    )
    jordan = build_unified_incident_evidence(
        title="Deputies search for missing autistic teen last seen in Palm City",
        body="14-year-old Jordan Smith was last seen near another neighborhood.",
        locations=("Palm City",),
        published_at="2026-08-06T01:00:00+00:00",
    )
    confidence, trace = compare_unified_incident_evidence(ethan, jordan)
    assert confidence == 0.0
    assert "Missing-person name conflict: True" in trace


def test_different_ages_in_same_city_do_not_merge_without_shared_name():
    fourteen = build_unified_incident_evidence(
        title="Help find missing 14-year-old autistic boy last seen in Palm City",
        locations=("Palm City",),
    )
    fifteen = build_unified_incident_evidence(
        title="Help find missing 15-year-old autistic boy last seen in Palm City",
        locations=("Palm City",),
    )
    confidence, trace = compare_unified_incident_evidence(fourteen, fifteen)
    assert confidence == 0.0
    assert "Missing-person age conflict: True" in trace


def test_editorial_engine_reuses_story_across_sparse_publisher_framings(tmp_path: Path):
    engine = EditorialEngine(
        default_published_at=datetime(2026, 8, 6, tzinfo=timezone.utc),
        registry_path=tmp_path / "registry.json",
    )
    first = engine.process(
        {
            "id": "wpbf-ethan",
            "title": WPBF_TITLE,
            "link": WPBF_URL,
            "summary": (
                "Authorities are asking for help finding a 14-year-old autistic "
                "boy last seen in Palm City."
            ),
        },
        source="WPBF",
        county="Martin",
    )
    second = engine.process(
        {
            "id": "wpec-ethan",
            "title": WPEC_TITLE,
            "link": WPEC_URL,
            "summary": (
                "Deputies are searching for a missing autistic teen last seen in "
                "Palm City."
            ),
        },
        source="WPEC",
        county="Martin",
    )
    assert second.story_id == first.story_id
    assert second.action in {EditorialAction.IGNORE, EditorialAction.UPDATE_EXISTING}
    assert second.relationship == "same_event"


def test_registry_repair_can_join_legacy_unknown_and_missing_person_records():
    stories = {
        "story_002406": {
            "story_id": "story_002406",
            "status": "active",
            "canonical_title": WPBF_TITLE,
            "titles": [WPBF_TITLE],
            "locations": ["Palm City"],
            "timeline": [
                {
                    "title": WPBF_TITLE,
                    "source": WPBF_URL,
                    "published_at": "2026-08-06T00:00:54+00:00",
                }
            ],
            "unified_incident_evidence": [
                {
                    "family": "unknown",
                    "concepts": [],
                    "people": [],
                    "locations": ["palm city"],
                    "agencies": [],
                    "distinctive_tokens": ["autistic", "last", "seen"],
                    "title_tokens": ["autistic", "last", "seen"],
                    "published_at": "2026-08-06T00:00:54+00:00",
                }
            ],
        },
        "story_002374": {
            "story_id": "story_002374",
            "status": "active",
            "canonical_title": WPEC_TITLE,
            "titles": [WPEC_TITLE],
            "locations": ["Palm City"],
            "timeline": [
                {
                    "title": WPEC_TITLE,
                    "source": WPEC_URL,
                    "published_at": "2026-08-05T23:49:33+00:00",
                }
            ],
            "unified_incident_evidence": [
                {
                    "family": "unknown",
                    "concepts": [],
                    "people": [],
                    "locations": ["palm city"],
                    "agencies": [],
                    "distinctive_tokens": ["autistic", "last", "seen"],
                    "title_tokens": ["autistic", "last", "seen"],
                    "published_at": "2026-08-05T23:49:33+00:00",
                }
            ],
        },
    }
    assert unified_incident_components(stories) == [
        {"story_002374", "story_002406"}
    ]


def test_existing_missing_person_duplicate_redirects_to_first_canonical(tmp_path: Path):
    generate = _load_generate_module()
    articles = tmp_path / "articles"
    articles.mkdir()
    archive = [
        {
            "slug": CANONICAL,
            "headline": (
                "Martin County Sheriff's Office seeks public help finding missing "
                "14-year-old autistic boy in Palm City"
            ),
            "teaser": (
                "The Martin County Sheriff's Office is asking for help locating "
                "Ethan Boyd, a 14-year-old autistic boy missing in Palm City."
            ),
            "source_url": WPBF_URL,
            "date": "2026-08-06",
            "first_published": "Wed, 05 Aug 2026 22:33:30 -0400",
        },
        {
            "slug": DUPLICATE,
            "headline": (
                "Martin County deputies search for missing autistic teen last seen "
                "in Palm City"
            ),
            "teaser": (
                "The Martin County Sheriff's Office is seeking assistance locating "
                "14-year-old Ethan Boyd near Grand Oaks and Coquina Cove."
            ),
            "source_url": WPEC_URL,
            "date": "2026-08-06",
            "first_published": "Wed, 05 Aug 2026 22:33:33 -0400",
        },
    ]
    cleaned, redirects = generate.apply_canonical_story_cleanup(
        archive, articles, tmp_path
    )
    assert [row["slug"] for row in cleaned] == [CANONICAL]
    redirect = next(row for row in redirects if row["source_slug"] == DUPLICATE)
    assert redirect["target_slug"] == CANONICAL
    rendered = (articles / f"{DUPLICATE}.html").read_text()
    assert f"/articles/{CANONICAL}.html" in rendered
    assert "noindex,follow" in rendered


def _debevec_custom_canonical():
    return {
        "slug": (
            "2026-08-29-martin-county-sheriffs-office-searches-for-missing-"
            "oklahoma-visitor-last-seen-at-chastain-beach"
        ),
        "headline": (
            "Martin County Sheriff's Office searches for missing Oklahoma visitor "
            "last seen at Chastain Beach"
        ),
        "teaser": (
            "The Martin County Sheriff's Office is asking for help finding Michael "
            "Anthony Debevec II, an Oklahoma visitor last seen Aug. 26 after going "
            "to Chastain Beach."
        ),
        "category_key": "martin",
        "category_label": "Martin County",
        "date": "2026-08-29",
        "lastmod": "2026-08-29",
        "first_published": "Sat, 29 Aug 2026 21:48:09 -0400",
        "editorial_story_id": "custom:debevec",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
        "is_custom": True,
        "authoritative_custom": True,
    }


def _debevec_later_publisher_source():
    body = (
        "Martin County Sheriff's Office deputies say they're searching for Michael "
        "Anthony Debevec II, who was visiting the area with family when he disappeared "
        "on August 26. Debevec went to Chastain Beach, also known as the rocks, and "
        "his vehicle was later found nearby. His family has not heard from him and "
        "authorities say he may be experiencing an emotional breakdown. Debevec is "
        "described as 5 feet, 7 inches tall with blue eyes."
    )
    return {
        "title": "Search underway for Oklahoma man after vehicle found at Chastain Beach",
        "headline": "Search underway for Oklahoma man after vehicle found at Chastain Beach",
        "summary": body,
        "article_text": body + " " + body + " " + body,
        "source_url": (
            "https://cbs12.com/news/local/search-underway-for-oklahoma-man-after-"
            "vehicle-found-at-chastain-beach"
        ),
        "link": (
            "https://cbs12.com/news/local/search-underway-for-oklahoma-man-after-"
            "vehicle-found-at-chastain-beach"
        ),
        "published": "Sun, 30 Aug 2026 16:00:00 GMT",
        "source_quality": "full",
        # Deliberately fragmented registry identity: durable custom incident identity
        # must outrank this and prevent a second public URL.
        "editorial_story_id": "story_fragmented_debevec",
        "_editorial_story_id": "story_fragmented_debevec",
        "_editorial_route": "new_story",
    }


def test_named_missing_person_publisher_drift_matches_authoritative_custom():
    g = _load_generate_module()
    matched, key = g._durable_custom_identity_match(
        _debevec_later_publisher_source(), _debevec_custom_canonical()
    )
    assert matched is True
    assert key == "missing-person|michael-debevec"


def test_fragmented_registry_cannot_mint_second_url_for_named_custom_missing_person():
    g = _load_generate_module()
    custom = _debevec_custom_canonical()
    source = _debevec_later_publisher_source()

    canonical, basis = g._published_skip_canonical(source, [custom])

    assert canonical is custom
    assert basis.startswith("durable_custom_incident_identity:missing-person|")


def test_existing_debevec_duplicate_redirects_to_custom_canonical(tmp_path: Path):
    g = _load_generate_module()
    articles = tmp_path / "articles"
    articles.mkdir()
    custom = _debevec_custom_canonical()
    duplicate = {
        "slug": (
            "2026-08-30-martin-county-sheriffs-office-searches-for-missing-"
            "oklahoma-man-last-seen-at-hut"
        ),
        **_debevec_later_publisher_source(),
        "headline": (
            "Martin County Sheriff's Office searches for missing Oklahoma man "
            "last seen at Hutchinson Island"
        ),
        "teaser": _debevec_later_publisher_source()["summary"],
        "date": "2026-08-30",
        "lastmod": "2026-08-30",
        "first_published": "Sun, 30 Aug 2026 13:30:00 -0400",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
        "is_custom": False,
        "authoritative_custom": False,
    }

    cleaned, redirects = g.apply_canonical_story_cleanup(
        [custom, duplicate], articles, tmp_path
    )

    assert [row["slug"] for row in cleaned] == [custom["slug"]]
    redirect = next(row for row in redirects if row["source_slug"] == duplicate["slug"])
    assert redirect["target_slug"] == custom["slug"]
    assert redirect["canonical_is_custom"] is True
    rendered = (articles / f"{duplicate['slug']}.html").read_text(encoding="utf-8")
    assert f"/articles/{custom['slug']}.html" in rendered
    assert "noindex,follow" in rendered


def test_newer_fragmented_missing_person_source_can_update_custom_in_place(monkeypatch):
    g = _load_generate_module()
    g.CURRENT_RUN_PREGEN_MATERIAL_UPDATE_MODEL_CALLS = 0
    g.CURRENT_RUN_EDITORIAL_IDENTITIES.clear()
    custom = _debevec_custom_canonical()
    source = _debevec_later_publisher_source()

    monkeypatch.setattr(
        g,
        "adjudicate_semantic_publication_candidates",
        lambda *args, **kwargs: {
            "status": "validated",
            "action": "update_existing_canonical",
            "recommended_action": "update_existing_canonical",
            "selected_candidate_slug": custom["slug"],
            "same_real_world_event": True,
            "material_new_update": True,
            "independently_newsworthy_followup": False,
            "confidence": 0.99,
            "shared_anchors": ["Michael Anthony Debevec II", "Chastain Beach"],
            "novel_facts": ["Later publisher reporting adds family-visit context."],
            "reason": "Same named missing-person incident with a material new detail.",
            "validation_errors": [],
        },
    )

    result = g._promote_published_skip_material_updates(
        [source],
        [custom],
        "martin",
        cache={"schema_version": 1, "entries": {}},
    )

    assert result["evaluated_count"] == 1
    assert result["promoted_count"] == 1
    assert source["canonical_slug"] == custom["slug"]
    assert source["editorial_story_id"] == custom["editorial_story_id"]
    assert source["_editorial_route"] == "update_existing"
    assert g._authorized_custom_material_update(source, custom) is True


def test_known_debevec_duplicate_url_remains_redirect_even_after_archive_row_is_removed(tmp_path: Path):
    g = _load_generate_module()
    articles = tmp_path / "articles"
    articles.mkdir()
    custom = _debevec_custom_canonical()

    cleaned, redirects = g.apply_canonical_story_cleanup([custom], articles, tmp_path)

    assert [row["slug"] for row in cleaned] == [custom["slug"]]
    source_slug = next(iter(g.DEBEVEC_MISSING_REDIRECT_SOURCE_SLUGS))
    redirect = next(row for row in redirects if row["source_slug"] == source_slug)
    assert redirect["target_slug"] == g.DEBEVEC_MISSING_CANONICAL_SLUG
    rendered = (articles / f"{source_slug}.html").read_text(encoding="utf-8")
    assert f"/articles/{g.DEBEVEC_MISSING_CANONICAL_SLUG}.html" in rendered
    assert "noindex,follow" in rendered



def _debevec_actual_followup_source():
    """Exact production framing that escaped on the run after v1.13.6.8l."""
    body = (
        "The Martin County Sheriff's Office is searching for a missing man from "
        "Oklahoma who was last seen Wednesday afternoon at Chastain Beach on "
        "Hutchinson Island. Michael Debevec visited the beach known as The Rocks "
        "on the southern tip of Hutchinson Island, where his vehicle was found. "
        "His family has not heard from him. The sheriff's office said Debevec may "
        "be experiencing an emotional breakdown."
    )
    return {
        "title": (
            "Martin County Sheriff's Office searches for missing Oklahoma man "
            "last seen at Hutchinson Island beach"
        ),
        "headline": (
            "Martin County Sheriff's Office searches for missing Oklahoma man "
            "last seen at Hutchinson Island beach"
        ),
        "summary": body,
        "teaser": body,
        "article_text": body,
        "body": body,
        "source_url": "https://www.wpbf.com/example/michael-debevec-followup",
        "link": "https://www.wpbf.com/example/michael-debevec-followup",
        "published": "Sun, 30 Aug 2026 17:30:00 GMT",
        "source_quality": "full",
        "editorial_story_id": "story_fragmented_debevec_followup",
        "_editorial_story_id": "story_fragmented_debevec_followup",
        "_editorial_route": "new_story",
    }



def _debevec_good_samaritan_body_source():
    """Exact Sept. 1 source framing that resurfaced as a Sept. 3 duplicate hero."""
    body = (
        "A body was found following an extensive search in Martin County, but the sheriff's office "
        "could not confirm whether it was that of a man reported missing Aug. 26. On Tuesday, the "
        "Martin County Sheriff's Office announced that a body had been recovered from deep within "
        "the mangroves near the House of Refuge. During a news conference, Martin County Sheriff "
        "John Budensiek said a Good Samaritan found a wallet Saturday belonging to Michael Anthony "
        "Debevec. In an attempt to return the wallet, the Good Samaritan went to Debevec's home, "
        "which ultimately led his family to file a missing person report. Investigators later found "
        "Debevec's vehicle at Chastain Beach. Phone records showed Debevec moving between Chastain "
        "Beach and the House of Refuge. Investigators then found Debevec's backpack before locating "
        "a body in the mangroves."
    )
    return {
        "title": "Body believed to be missing Port St. Lucie man found in Martin County mangroves",
        "headline": "Body believed to be missing Port St. Lucie man found in Martin County mangroves",
        "summary": body,
        "teaser": body,
        "article_text": body,
        "body": body,
        "source_url": (
            "https://cw34.com/news/local/body-found-floating-near-stuart-beach-located-"
            "house-of-refuge-martin-county-sheriffs-office-investigate-missing-oklahoma-man-florida-news"
        ),
        "link": (
            "https://cw34.com/news/local/body-found-floating-near-stuart-beach-located-"
            "house-of-refuge-martin-county-sheriffs-office-investigate-missing-oklahoma-man-florida-news"
        ),
        "published": "Wed, 02 Sep 2026 06:07:31 GMT",
        "source_quality": "full",
        "source_type": "full_source",
        "editorial_story_id": "story_fragmented_body_believed",
        "_editorial_story_id": "story_fragmented_body_believed",
        "_editorial_route": "skip",
    }


def test_named_missing_person_anchor_survives_middle_name_and_suffix_drop():
    original = _debevec_custom_canonical()
    followup = _debevec_actual_followup_source()
    original_anchor = incident_anchor_key(
        titles=(original["headline"], original["teaser"]),
        body=original["teaser"],
    )
    followup_anchor = incident_anchor_key(
        titles=(followup["headline"], followup["teaser"]),
        body=followup["body"],
    )
    assert original_anchor == followup_anchor == "missing-person:michael-debevec"



def test_good_samaritan_role_phrase_cannot_become_missing_person_subject():
    source = _debevec_good_samaritan_body_source()
    anchor = incident_anchor_key(
        titles=(source["headline"], source["teaser"]),
        body=source["body"],
    )
    assert anchor != "missing-person:good-samaritan"


def test_good_samaritan_debevec_source_still_matches_authoritative_custom():
    g = _load_generate_module()
    custom = _debevec_custom_canonical()
    source = _debevec_good_samaritan_body_source()

    matched, key = g._durable_custom_identity_match(source, custom)
    assert matched is True
    assert key == "missing-person|michael-debevec"

    canonical, basis = g._published_skip_canonical(source, [custom])
    assert canonical is custom
    assert basis == "durable_custom_incident_identity:missing-person|michael-debevec"


def test_sept3_debevec_duplicate_slug_is_permanent_redirect(tmp_path: Path):
    g = _load_generate_module()
    articles = tmp_path / "articles"
    articles.mkdir()
    custom = _debevec_custom_canonical()
    escaped_slug = (
        "2026-09-03-body-found-in-martin-county-mangroves-believed-to-be-missing-"
        "port-st-lucie-man-m"
    )
    assert escaped_slug in g.DEBEVEC_MISSING_REDIRECT_SOURCE_SLUGS

    cleaned, redirects = g.apply_canonical_story_cleanup([custom], articles, tmp_path)
    assert [row["slug"] for row in cleaned] == [custom["slug"]]
    redirect = next(row for row in redirects if row["source_slug"] == escaped_slug)
    assert redirect["target_slug"] == g.DEBEVEC_MISSING_CANONICAL_SLUG
    rendered = (articles / f"{escaped_slug}.html").read_text(encoding="utf-8")
    assert f"/articles/{g.DEBEVEC_MISSING_CANONICAL_SLUG}.html" in rendered
    assert "noindex,follow" in rendered


def test_unified_missing_person_identity_accepts_first_surname_alias_when_other_side_is_unambiguous():
    original = build_unified_incident_evidence(
        title=_debevec_custom_canonical()["headline"],
        body=_debevec_custom_canonical()["teaser"],
        locations=("Martin County",),
        published_at="2026-08-29T21:48:09-04:00",
    )
    followup = build_unified_incident_evidence(
        title=_debevec_actual_followup_source()["headline"],
        body=_debevec_actual_followup_source()["body"],
        locations=("Martin County",),
        published_at="2026-08-30T17:30:00-04:00",
    )
    assert original.people == ("michael anthony debevec",)
    assert followup.people == ()
    confidence, trace = compare_unified_incident_evidence(followup, original)
    assert confidence >= 0.97
    assert "Shared person aliases: michael debevec" in trace


def test_exact_production_debevec_followup_cannot_bypass_custom_canonical():
    g = _load_generate_module()
    custom = _debevec_custom_canonical()
    followup = _debevec_actual_followup_source()

    matched, key = g._durable_custom_identity_match(followup, custom)
    assert matched is True
    assert key == "missing-person|michael-debevec"

    canonical, basis = g._published_skip_canonical(followup, [custom])
    assert canonical is custom
    assert basis == "durable_custom_incident_identity:missing-person|michael-debevec"


def test_custom_incident_match_returns_authoritative_archive_row_not_transient_copy():
    g = _load_generate_module()
    custom = _debevec_custom_canonical()
    followup = _debevec_actual_followup_source()
    match, confidence, basis = g._find_authoritative_custom_incident_match(
        followup, [custom], []
    )
    assert match is custom
    assert confidence == 100
    assert basis == "durable_custom_incident_identity:missing-person|michael-debevec"
    assert custom["durable_custom_identity_key"] == "missing-person|michael-debevec"


def test_two_sequential_debevec_escape_variants_both_redirect_to_original_custom(tmp_path: Path):
    g = _load_generate_module()
    articles = tmp_path / "articles"
    articles.mkdir()
    custom = _debevec_custom_canonical()

    first_escape = {
        **_debevec_later_publisher_source(),
        "slug": (
            "2026-08-30-martin-county-sheriffs-office-searches-for-missing-"
            "oklahoma-man-last-seen-at-hut"
        ),
        "headline": (
            "Martin County Sheriff's Office searches for missing Oklahoma man "
            "last seen at Hutchinson Island"
        ),
        "teaser": _debevec_later_publisher_source()["summary"],
        "date": "2026-08-30",
        "first_published": "Sun, 30 Aug 2026 13:30:00 -0400",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }
    second_escape = {
        **_debevec_actual_followup_source(),
        "slug": (
            "2026-08-30-martin-county-sheriffs-office-searches-for-oklahoma-"
            "visitor-last-seen-at-hutchin"
        ),
        "date": "2026-08-30",
        "first_published": "Sun, 30 Aug 2026 17:30:00 -0400",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
        "is_custom": False,
        "authoritative_custom": False,
    }

    cleaned, redirects = g.apply_canonical_story_cleanup(
        [custom, first_escape, second_escape], articles, tmp_path
    )
    assert [row["slug"] for row in cleaned] == [custom["slug"]]
    redirect_map = {row["source_slug"]: row["target_slug"] for row in redirects}
    assert redirect_map[first_escape["slug"]] == custom["slug"]
    assert redirect_map[second_escape["slug"]] == custom["slug"]



def test_missing_person_incident_anchor_is_publication_ledger_write_authority():
    g = _load_generate_module()
    custom = _debevec_custom_canonical()
    followup = _debevec_actual_followup_source()
    ledger = g._build_canonical_publication_ledger([custom])
    canonical, basis, keys = g._canonical_publication_ledger_target(
        followup, ledger
    )
    assert canonical is custom
    assert "incident:missing-person:michael-debevec" in keys
    assert basis == "exact_structured_incident_key"


def test_sanitize_persists_missing_person_custom_identity_key():
    g = _load_generate_module()
    custom = _debevec_custom_canonical()
    result = g._sanitize_authoritative_custom_archive([custom])
    assert result[0]["incident_anchor_key"] == "missing-person:michael-debevec"
    assert result[0]["durable_custom_identity_key"] == "missing-person|michael-debevec"



def test_named_missing_person_anchor_does_not_merge_different_people():
    michael = incident_anchor_key(
        titles=("Deputies search for missing Oklahoma man",),
        body="Michael Debevec visited Chastain Beach before he was reported missing.",
    )
    jordan = incident_anchor_key(
        titles=("Deputies search for missing Oklahoma man",),
        body="Jordan Smith visited Chastain Beach before he was reported missing.",
    )
    assert michael == "missing-person:michael-debevec"
    assert jordan == "missing-person:jordan-smith"
    assert michael != jordan


def test_validated_debevec_body_recovery_survives_immediate_published_story_guard(monkeypatch):
    """Regression: promotion must not be undone by the very next duplicate guard.

    Production on 2026-09-01 correctly validated the WPTV body-recovery source as a
    material update to the authoritative Debevec custom canonical, then immediately
    suppressed the same source as an already-published durable-custom duplicate.
    """
    g = _load_generate_module()
    canonical = _debevec_custom_canonical()
    canonical["incident_anchor_key"] = "missing-person:michael-debevec"
    canonical["durable_custom_identity_key"] = "missing-person|michael-debevec"
    body = (
        "A body discovered deep in the mangroves on Hutchinson Island is believed "
        "to belong to missing Oklahoma visitor Michael Anthony Debevec II. The "
        "Martin County Sheriff's Office said the body was found just north of the "
        "House of Refuge and the clothing matches surveillance video of Debevec. "
        "Investigators are awaiting positive identification. The Medical Examiner's "
        "Office is determining the cause of death."
    )
    source = {
        "title": "Martin County Sheriff's Office investigates body found in Hutchinson Island mangroves",
        "headline": "Martin County Sheriff's Office investigates body found in Hutchinson Island mangroves",
        "summary": body,
        "article_text": body + " " + body,
        "source_url": (
            "https://www.wptv.com/news/treasure-coast/region-martin-county/"
            "martin-county-sheriffs-office-investigates-body-found-in-hutchinson-island-mangroves"
        ),
        "link": (
            "https://www.wptv.com/news/treasure-coast/region-martin-county/"
            "martin-county-sheriffs-office-investigates-body-found-in-hutchinson-island-mangroves"
        ),
        "published": "Tue, 01 Sep 2026 20:02:41 GMT",
        "source_quality": "full",
        "source_type": "full_source",
        "editorial_story_id": "story_fragmented_body_recovery",
        "_editorial_story_id": "story_fragmented_body_recovery",
        "_editorial_route": "skip",
        "incident_anchor_key": "missing-person:michael-debevec",
    }

    canonical_slug = canonical["slug"]

    monkeypatch.setattr(
        g,
        "_run_known_canonical_materiality_gate",
        lambda *args, **kwargs: (
            {
                "status": "validated",
                "action": g.SEMANTIC_ACTION_UPDATE,
                "recommended_action": g.SEMANTIC_ACTION_UPDATE,
                "selected_candidate_slug": canonical_slug,
                "same_real_world_event": True,
                "material_new_update": True,
                "independently_newsworthy_followup": False,
                "confidence": 1.0,
                "shared_anchors": ["Michael Anthony Debevec II", "House of Refuge"],
                "novel_facts": ["Body recovered", "Awaiting positive identification"],
                "reason": "Body recovery is a major material update to the same missing-person case.",
                "validation_errors": [],
            },
            [{"slug": canonical_slug, "article": {}, "evidence": {}}],
            True,
            False,
        ),
    )

    headlines = [source]
    promotion = g._promote_published_skip_material_updates(
        headlines,
        [canonical],
        "martin",
        cache={"entries": {}},
    )

    assert promotion["promoted_count"] == 1
    assert source["_pre_generation_material_update_promotion"] is True
    assert source["_semantic_material_update"] is True
    assert source["_editorial_route"] == "update_existing"
    assert source["_pre_generation_material_update_canonical_slug"] == canonical_slug

    kept, suppressed = g._filter_published_skip_candidates(
        headlines, [canonical], "martin"
    )

    assert kept == [source]
    assert suppressed == []
    assert g._source_candidate_publishable(source) is True
