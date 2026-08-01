import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _load_generate_module():
    path = Path("scripts/generate.py")
    spec = importlib.util.spec_from_file_location("scripts.generate_front_page_priority_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _item(headline, when, urgency, *, body=None, archive_only=False, custom=False):
    article = {
        "headline": headline,
        "teaser": body or headline,
        "body": body or headline,
        "published_raw": when,
        "date": when,
        "urgency_score": urgency,
        "source_quality": "archive" if archive_only else "full",
        "enriched": True,
    }
    if archive_only:
        article["_archive_only"] = True
        article["_archive_verified_quality"] = True
        article["ranking_eligible"] = True
    if custom:
        article["is_custom"] = True
        article["authoritative_custom"] = True
        article["category"] = "st_lucie"
    return article


def _category(key, label, hero, cards=None):
    return {
        "category_key": key,
        "category_label": label,
        "hero": hero,
        "cards": list(cards or []),
    }


def test_fresh_custom_card_can_replace_stale_section_hero_and_archive_sports():
    generate = _load_generate_module()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    old = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")

    sports = _category(
        "sports",
        "Sports",
        _item(
            "Zayas Homers Twice as St. Lucie Mets Cruise Past Mighty Mussels",
            old,
            6,
            body="The Mets won a routine game three days ago at Clover Park.",
            archive_only=True,
        ),
    )
    stale_county_hero = _item(
        "Treasure Coast home prices rose earlier this week",
        old,
        6,
        body="Martin and St. Lucie County home prices were reported earlier this week.",
    )
    fresh_custom = _item(
        "Port St. Lucie Police Unveil New $28 Million Training Facility",
        today,
        6,
        body=(
            "Port St. Lucie police unveiled the new training facility today. "
            "The building includes an indoor range and simulation technology."
        ),
        custom=True,
    )
    st_lucie = _category(
        "st_lucie",
        "St. Lucie County",
        stale_county_hero,
        cards=[fresh_custom],
    )

    selected = generate.select_front_page_hero([sports, st_lucie])

    assert selected is st_lucie
    assert selected["hero"]["headline"] == fresh_custom["headline"]
    assert any(card["headline"] == stale_county_hero["headline"] for card in selected["cards"])
    assert generate.FRONT_PAGE_HERO_AUDIT["selection_reason"] == "only_fresh_candidate"
    assert generate.FRONT_PAGE_HERO_AUDIT["selected"]["archive_only"] is False


def test_no_fresh_candidates_uses_non_sports_deterministic_fallback():
    generate = _load_generate_module()
    old = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")

    sports = _category(
        "sports",
        "Sports",
        _item(
            "St. Lucie Mets win routine series game",
            old,
            6,
            body="The Mets won a routine baseball game three days ago at Clover Park.",
        ),
    )
    local_gov = _category(
        "local_gov",
        "Local Government",
        _item(
            "Port St. Lucie council approves infrastructure plan",
            old,
            4,
            body="Port St. Lucie council approved the infrastructure plan earlier this week.",
        ),
    )

    selected = generate.select_front_page_hero([sports, local_gov])

    assert selected is local_gov
    assert generate.FRONT_PAGE_HERO_AUDIT["selection_reason"] == "deterministic_stale_fallback"


def test_archive_only_sports_is_last_resort_when_archive_non_sports_exists():
    generate = _load_generate_module()
    old = (datetime.now(timezone.utc) - timedelta(days=4)).strftime("%Y-%m-%d")

    sports = _category(
        "sports",
        "Sports",
        _item(
            "St. Lucie Mets win old game",
            old,
            6,
            body="The Mets won an old game at Clover Park.",
            archive_only=True,
        ),
    )
    crime = _category(
        "crime",
        "Crime & Safety",
        _item(
            "Fort Pierce police investigation remains active",
            old,
            4,
            body="Fort Pierce police said the investigation remains active.",
            archive_only=True,
        ),
    )

    selected = generate.select_front_page_hero([sports, crime])

    assert selected is crime
    assert generate.FRONT_PAGE_HERO_AUDIT["selected"]["category_key"] == "crime"


def test_structural_fallback_still_blocks_sports_when_identity_is_unresolved():
    generate = _load_generate_module()
    old = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")

    sports_item = _item(
        "St. Lucie Mets win another old game",
        old,
        6,
        body="The Mets won a routine old game at Clover Park.",
        archive_only=True,
    )
    sports_item["ranking_eligible"] = False
    gov_item = _item(
        "Stuart commission discusses long-term budget",
        old,
        3,
        body="The Stuart commission discussed its long-term budget.",
        archive_only=True,
    )
    gov_item["ranking_eligible"] = False

    sports = _category("sports", "Sports", sports_item)
    local_gov = _category("local_gov", "Local Government", gov_item)

    selected = generate.select_front_page_hero([sports, local_gov])

    assert selected is local_gov
    assert generate.FRONT_PAGE_HERO_AUDIT["selection_reason"] == "structural_non_sports_fallback"


def test_active_queue_custom_is_fresh_even_if_recovery_marker_survives():
    generate = _load_generate_module()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    old = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")

    stale_housing = _category(
        "local_gov",
        "Local Government",
        _item(
            "Treasure Coast home prices rise after two years of decline",
            old,
            6,
            body="Housing prices were reported two days ago.",
        ),
    )
    active_custom = _item(
        "Port St. Lucie Police Unveil New $28 Million Training Facility",
        today,
        2,
        body="Port St. Lucie police unveiled the new training facility today.",
        archive_only=True,
        custom=True,
    )
    active_custom["_custom_active_queue"] = True
    st_lucie = _category("st_lucie", "St. Lucie County", active_custom)

    selected = generate.select_front_page_hero([stale_housing, st_lucie])

    assert selected is st_lucie
    assert generate.FRONT_PAGE_HERO_AUDIT["selection_reason"] == "only_fresh_candidate"
    assert generate.FRONT_PAGE_HERO_AUDIT["selected"]["archive_only"] is False
    assert generate.FRONT_PAGE_HERO_AUDIT["selected"]["active_custom_queue"] is True


def test_fresh_archive_recovery_beats_stale_live_candidate_after_canonical_binding():
    generate = _load_generate_module()
    now = datetime.now(timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    old = (now - timedelta(days=4)).strftime("%a, %d %b %Y %H:%M:%S GMT")

    stale_live = _category(
        "local_gov",
        "Local Government",
        _item(
            "Martin County commission reviews an older budget item",
            old,
            7,
            body="Martin County commissioners reviewed the budget item earlier this week.",
        ),
    )
    fresh_archive_item = _item(
        "Fort Pierce police announce new public-safety development",
        fresh,
        6,
        body="Fort Pierce police announced the new development today.",
        archive_only=True,
    )
    fresh_archive_item.update({
        "_canonical_freshness_bound": True,
        "canonical_slug": "fresh-fort-pierce-public-safety-development",
        "_archived_slug": "fresh-fort-pierce-public-safety-development",
        "first_published": fresh,
    })
    fresh_archive = _category("crime", "Crime & Safety", fresh_archive_item)

    selected = generate.select_front_page_hero(
        [stale_live, fresh_archive], deterministic_only=True
    )

    assert selected is fresh_archive
    assert selected["hero"]["headline"] == fresh_archive_item["headline"]
    assert (
        generate.FRONT_PAGE_HERO_AUDIT["selection_reason"]
        == "deterministic_post_canonical_archive_recovery"
    )
    assert generate.FRONT_PAGE_HERO_AUDIT["selected"]["archive_only"] is True
