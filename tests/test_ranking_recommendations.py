from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from tct_engine import (
    RANKING_MODE,
    build_homepage_ranking_recommendations,
    write_homepage_ranking_recommendations,
)


def _registry():
    return {
        "stories": {
            "story_low": {
                "story_id": "story_low",
                "canonical_title": "Community festival announced",
                "editorial_score": 25,
                "score_breakdown": {"score": 25, "importance": 30},
                "timeline": [{"title": "Community festival announced", "url": "https://source.test/festival"}],
            },
            "story_high": {
                "story_id": "story_high",
                "canonical_title": "County issues evacuation order",
                "editorial_score": 95,
                "score_breakdown": {"score": 95, "importance": 100},
                "timeline": [{"title": "County issues evacuation order", "url": "https://source.test/evacuation"}],
                "article_slugs": ["evacuation-story"],
            },
        }
    }


def _cards():
    now = datetime.now(timezone.utc).isoformat()
    return [
        {"headline": "Community festival announced", "link": "https://source.test/festival", "cat_key": "things_to_do", "published_raw": now, "urgency_score": 3},
        {"headline": "County issues evacuation order", "link": "https://source.test/evacuation", "cat_key": "crime", "published_raw": now, "urgency_score": 9},
    ]


def test_recommendations_do_not_mutate_live_order_or_hero():
    cards = _cards()
    hero = {"headline": "Existing live hero"}
    before_cards = deepcopy(cards)
    before_hero = deepcopy(hero)

    report = build_homepage_ranking_recommendations(cards, hero, registry=_registry())

    assert cards == before_cards
    assert hero == before_hero
    assert report["mode"] == RANKING_MODE == "recommend"
    assert report["publication_behavior_changed"] is False
    assert report["hero"]["changed"] is False
    assert report["current_order"] == ["Community festival announced", "County issues evacuation order"]
    assert report["recommended_order"] == ["County issues evacuation order", "Community festival announced"]


def test_pinned_custom_position_is_preserved():
    cards = _cards()
    cards[0]["pin_position"] = 1
    cards[0]["is_custom"] = True
    report = build_homepage_ranking_recommendations(cards, {}, registry=_registry())
    assert report["recommended_order"][0] == "Community festival announced"
    assert all(move["headline"] != "Community festival announced" for move in report["recommendations"])


def test_writer_persists_observe_only_report(tmp_path: Path):
    registry_path = tmp_path / "registry.json"
    output_path = tmp_path / "data" / "homepage-ranking-recommendations.json"
    registry_path.write_text(json.dumps(_registry()), encoding="utf-8")

    report = write_homepage_ranking_recommendations(
        _cards(),
        {"headline": "Existing live hero"},
        registry_path=registry_path,
        archive=[],
        output_path=output_path,
    )

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved == report
    assert saved["controls"]["card_reordering_enabled"] is False
    assert saved["summary"]["registry_matches"] == 2


def test_unmatched_card_uses_explainable_fallback_without_enforcement():
    report = build_homepage_ranking_recommendations(
        [{"headline": "Unmatched local story", "urgency_score": 7}],
        {},
        registry={"stories": {}},
    )
    item = report["items"][0]
    assert item["score"] == 36
    assert item["score_breakdown"]["basis"] == "homepage_editorial_shadow_v2"
    assert item["score_breakdown"]["urgency"] == 7
    assert report["summary"]["fallback_scores"] == 1


def test_cross_category_placements_are_ranked_once_by_persistent_story():
    registry = _registry()
    cards = [
        {"headline": "County issues evacuation order", "link": "https://source.test/evacuation", "cat_key": "crime"},
        {"headline": "County issues evacuation order", "link": "https://source.test/evacuation?utm_source=rss", "cat_key": "st_lucie"},
        {"headline": "Community festival announced", "link": "https://source.test/festival", "cat_key": "things_to_do"},
    ]
    report = build_homepage_ranking_recommendations(cards, {}, registry=registry)
    assert report["summary"]["input_placements"] == 3
    assert report["summary"]["unique_cards_observed"] == 2
    assert report["summary"]["duplicate_placements_excluded"] == 1
    assert report["current_order"].count("County issues evacuation order") == 1


def test_archive_story_id_matches_before_fallback():
    registry = _registry()
    cards = [{"headline": "Rewritten evacuation headline", "_archived_slug": "evacuation-story", "urgency_score": 1}]
    archive = [{
        "slug": "evacuation-story",
        "headline": "Rewritten evacuation headline",
        "editorial_story_id": "story_high",
    }]
    report = build_homepage_ranking_recommendations(cards, {}, registry=registry, archive=archive)
    item = report["items"][0]
    assert item["story_id"] == "story_high"
    assert item["match_basis"] == "persistent_story_id+canonical_slug"
    assert item["score_breakdown"]["basis"] == "homepage_editorial_shadow_v2"
    assert item["score_breakdown"]["importance"] == 100


def test_custom_article_competes_normally_unless_manually_pinned():
    now = datetime.now(timezone.utc).isoformat()
    cards = [
        {"headline": "Generated low story", "urgency_score": 1, "published_raw": now},
        {"headline": "Manual traffic report", "is_custom": True, "slug": "manual-traffic", "urgency_score": 8, "published_raw": now},
        {"headline": "Generated high story", "urgency_score": 10, "published_raw": now},
    ]
    report = build_homepage_ranking_recommendations(cards, {}, registry={"stories": {}})
    manual = next(item for item in report["items"] if item["headline"] == "Manual traffic report")
    assert manual["current_position"] == 2
    assert manual["position_locked"] is False
    assert manual["position_lock_reason"] == ""
    assert report["controls"]["custom_articles_compete_normally"] is True

    cards[1]["pin_position"] = 2
    pinned = build_homepage_ranking_recommendations(cards, {}, registry={"stories": {}})
    manual_pinned = next(item for item in pinned["items"] if item["headline"] == "Manual traffic report")
    assert manual_pinned["position_locked"] is True
    assert manual_pinned["position_lock_reason"] == "pin_position"


def test_report_exposes_editorial_deck_and_registry_match_rate():
    report = build_homepage_ranking_recommendations(_cards(), {}, registry=_registry(), current_deck_count=2)
    assert report["summary"]["recommended_deck_count"] == 2
    assert report["recommended_deck"][0] == "County issues evacuation order"
    assert report["summary"]["registry_match_rate"] == 1.0


def test_low_registry_match_rate_is_explicitly_not_ready_for_enforcement():
    cards = [
        {"headline": "County issues evacuation order", "story_id": "story_high", "link": "https://source.test/evacuation"},
        {"headline": "Unmatched one", "urgency_score": 5},
        {"headline": "Unmatched two", "urgency_score": 4},
    ]
    report = build_homepage_ranking_recommendations(cards, {}, registry=_registry())
    assert report["summary"]["enforcement_readiness"] == "not_ready"
    assert "Fewer than 80%" in report["summary"]["enforcement_readiness_reason"]


def test_recent_high_urgency_exclusion_blocks_enforcement_readiness():
    report = build_homepage_ranking_recommendations(
        _cards(),
        {},
        registry=_registry(),
        excluded_candidates=[{
            "headline": "3 arrested in death of 3-month-old",
            "category_key": "st_lucie",
            "urgency_score": 9,
            "stale": True,
            "reason": "past_day_reference:thursday",
            "date_value": "2026-07-25",
            "age_hours": 2.0,
        }],
    )
    assert report["summary"]["recent_high_urgency_exclusions"] == 1
    assert report["summary"]["enforcement_readiness"] == "not_ready"
    assert "Recent high-urgency" in report["summary"]["enforcement_readiness_reason"]
    assert report["excluded_candidates"][0]["headline"].startswith("3 arrested")


def test_unresolved_legacy_archive_card_is_excluded_from_ranking():
    cards = [{
        "headline": "Legacy archive story",
        "_archived_slug": "legacy-story",
        "_archive_only": True,
        "legacy_identity_status": "legacy_unresolved",
        "ranking_eligible": False,
        "urgency_score": 10,
    }]
    archive = [{
        "slug": "legacy-story",
        "headline": "Legacy archive story",
        "legacy_identity_status": "legacy_unresolved",
        "ranking_eligible": False,
    }]
    report = build_homepage_ranking_recommendations(
        cards, {}, registry={"stories": {}}, archive=archive
    )
    assert report["summary"]["legacy_identity_placements_excluded"] == 1
    assert report["summary"]["unique_cards_observed"] == 0
    assert report["items"] == []
    assert report["excluded_legacy_identity_placements"][0]["slug"] == "legacy-story"


def test_uncorroborated_explicit_story_id_is_locked_and_blocks_enforcement():
    registry = _registry()
    cards = [{
        "headline": "Martin and St. Lucie counties report five confirmed cases of cyclosporiasis",
        "story_id": "story_low",
        "urgency_score": 7,
        "cat_key": "local_gov",
    }]

    report = build_homepage_ranking_recommendations(cards, {}, registry=registry)

    item = report["items"][0]
    assert item["story_id"] == ""
    assert item["match_basis"] == "uncorroborated_persistent_story_id"
    assert item["identity_confidence"] == "low"
    assert item["position_locked"] is True
    assert item["position_lock_reason"] == "identity_conflict"
    assert report["summary"]["identity_warning_count"] == 1
    assert report["summary"]["enforcement_readiness"] == "not_ready"
    assert "identity conflict" in report["summary"]["enforcement_readiness_reason"].lower()


def test_exact_title_fallback_corrects_conflicting_explicit_story_id_but_locks_move():
    registry = _registry()
    registry["stories"]["story_health"] = {
        "story_id": "story_health",
        "canonical_title": "Martin and St. Lucie counties report five confirmed cases of cyclosporiasis",
        "editorial_score": 70,
        "score_breakdown": {"score": 70, "importance": 70},
        "timeline": [],
    }
    cards = [{
        "headline": "Martin and St. Lucie counties report five confirmed cases of cyclosporiasis",
        "story_id": "story_low",
        "urgency_score": 7,
        "cat_key": "local_gov",
    }]

    report = build_homepage_ranking_recommendations(cards, {}, registry=registry)

    item = report["items"][0]
    assert item["story_id"] == "story_health"
    assert item["match_basis"] == "title"
    assert item["identity_confidence"] == "high"
    assert "persistent_story_id_conflicts_with_title" in item["identity_warning"]
    assert item["position_locked"] is True
    assert report["summary"]["identity_warning_count"] == 1
    assert report["summary"]["enforcement_readiness"] == "not_ready"


def test_corroborated_story_id_remains_high_confidence_and_movable():
    cards = [{
        "headline": "County issues evacuation order",
        "story_id": "story_high",
        "link": "https://source.test/evacuation?utm_source=rss",
        "cat_key": "crime",
    }]

    report = build_homepage_ranking_recommendations(cards, {}, registry=_registry())

    item = report["items"][0]
    assert item["story_id"] == "story_high"
    assert item["identity_confidence"] == "high"
    assert "source_url" in item["identity_evidence"]
    assert item["identity_warning"] == ""
    assert item["position_locked"] is False
    assert report["summary"]["identity_warning_count"] == 0


def test_strong_title_overlap_is_medium_confidence_and_stays_observe_only():
    registry = {
        "stories": {
            "story_evac": {
                "story_id": "story_evac",
                "canonical_title": "St. Lucie County issues mandatory evacuation order for coastal residents",
                "editorial_score": 90,
                "score_breakdown": {"score": 90, "importance": 95},
                "timeline": [],
            }
        }
    }
    cards = [{
        "headline": "Mandatory evacuation order issued for St. Lucie County coastal residents",
        "story_id": "story_evac",
        "cat_key": "st_lucie",
    }]

    report = build_homepage_ranking_recommendations(cards, {}, registry=registry)

    item = report["items"][0]
    assert item["story_id"] == "story_evac"
    assert item["identity_confidence"] == "medium"
    assert item["position_locked"] is True
    assert item["position_lock_reason"] == "medium_identity_confidence"
    assert report["summary"]["identity_warning_count"] == 1
    assert report["summary"]["enforcement_readiness"] == "not_ready"


def test_stale_high_registry_score_cannot_be_promoted_back_into_deck():
    reference = datetime(2026, 8, 30, 18, 0, tzinfo=timezone.utc)
    old = (reference - timedelta(hours=72)).isoformat()
    fresh = (reference - timedelta(hours=2)).isoformat()
    registry = {
        "stories": {
            "old": {
                "story_id": "old",
                "canonical_title": "Old major investigation",
                "importance": {"score": 95, "level": "breaking", "reasons": []},
                "timeline": [{"title": "Old major investigation", "url": "https://source.test/old", "published_at": old}],
                "local_relevance": {"score": 100, "counties": ["Martin County"]},
            },
            "fresh": {
                "story_id": "fresh",
                "canonical_title": "Fresh local government vote",
                "importance": {"score": 45, "level": "normal", "reasons": []},
                "timeline": [{"title": "Fresh local government vote", "url": "https://source.test/fresh", "published_at": fresh}],
                "local_relevance": {"score": 100, "counties": ["St. Lucie County"]},
            },
        }
    }
    cards = [
        {"headline": "Old major investigation", "link": "https://source.test/old", "urgency_score": 10, "cat_key": "crime"},
        {"headline": "Fresh local government vote", "link": "https://source.test/fresh", "urgency_score": 6, "cat_key": "local_gov"},
    ]
    report = build_homepage_ranking_recommendations(
        cards, {}, registry=registry, generated_at=reference.isoformat(), current_deck_count=1
    )
    assert report["recommended_deck"] == ["Fresh local government vote"]
    stale = next(row for row in report["stale_or_ineligible_deck_candidates"] if row["headline"] == "Old major investigation")
    assert stale["eligibility_reason"] == "older_than_60_hours"


def test_validated_material_update_refreshes_old_canonical_for_shadow_deck():
    reference = datetime(2026, 8, 30, 18, 0, tzinfo=timezone.utc)
    old = (reference - timedelta(days=10)).isoformat()
    update = (reference - timedelta(hours=1)).isoformat()
    registry = {
        "stories": {
            "story": {
                "story_id": "story",
                "canonical_title": "Long-running development dispute gets major ruling",
                "importance": {"score": 60, "level": "high", "reasons": []},
                "timeline": [{"title": "Long-running development dispute gets major ruling", "url": "https://source.test/ruling", "published_at": old}],
                "local_relevance": {"score": 100, "counties": ["Martin County"]},
            }
        }
    }
    card = {
        "headline": "Long-running development dispute gets major ruling",
        "link": "https://source.test/ruling",
        "slug": "development-ruling",
        "urgency_score": 7,
        "cat_key": "local_gov",
    }
    archive = [{
        "slug": "development-ruling",
        "headline": card["headline"],
        "source_url": card["link"],
        "first_published": old,
        "meaningful_update_validated": True,
        "last_meaningful_update_at": update,
    }]
    report = build_homepage_ranking_recommendations(
        [card], {}, registry=registry, archive=archive, generated_at=reference.isoformat()
    )
    item = report["items"][0]
    assert item["deck_eligible"] is True
    assert item["score_breakdown"]["age_hours"] == 1.0
    assert item["score_breakdown"]["timestamp_basis"] == "archive:last_meaningful_update_at"
    assert item["score_breakdown"]["material_update_bonus"] == 6.0


def test_soft_category_saturation_penalty_does_not_create_quota():
    now = datetime.now(timezone.utc).isoformat()
    cards = [
        {"headline": "Crime one", "urgency_score": 9, "cat_key": "crime", "published_raw": now},
        {"headline": "Crime two", "urgency_score": 9, "cat_key": "crime", "published_raw": now},
        {"headline": "Crime three", "urgency_score": 9, "cat_key": "crime", "published_raw": now},
        {"headline": "Government consequence", "urgency_score": 8, "cat_key": "local_gov", "published_raw": now},
    ]
    report = build_homepage_ranking_recommendations(cards, {}, registry={"stories": {}}, deck_limit=4)
    third_crime = next(row for row in report["items"] if row["headline"] == "Crime three")
    assert third_crime["category_saturation_penalty"] == 6.0
    assert report["controls"]["county_representation_quotas"] is False


def test_writer_can_emit_human_readable_shadow_review(tmp_path: Path):
    registry_path = tmp_path / "registry.json"
    output_path = tmp_path / "data" / "homepage-ranking-recommendations.json"
    review_path = tmp_path / "data" / "homepage-ranking-review.md"
    registry_path.write_text(json.dumps(_registry()), encoding="utf-8")
    report = write_homepage_ranking_recommendations(
        _cards(),
        {"headline": "Existing live hero"},
        registry_path=registry_path,
        archive=[],
        output_path=output_path,
        review_path=review_path,
        current_deck_count=2,
    )
    review = review_path.read_text(encoding="utf-8")
    assert "Publication behavior changed:** No" in review
    assert "## Hero" in review
    assert "## Top Stories deck" in review
    assert "County issues evacuation order" in review
    assert report["publication_behavior_changed"] is False
