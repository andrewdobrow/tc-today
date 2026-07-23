from pathlib import Path
from tempfile import TemporaryDirectory

from tct_engine.editorial_pipeline import EditorialPipeline, PipelineArticle


def article(article_id, event_key, title, facts):
    return PipelineArticle(
        article_id=article_id,
        event_key=event_key,
        title=title,
        source="WPTV",
        url=f"https://example.com/{article_id}",
        is_custom=False,
        facts=tuple(facts),
    )


def test_same_event_keeps_story_id_and_editorial_behavior():
    with TemporaryDirectory() as tmp:
        pipeline = EditorialPipeline(registry_path=Path(tmp) / "registry.json")
        first = pipeline.process(article(
            "one", "animal-rescue-stuart-cats",
            "Deputies rescue 80 cats from Stuart home",
            ("80 cats rescued", "Stuart home"),
        ))
        second = pipeline.process(article(
            "two", "animal-rescue-stuart-cats",
            "Dozens of cats rescued in Stuart",
            ("80 cats rescued", "Stuart home"),
        ))
        assert first.story_id == second.story_id
        assert second.action.name == "IGNORE"


def test_related_different_events_can_share_story():
    with TemporaryDirectory() as tmp:
        pipeline = EditorialPipeline(registry_path=Path(tmp) / "registry.json")
        first = pipeline.process(article(
            "one", "animal-rescue-stuart-cats",
            "Deputies rescue 80 cats from Stuart home",
            ("80 cats rescued", "animal cruelty investigation", "Stuart home"),
        ))
        second = pipeline.process(article(
            "two", "animal-cruelty-arrest-stuart",
            "Woman arrested after 80 cats rescued in Stuart",
            ("80 cats rescued", "animal cruelty charges", "Stuart home"),
        ))
        assert first.story_id == second.story_id
        assert first.event_key != second.event_key
