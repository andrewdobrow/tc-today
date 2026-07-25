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
