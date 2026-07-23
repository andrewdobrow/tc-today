from pathlib import Path

from tct_engine.observability import (
    ENGINE_VERSION,
    OBSERVABILITY_SCHEMA_VERSION,
    build_editorial_observability,
    write_editorial_observability,
)


class FakeEngine:
    def get_top_stories(self, limit=10):
        return [
            {
                "story_id": "story_000001",
                "canonical_title": "Woman arrested after 80 cats rescued",
                "events": ["rescue", "arrest"],
                "timeline": [{"event_key": "rescue"}, {"event_key": "arrest"}],
                "importance": {"score": 86, "level": "high", "reasons": ["public_safety"]},
                "local_relevance": {
                    "scope": "treasure_coast",
                    "score": 100,
                    "counties": ["Martin"],
                    "places": ["Stuart"],
                },
                "relationship_history": [
                    {
                        "event_key": "arrest",
                        "relationship": "follow_up",
                        "confidence": 0.94,
                        "reason": "same developing case",
                        "decision_trace": ["same city", "same agency", "shared 80 cats fact"],
                    }
                ],
                "resolution_history": [
                    {
                        "event_key": "rescue",
                        "relationship": "new_story",
                        "confidence": 0.0,
                        "matched_existing": False,
                        "reason": "no matching story",
                        "decision_trace": ["no candidates"],
                    }
                ],
                "title_candidates": [{"title": "Woman arrested after 80 cats rescued"}],
            }
        ]


def test_observability_exports_relationships_and_locality():
    report = build_editorial_observability(
        FakeEngine(),
        [{
            "route": "publish_new",
            "eligible": True,
            "eligibility_status": "publishable",
            "source_class": "local_news",
        }],
    )
    assert report["schema_version"] == OBSERVABILITY_SCHEMA_VERSION
    assert report["engine"]["version"] == ENGINE_VERSION
    assert report["relationships"]["counts"]["follow_up"] == 1
    assert report["relationships"]["counts"]["new_story"] == 1
    assert report["local_relevance"]["average_score"] == 100.0
    assert report["stories"]["top"][0]["local_relevance"]["score"] == 100


def test_observability_write_is_atomic(tmp_path: Path):
    output = tmp_path / "editorial_observability.json"
    report = write_editorial_observability(FakeEngine(), [], output)
    assert output.exists()
    assert not output.with_suffix(".json.tmp").exists()
    assert report["status"] == "healthy"
