from datetime import datetime, timezone

from tct_engine import (
    EditorialAction,
    EditorialPipeline,
    PipelineArticle,
)


def make_article(
    article_id: str,
    *,
    event_key: str = "martin-county-cat-hoarding",
    source: str = "WPTV",
    is_custom: bool = False,
    facts: tuple[str, ...] = (),
    status: str = "developing",
    is_major: bool = False,
    is_correction: bool = False,
    hour: int = 8,
) -> PipelineArticle:
    return PipelineArticle(
        article_id=article_id,
        event_key=event_key,
        title="Deputies rescue cats from Martin County home",
        source=source,
        url=f"https://example.com/{article_id}",
        is_custom=is_custom,
        facts=facts,
        status=status,
        is_major=is_major,
        is_correction=is_correction,
        published_at=datetime(
            2026,
            7,
            20,
            hour,
            0,
            tzinfo=timezone.utc,
        ),
    )


def test_first_article_is_published_and_becomes_canonical():
    pipeline = EditorialPipeline()

    result = pipeline.process(
        make_article(
            "wptv-1",
            facts=("Deputies removed dozens of cats.",),
        )
    )

    assert result.action is EditorialAction.PUBLISH_NEW
    assert result.event_key == "martin-county-cat-hoarding"
    assert result.canonical_article_id == "wptv-1"
    assert result.new_facts == ("Deputies removed dozens of cats.",)


def test_duplicate_external_article_is_ignored():
    pipeline = EditorialPipeline()

    pipeline.process(
        make_article(
            "wptv-1",
            facts=("Deputies removed dozens of cats.",),
        )
    )

    result = pipeline.process(
        make_article(
            "tcpalm-1",
            source="TCPalm",
            facts=("Deputies removed dozens of cats.",),
            hour=9,
        )
    )

    assert result.action is EditorialAction.IGNORE
    assert result.canonical_article_id == "wptv-1"
    assert result.new_facts == ()


def test_custom_story_replaces_external_canonical():
    pipeline = EditorialPipeline()

    pipeline.process(
        make_article(
            "wptv-1",
            facts=("Deputies removed dozens of cats.",),
        )
    )

    result = pipeline.process(
        make_article(
            "tct-custom-1",
            source="Treasure Coast Today",
            is_custom=True,
            facts=(
                "Deputies removed dozens of cats.",
                "The sheriff called it the worst hoarding case he had seen.",
            ),
            hour=10,
        )
    )

    assert result.action is EditorialAction.REPLACE_CANONICAL
    assert result.canonical_article_id == "tct-custom-1"
    assert result.new_facts == (
        "The sheriff called it the worst hoarding case he had seen.",
    )


def test_external_update_updates_existing_custom_story():
    pipeline = EditorialPipeline()

    pipeline.process(
        make_article(
            "tct-custom-1",
            source="Treasure Coast Today",
            is_custom=True,
            facts=("Deputies removed dozens of cats.",),
        )
    )

    result = pipeline.process(
        make_article(
            "sheriff-update",
            source="Martin County Sheriff's Office",
            facts=(
                "Deputies removed dozens of cats.",
                "Animal Control took custody of the cats.",
            ),
            hour=11,
        )
    )

    assert result.action is EditorialAction.UPDATE_EXISTING
    assert result.canonical_article_id == "tct-custom-1"
    assert result.new_facts == (
        "Animal Control took custody of the cats.",
    )


def test_major_update_is_preserved():
    pipeline = EditorialPipeline()

    pipeline.process(
        make_article(
            "initial",
            facts=("One person was injured.",),
        )
    )

    result = pipeline.process(
        make_article(
            "hospital-update",
            facts=(
                "One person was injured.",
                "The victim later died at the hospital.",
            ),
            is_major=True,
            hour=12,
        )
    )

    assert result.action is EditorialAction.UPDATE_EXISTING
    assert result.is_major is True
    assert result.new_facts == (
        "The victim later died at the hospital.",
    )


def test_pipeline_keeps_events_separate():
    pipeline = EditorialPipeline()

    first = pipeline.process(
        make_article(
            "cat-story",
            facts=("Deputies removed dozens of cats.",),
        )
    )

    second = pipeline.process(
        make_article(
            "crash-story",
            event_key="us-1-fatal-crash",
            facts=("A crash closed U.S. 1.",),
        )
    )

    assert first.canonical_article_id == "cat-story"
    assert second.canonical_article_id == "crash-story"
    assert pipeline.get_event("martin-county-cat-hoarding") is not None
    assert pipeline.get_event("us-1-fatal-crash") is not None