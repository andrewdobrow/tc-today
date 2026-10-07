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


def _custom_canonical(g):
    return {
        "slug": g.HOARDING_CANONICAL_SLUG,
        "headline": "More Than 70 Animals Found in Stuart Home During Large-Scale Hoarding Response",
        "teaser": "Authorities rescued dozens of cats and dogs from a Stuart home.",
        "is_custom": True,
        "authoritative_custom": True,
        "editorial_story_id": "custom:hoarding",
    }


def _friday_feed_update():
    return {
        "headline": "100 animals rescued in worst hoarding case Martin County has seen, owners search for missing pets",
        "teaser": "The total reached 100 after 83 cats and 17 dogs were rescued.",
        "body": "On Monday authorities removed 80 cats and 12 dogs. More animals were later rescued.",
        "source_url": "https://www.wptv.com/news/treasure-coast/region-martin-county/more-animals-rescued-in-martin-county-hoarding-case-as-owners-search-for-missing-pets",
        "enriched": True,
    }


def test_known_event_key_accepts_later_100_animal_count():
    g = _load_generate()
    assert g._known_event_key("100 animals rescued in Martin County's worst hoarding case") == (
        "2026-07-stuart-martin-animal-hoarding"
    )


def test_live_custom_incident_lock_removes_cross_category_copies():
    g = _load_generate()
    custom = _custom_canonical(g)
    crime_copy = _friday_feed_update()
    martin_copy = dict(crime_copy)
    categories = [
        {"category_key": "crime", "hero": crime_copy, "cards": [{"headline": "Other crime story"}]},
        {"category_key": "martin", "hero": {"headline": "Other Martin story"}, "cards": [martin_copy]},
    ]
    removed = g.suppress_authoritative_custom_incidents_from_live(
        categories, archived_customs=[custom], current_customs=[]
    )
    assert len(removed) == 2
    assert categories[0]["hero"]["headline"] == "Other crime story"
    assert categories[1]["cards"] == []
    assert all(row["canonical_slug"] == g.HOARDING_CANONICAL_SLUG for row in removed)


def test_publication_lock_finds_authoritative_custom_independent_of_stage():
    g = _load_generate()
    custom = _custom_canonical(g)
    match, confidence, basis = g._find_authoritative_custom_incident_match(
        _friday_feed_update(), archived_customs=[custom], current_customs=[]
    )
    assert match["slug"] == g.HOARDING_CANONICAL_SLUG
    assert confidence == 100
    assert basis == "exact_known_event_key"


def test_same_run_canonical_cleanup_redirects_july_25_duplicate(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    (tmp_path / "data").mkdir()
    duplicate_slug = (
        "2026-07-25-100-animals-rescued-in-worst-hoarding-case-"
        "martin-county-has-seen-owners-search"
    )
    archive = [
        _custom_canonical(g),
        {
            "slug": duplicate_slug,
            **_friday_feed_update(),
            "editorial_story_id": "story-generated-follow-up",
        },
    ]
    cleaned, redirects = g.apply_canonical_story_cleanup(archive, articles, tmp_path)
    assert [row["slug"] for row in cleaned] == [g.HOARDING_CANONICAL_SLUG]
    redirect = next(row for row in redirects if row["source_slug"] == duplicate_slug)
    assert redirect["target_slug"] == g.HOARDING_CANONICAL_SLUG
    assert redirect["canonical_is_custom"] is True


def test_unrelated_animal_story_survives_custom_incident_lock():
    g = _load_generate()
    custom = _custom_canonical(g)
    categories = [{
        "category_key": "crime",
        "hero": {
            "headline": "Three dogs rescued after being abandoned near I-95 in Martin County",
            "body": "The animals were found beside Bridge Road.",
        },
        "cards": [],
    }]
    removed = g.suppress_authoritative_custom_incidents_from_live(
        categories, archived_customs=[custom], current_customs=[]
    )
    assert removed == []
    assert categories[0]["hero"] is not None


def _debevec_custom_canonical(g):
    return {
        "slug": "2026-08-29-martin-county-sheriffs-office-searches-for-missing-oklahoma-visitor-last-seen-at-chastain-beach",
        "headline": "Martin County Sheriff's Office searches for missing Oklahoma visitor last seen at Chastain Beach",
        "teaser": "Deputies are searching for Michael Anthony Debevec II after he was last seen at Chastain Beach.",
        "body": "Michael Anthony Debevec II was reported missing after visiting Chastain Beach in Martin County.",
        "category_key": "martin",
        "category_keys": ["martin", "crime"],
        "county_keys": ["martin"],
        "date": "2026-08-29",
        "first_published": "Sat, 29 Aug 2026 21:48:09 -0400",
        "is_custom": True,
        "authoritative_custom": True,
        "incident_anchor_key": "missing-person:michael-debevec",
        "durable_custom_identity_key": "missing-person|michael-debevec",
        "editorial_story_id": "custom:debevec",
    }


def _validated_debevec_generated_update(g, canonical, headline):
    decision = {
        "status": "validated",
        "action": g.SEMANTIC_ACTION_UPDATE,
        "recommended_action": g.SEMANTIC_ACTION_UPDATE,
        "selected_candidate_slug": canonical["slug"],
        "same_real_world_event": True,
        "material_new_update": True,
        "confidence": 0.99,
        "shared_anchors": ["Michael Anthony Debevec II", "Chastain Beach"],
        "novel_facts": ["A body believed to be Debevec was recovered near the House of Refuge"],
        "reason": "The body recovery is a major development in the existing missing-person case.",
        "validation_errors": [],
    }
    item = {
        "headline": headline,
        "source_headline": "Martin County Sheriff's Office investigates body found in Hutchinson Island mangroves",
        "source_url": "https://www.wptv.com/news/treasure-coast/region-martin-county/martin-county-sheriffs-office-investigates-body-found-in-hutchinson-island-mangroves",
        "body": (
            "A body was recovered in mangroves near the House of Refuge during the search for "
            "Michael Anthony Debevec II. Investigators said the clothing matched what Debevec "
            "was believed to be wearing, while formal identification remained pending."
        ),
        "editorial_story_id": canonical["editorial_story_id"],
        "_editorial_story_id": canonical["editorial_story_id"],
        "_editorial_route": "update_existing",
        "editorial_route": "update_existing",
        "story_form": "update",
        "_semantic_material_update": True,
        "_semantic_material_update_decision": decision,
        "_pre_generation_material_update_promotion": True,
        "_pre_generation_material_update_canonical_slug": canonical["slug"],
        "canonical_slug": canonical["slug"],
        "_protected_material_update": True,
    }
    g._stamp_canonical_write_authorization(
        item,
        canonical,
        {
            "outcome": g.IDENTITY_OUTCOME_VERIFIED,
            "identity_outcome": g.IDENTITY_OUTCOME_VERIFIED,
            "evidence_tier": "known_canonical_plus_semantic_materiality",
            "write_authorized": True,
            "proof_type": "published_skip_canonical_plus_semantic_materiality",
            "reason": "Major body-recovery development.",
            "reason_codes": ["semantic_material_update_validated"],
        },
        basis="pre_generation_material_update_promotion",
    )
    return item


def test_authoritative_custom_incident_lock_preserves_target_bound_debevec_material_update():
    """2026-09-01 regression: custom lock must not erase a pending canonical update transaction."""
    g = _load_generate()
    canonical = _debevec_custom_canonical(g)
    crime = _validated_debevec_generated_update(
        g, canonical,
        "Body found in Hutchinson Island mangroves believed to be missing Port St. Lucie man",
    )
    martin = _validated_debevec_generated_update(
        g, canonical,
        "Martin County Sheriff's Office finds body believed to be missing Michael Debevec",
    )
    categories = [
        {"category_key": "crime", "hero": crime, "cards": []},
        {"category_key": "martin", "hero": martin, "cards": []},
    ]

    removed = g.suppress_authoritative_custom_incidents_from_live(
        categories, archived_customs=[canonical], current_customs=[]
    )

    assert removed == []
    assert categories[0]["hero"] is crime
    assert categories[1]["hero"] is martin
    assert g._has_target_bound_pre_generation_material_update_authority(crime, canonical)
    assert g._has_target_bound_pre_generation_material_update_authority(martin, canonical)


def test_authoritative_custom_incident_lock_still_removes_unapproved_debevec_reprint():
    g = _load_generate()
    canonical = _debevec_custom_canonical(g)
    ordinary = {
        "headline": "Body found in Hutchinson Island mangroves believed to be missing Michael Debevec",
        "body": "Deputies found a body during the search for Michael Anthony Debevec II near Chastain Beach.",
        "source_url": "https://example.com/unapproved-reprint",
        "incident_anchor_key": "missing-person:michael-debevec",
    }
    categories = [{"category_key": "martin", "hero": ordinary, "cards": []}]

    removed = g.suppress_authoritative_custom_incidents_from_live(
        categories, archived_customs=[canonical], current_customs=[]
    )

    assert len(removed) == 1
    assert categories[0]["hero"] is None


def _florida_driver_license_custom():
    return {
        "slug": "2026-09-29-florida-begins-issuing-redesigned-driver-licenses-id-cards",
        "headline": "Florida to begin issuing redesigned driver licenses and ID cards",
        "teaser": (
            "Florida will begin issuing newly redesigned driver licenses and identification "
            "cards Sept. 30, featuring updated security elements and imagery tied to the state's history."
        ),
        "body": (
            "Florida will begin issuing newly redesigned driver licenses and identification cards "
            "on Sept. 30 at service centers statewide. The new credentials include updated security "
            "features and new imagery."
        ),
        "category_key": "florida",
        "date": "2026-09-29",
        "first_published": "Tue, 29 Sep 2026 14:26:16 -0400",
        "is_custom": True,
        "authoritative_custom": True,
        "custom_id": "2026-09-29-florida-new-driver-license-design",
        "custom_publication_key": "id:2026-09-29-florida-new-driver-license-design",
        "editorial_story_id": "custom:florida-driver-license-redesign",
    }


def _florida_driver_license_rollout_reprint():
    return {
        "headline": "Florida rolls out redesigned driver's licenses with new imagery at service center",
        "source_headline": "Florida rolls out redesigned driver's licenses with new imagery at service center",
        "teaser": (
            "Florida began issuing redesigned driver licenses and identification cards at service "
            "centers statewide with updated security elements and imagery."
        ),
        "body": (
            "The newly redesigned Florida driver licenses and identification cards are now being "
            "issued at service centers statewide. The credentials feature updated security elements "
            "and new imagery."
        ),
        "source_url": "https://example.com/florida-redesigned-driver-license-rollout",
        "category_key": "florida",
        "published": "Wed, 30 Sep 2026 09:00:00 -0400",
    }


def test_near_term_custom_subject_contract_routes_driver_license_rollout_to_custom_canonical():
    """Sept. 30 regression: next-day rollout wording must not mint a second DMV URL."""
    g = _load_generate()
    custom = _florida_driver_license_custom()
    incoming = _florida_driver_license_rollout_reprint()

    matched, confidence, basis = g._find_authoritative_custom_incident_match(
        incoming, archived_customs=[custom], current_customs=[]
    )

    assert matched is custom
    assert confidence == 100
    assert basis.startswith("durable_custom_incident_identity:near-term-custom-subject|")


def test_near_term_custom_subject_contract_suppresses_parallel_driver_license_placement():
    g = _load_generate()
    custom = _florida_driver_license_custom()
    incoming = _florida_driver_license_rollout_reprint()
    categories = [{"category_key": "florida", "hero": incoming, "cards": []}]

    removed = g.suppress_authoritative_custom_incidents_from_live(
        categories, archived_customs=[custom], current_customs=[]
    )

    assert len(removed) == 1
    assert categories[0]["hero"] is None
    assert removed[0]["canonical_slug"] == custom["slug"]


def test_near_term_custom_subject_contract_does_not_merge_unrelated_dmv_story():
    g = _load_generate()
    custom = _florida_driver_license_custom()
    unrelated = {
        "headline": "Florida DMV warns residents about phishing messages targeting driver records",
        "teaser": "Officials warned motorists about fraudulent messages seeking personal information.",
        "body": "The warning concerns phishing messages and does not involve the redesigned credential rollout.",
        "source_url": "https://example.com/florida-dmv-phishing-warning",
        "category_key": "florida",
        "published": "Wed, 30 Sep 2026 10:00:00 -0400",
    }

    matched, confidence, basis = g._find_authoritative_custom_incident_match(
        unrelated, archived_customs=[custom], current_customs=[]
    )

    assert matched is None
    assert confidence == 0
    assert basis == ""


def test_canonical_cleanup_repairs_already_published_driver_license_duplicate(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    (tmp_path / "data").mkdir()
    custom = _florida_driver_license_custom()
    duplicate = {
        **_florida_driver_license_rollout_reprint(),
        "slug": "2026-09-30-florida-rolls-out-redesigned-drivers-licenses-with-new-imagery-at-service-center",
        "date": "2026-09-30",
        "lastmod": "2026-09-30",
        "first_published": "Wed, 30 Sep 2026 12:00:00 -0400",
        "article_word_count": 280,
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }
    (articles / f"{custom['slug']}.html").write_text("custom", encoding="utf-8")
    (articles / f"{duplicate['slug']}.html").write_text("duplicate", encoding="utf-8")

    cleaned, redirects = g.apply_canonical_story_cleanup(
        [custom, duplicate], articles, tmp_path
    )

    assert [row["slug"] for row in cleaned] == [custom["slug"]]
    redirect = next(row for row in redirects if row["source_slug"] == duplicate["slug"])
    assert redirect["target_slug"] == custom["slug"]
    assert redirect["canonical_is_custom"] is True
    rendered = (articles / f"{duplicate['slug']}.html").read_text(encoding="utf-8")
    assert custom["slug"] in rendered


def test_known_driver_license_duplicate_slug_is_permanent_redirect_even_with_sparse_metadata(tmp_path):
    """Repair the already-public Sept. 30 DMV URL even if its archive evidence degrades."""
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    (tmp_path / "data").mkdir()
    custom = _florida_driver_license_custom()
    duplicate = {
        "slug": next(iter(g.FLORIDA_DRIVER_LICENSE_REDIRECT_SOURCE_SLUGS)),
        "headline": "Florida rolls out redesigned driver's licenses with new imagery at service centers statewide",
        "date": "2026-09-30",
        "lastmod": "2026-09-30",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
        # Deliberately omit body/teaser/source facts. The prevention matcher may no
        # longer have enough evidence, but the known escaped public URL still must
        # remain permanently bound to the verified custom canonical.
    }
    (articles / f"{custom['slug']}.html").write_text("custom", encoding="utf-8")
    (articles / f"{duplicate['slug']}.html").write_text("duplicate", encoding="utf-8")

    cleaned, redirects = g.apply_canonical_story_cleanup(
        [custom, duplicate], articles, tmp_path
    )

    assert [row["slug"] for row in cleaned] == [custom["slug"]]
    redirect = next(row for row in redirects if row["source_slug"] == duplicate["slug"])
    assert redirect["target_slug"] == g.FLORIDA_DRIVER_LICENSE_CANONICAL_SLUG
    assert redirect["canonical_is_custom"] is True
    rendered = (articles / f"{duplicate['slug']}.html").read_text(encoding="utf-8")
    assert g.FLORIDA_DRIVER_LICENSE_CANONICAL_SLUG in rendered


def _st_lucie_polling_change_custom():
    return {
        "slug": (
            "2026-10-05-st-lucie-county-changes-polling-location-for-"
            "precincts-39-and-52-for-nov-3-election"
        ),
        "headline": (
            "St. Lucie County changes polling location for Precincts 39 and 52 "
            "for Nov. 3 election"
        ),
        "teaser": (
            "Voters in Precincts 39 and 52 will cast Election Day ballots at Lakewood "
            "Park Church instead of Spanish Lakes Country Club because of clubhouse renovations."
        ),
        "body": (
            "Voters in St. Lucie County Precincts 39 and 52 will have a temporary polling "
            "place for the Nov. 3 general election because of renovations at their usual "
            "Election Day location. The two precincts will move from the Spanish Lakes "
            "Country Club clubhouse to Lakewood Park Church, 5405 Turnpike Feeder Road in "
            "Fort Pierce. The change applies to the Nov. 3, 2026 General Election."
        ),
        "category_key": "local_gov",
        "date": "2026-10-05",
        "first_published": "Mon, 05 Oct 2026 18:50:00 -0400",
        "is_custom": True,
        "authoritative_custom": True,
        "custom_id": "st-lucie-precincts-39-52-polling-place-change-2026-11-03",
    }


def _st_lucie_polling_change_reprint():
    return {
        "slug": (
            "2026-10-07-st-lucie-precincts-39-52-move-to-lakewood-park-church-"
            "for-nov-3-vote"
        ),
        "headline": (
            "St. Lucie Precincts 39, 52 Move to Lakewood Park Church for Nov. 3 Vote"
        ),
        "teaser": (
            "Voters in St. Lucie County's Precincts 39 and 52 will use a temporary polling "
            "place for the Nov. 3 general election because of renovations at their regular site."
        ),
        "body": (
            "Supervisor of Elections Gertrude Walker announced Tuesday that voters in both "
            "precincts will move from the Spanish Lakes Country Club clubhouse to Lakewood "
            "Park Church, 5405 Turnpike Feeder Road in Fort Pierce."
        ),
        "category_key": "st_lucie",
        "date": "2026-10-07",
        "first_published": "Wed, 07 Oct 2026 08:46:00 -0400",
        "source_url": (
            "https://cbs12.com/news/local/st-lucie-county-voting-precincts-36-52-"
            "moved-temporary-polling-places-november-3-election-supervisor-of-elections-"
            "gertrude-walker-florida-news"
        ),
    }


def test_polling_place_identity_matches_reworded_publisher_copy():
    g = _load_generate()
    custom = _st_lucie_polling_change_custom()
    incoming = _st_lucie_polling_change_reprint()

    expected = "polling-place-change|st-lucie|2026-11-03|precincts-39-52"
    assert g._polling_place_change_identity(custom) == expected
    assert g._polling_place_change_identity(incoming) == expected

    matched, confidence, basis = g._find_authoritative_custom_incident_match(
        incoming, archived_customs=[custom], current_customs=[]
    )
    assert matched is custom
    assert confidence == 100
    assert basis == f"durable_custom_incident_identity:{expected}"


def test_polling_place_custom_lock_suppresses_parallel_generated_placement():
    g = _load_generate()
    custom = _st_lucie_polling_change_custom()
    incoming = _st_lucie_polling_change_reprint()
    categories = [{"category_key": "st_lucie", "hero": incoming, "cards": []}]

    removed = g.suppress_authoritative_custom_incidents_from_live(
        categories, archived_customs=[custom], current_customs=[]
    )

    assert len(removed) == 1
    assert categories[0]["hero"] is None
    assert removed[0]["canonical_slug"] == custom["slug"]
    assert removed[0]["confidence"] == 100


def test_polling_place_identity_does_not_merge_different_election_or_precincts():
    g = _load_generate()
    custom = _st_lucie_polling_change_custom()

    different_election = dict(_st_lucie_polling_change_reprint())
    different_election["headline"] = (
        "St. Lucie Precincts 39, 52 Move to Lakewood Park Church for Aug. 18 Vote"
    )
    different_election["teaser"] = (
        "Voters in St. Lucie County Precincts 39 and 52 will use a temporary polling place "
        "for the Aug. 18 primary election."
    )
    different_election["body"] = ""

    different_precincts = dict(_st_lucie_polling_change_reprint())
    different_precincts["headline"] = (
        "St. Lucie Precincts 2 and 7 Move to Lakewood Park Church for Nov. 3 Vote"
    )
    different_precincts["teaser"] = (
        "Voters in St. Lucie County Precincts 2 and 7 will use a temporary polling place "
        "for the Nov. 3 general election."
    )
    different_precincts["body"] = ""

    custom_key = g._polling_place_change_identity(custom)
    assert g._polling_place_change_identity(different_election) != custom_key
    assert g._polling_place_change_identity(different_precincts) != custom_key

    assert g._find_authoritative_custom_incident_match(
        different_election, archived_customs=[custom], current_customs=[]
    )[0] is None
    assert g._find_authoritative_custom_incident_match(
        different_precincts, archived_customs=[custom], current_customs=[]
    )[0] is None


def test_canonical_cleanup_repairs_oct_7_polling_place_duplicate(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    (tmp_path / "data").mkdir()
    custom = _st_lucie_polling_change_custom()
    duplicate = _st_lucie_polling_change_reprint()
    duplicate.update({
        "lastmod": "2026-10-07",
        "article_word_count": 350,
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    })
    (articles / f"{custom['slug']}.html").write_text("custom", encoding="utf-8")
    (articles / f"{duplicate['slug']}.html").write_text("duplicate", encoding="utf-8")

    cleaned, redirects = g.apply_canonical_story_cleanup(
        [custom, duplicate], articles, tmp_path
    )

    assert [row["slug"] for row in cleaned] == [custom["slug"]]
    redirect = next(row for row in redirects if row["source_slug"] == duplicate["slug"])
    assert redirect["target_slug"] == custom["slug"]
    assert redirect["canonical_is_custom"] is True
    rendered = (articles / f"{duplicate['slug']}.html").read_text(encoding="utf-8")
    assert custom["slug"] in rendered


def test_known_polling_place_duplicate_slug_is_permanent_redirect_with_sparse_metadata(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    (tmp_path / "data").mkdir()
    custom = _st_lucie_polling_change_custom()
    duplicate_slug = next(iter(g.ST_LUCIE_POLLING_CHANGE_REDIRECT_SOURCE_SLUGS))
    duplicate = {
        "slug": duplicate_slug,
        "headline": "St. Lucie polling place update",
        "date": "2026-10-07",
        "lastmod": "2026-10-07",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }
    (articles / f"{custom['slug']}.html").write_text("custom", encoding="utf-8")
    (articles / f"{duplicate_slug}.html").write_text("duplicate", encoding="utf-8")

    cleaned, redirects = g.apply_canonical_story_cleanup(
        [custom, duplicate], articles, tmp_path
    )

    assert [row["slug"] for row in cleaned] == [custom["slug"]]
    redirect = next(row for row in redirects if row["source_slug"] == duplicate_slug)
    assert redirect["target_slug"] == g.ST_LUCIE_POLLING_CHANGE_CANONICAL_SLUG
    assert redirect["canonical_is_custom"] is True
    rendered = (articles / f"{duplicate_slug}.html").read_text(encoding="utf-8")
    assert g.ST_LUCIE_POLLING_CHANGE_CANONICAL_SLUG in rendered
