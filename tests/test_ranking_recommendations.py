from copy import deepcopy
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
    return [
        {"headline": "Community festival announced", "link": "https://source.test/festival", "cat_key": "things_to_do"},
        {"headline": "County issues evacuation order", "link": "https://source.test/evacuation", "cat_key": "crime"},
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
    assert item["score"] == 56
    assert item["score_breakdown"]["basis"] == "live_urgency_fallback"
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
    assert item["score_breakdown"]["basis"] == "persistent_story_registry"


def test_custom_article_is_position_locked_even_without_registry_match():
    cards = [
        {"headline": "Generated low story", "urgency_score": 1},
        {"headline": "Manual traffic report", "is_custom": True, "urgency_score": 1},
        {"headline": "Generated high story", "urgency_score": 10},
    ]
    report = build_homepage_ranking_recommendations(cards, {}, registry={"stories": {}})
    manual = next(item for item in report["items"] if item["headline"] == "Manual traffic report")
    assert manual["current_position"] == 2
    assert manual["recommended_position"] == 2
    assert manual["position_locked"] is True
    assert manual["position_lock_reason"] == "custom_article"
    assert all(move["headline"] != "Manual traffic report" for move in report["recommendations"])


def test_report_counts_unchanged_positions_after_deduplication():
    report = build_homepage_ranking_recommendations(_cards(), {}, registry=_registry())
    assert report["summary"]["recommended_moves"] == 2
    assert report["summary"]["unchanged_positions"] == 0
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
