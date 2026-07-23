from pathlib import Path

from tct_engine.editorial_eligibility import EditorialEligibilityEngine
from tct_engine.editorial_proximity import calculate_editorial_priority
from tct_engine.editorial_pipeline import EditorialPipeline, PipelineArticle


def article(article_id, event_key, title, facts, **kwargs):
    return PipelineArticle(
        article_id=article_id,
        event_key=event_key,
        title=title,
        source=kwargs.pop("source", "https://www.wptv.com/news/local-news.rss"),
        url=kwargs.pop("url", f"https://example.com/{article_id}"),
        is_custom=kwargs.pop("is_custom", False),
        facts=tuple(facts),
        **kwargs,
    )


def test_google_feed_is_aggregator_not_unknown():
    result = EditorialEligibilityEngine().evaluate(
        {"title": "Local story", "link": "https://news.google.com/rss/articles/example"},
        source="https://news.google.com/rss/search?q=stuart+florida",
    )
    assert result.source_profile.source_class == "aggregator"


def test_publisher_url_beats_feed_alias():
    result = EditorialEligibilityEngine().evaluate(
        {"title": "Local story", "link": "https://www.wptv.com/news/region-martin-county/story"},
        source="https://news.google.com/rss/search?q=stuart+florida",
    )
    assert result.source_profile.source_class == "local_news"


def test_local_story_outranks_equally_important_florida_story():
    assert calculate_editorial_priority(100, 100) == 100
    assert calculate_editorial_priority(100, 55) == 55


def test_exact_event_emits_same_event_decision(tmp_path: Path):
    pipeline = EditorialPipeline(registry_path=tmp_path / "registry.json")
    first = pipeline.process(article("a", "event-a", "Crash closes US 1 in Stuart", ("road closed",), locations=("Stuart",), event_types=("traffic crash",)))
    second = pipeline.process(article("b", "event-a", "US 1 remains closed after Stuart crash", ("road closed",), locations=("Stuart",), event_types=("traffic crash",)))
    assert first.relationship == "new_story"
    assert second.relationship == "same_event"
    assert second.relationship_confidence == 1.0
    assert second.decision_trace
