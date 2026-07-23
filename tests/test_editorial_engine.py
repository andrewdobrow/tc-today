from datetime import datetime, timezone

from tct_engine import (
    EditorialAction,
    EditorialEngine,
    EditorialEngineResult,
)


DEFAULT_TIME = datetime(
    2026,
    7,
    20,
    12,
    0,
    tzinfo=timezone.utc,
)


def make_cat_story(
    *,
    article_id: str,
    title: str,
    body: str,
    url: str,
) -> dict:
    return {
        "id": article_id,
        "title": title,
        "link": url,
        "summary": body,
    }


def test_processes_rss_entry_end_to_end():
    engine = EditorialEngine(
        default_published_at=DEFAULT_TIME,
    )

    result = engine.process(
        make_cat_story(
            article_id="wptv-cat-story",
            title="Deputies rescue 80 cats from Stuart home",
            body=(
                "Martin County sheriff's deputies rescued "
                "80 cats from a home in Stuart."
            ),
            url="https://example.com/wptv-cat-story",
        ),
        source="WPTV",
        county="Martin",
    )

    assert isinstance(result, EditorialEngineResult)
    assert result.action is EditorialAction.PUBLISH_NEW
    assert result.article_id == "wptv-cat-story"
    assert result.event_key == "animal-rescue-stuart-cats"
    assert result.canonical_article_id == "wptv-cat-story"
    assert "80 cats" in result.extracted_facts
    assert "cats rescued" in result.extracted_facts


def test_duplicate_external_story_is_ignored(tmp_path):
    engine = EditorialEngine(
        default_published_at=DEFAULT_TIME,
        registry_path=tmp_path / "registry.json",
    )

    engine.process(
        make_cat_story(
            article_id="wptv-cat-story",
            title="Deputies rescue 80 cats from Stuart home",
            body=(
                "Deputies rescued 80 cats from a home "
                "in Stuart."
            ),
            url="https://example.com/wptv-cat-story",
        ),
        source="WPTV",
        county="Martin",
    )

    result = engine.process(
        make_cat_story(
            article_id="tcpalm-cat-story",
            title="Dozens of cats rescued from Stuart residence",
            body=(
                "Authorities rescued 80 cats from a home "
                "in Stuart."
            ),
            url="https://example.com/tcpalm-cat-story",
        ),
        source="TCPalm",
        county="Martin",
    )

    assert result.action is EditorialAction.IGNORE
    assert result.event_key == "animal-rescue-stuart-cats"
    assert result.canonical_article_id == "wptv-cat-story"
    assert result.new_facts == ()
    assert result.relationship == "same_event"


def test_custom_tct_story_replaces_external_canonical(tmp_path):
    engine = EditorialEngine(
        default_published_at=DEFAULT_TIME,
        registry_path=tmp_path / "registry.json",
    )

    engine.process(
        make_cat_story(
            article_id="wptv-cat-story",
            title="Deputies rescue 80 cats from Stuart home",
            body=(
                "Deputies rescued 80 cats from a home "
                "in Stuart."
            ),
            url="https://example.com/wptv-cat-story",
        ),
        source="WPTV",
        county="Martin",
    )

    result = engine.process(
        make_cat_story(
            article_id="tct-custom-cat-story",
            title=(
                "Stuart woman arrested after deputies "
                "rescue 80 cats"
            ),
            body=(
                "Martin County sheriff's deputies rescued "
                "80 cats from a Stuart home. The homeowner "
                "was arrested on animal cruelty charges."
            ),
            url=(
                "https://treasurecoast.today/"
                "stuart-woman-arrested-80-cats"
            ),
        ),
        source="Treasure Coast Today",
        county="Martin",
    )

    assert result.action is EditorialAction.REPLACE_CANONICAL
    assert result.canonical_article_id == "tct-custom-cat-story"
    assert result.is_custom is True
    assert "arrest made" in result.new_facts
    assert "animal cruelty" in result.new_facts
    assert result.relationship == "follow_up"


def test_later_external_duplicate_does_not_replace_custom_story():
    engine = EditorialEngine(
        default_published_at=DEFAULT_TIME,
    )

    engine.process(
        make_cat_story(
            article_id="tct-custom-cat-story",
            title=(
                "Stuart woman arrested after deputies "
                "rescue 80 cats"
            ),
            body=(
                "Deputies rescued 80 cats from a Stuart home. "
                "The homeowner was arrested on animal cruelty charges."
            ),
            url=(
                "https://treasurecoast.today/"
                "stuart-woman-arrested-80-cats"
            ),
        ),
        source="Treasure Coast Today",
        county="Martin",
    )

    result = engine.process(
        make_cat_story(
            article_id="external-copy",
            title=(
                "Woman arrested after 80 cats removed "
                "from Stuart home"
            ),
            body=(
                "Deputies rescued 80 cats from a Stuart home. "
                "The homeowner was arrested on animal cruelty charges."
            ),
            url="https://example.com/external-copy",
        ),
        source="WPTV",
        county="Martin",
    )

    assert result.action is EditorialAction.IGNORE
    assert result.canonical_article_id == "tct-custom-cat-story"
    assert result.is_custom is False


def test_external_story_with_new_fact_updates_custom_story(tmp_path):
    engine = EditorialEngine(
        default_published_at=DEFAULT_TIME,
        registry_path=tmp_path / "registry.json",
    )

    engine.process(
        make_cat_story(
            article_id="tct-custom-cat-story",
            title="Deputies rescue 80 cats from Stuart home",
            body=(
                "Deputies rescued 80 cats from a home "
                "in Stuart."
            ),
            url="https://treasurecoast.today/cat-story",
        ),
        source="Treasure Coast Today",
        county="Martin",
    )

    result = engine.process(
        make_cat_story(
            article_id="sheriff-update",
            title="Woman arrested after Stuart animal rescue",
            body=(
                "Deputies rescued 80 cats from a Stuart home. "
                "The homeowner was arrested on animal cruelty charges."
            ),
            url="https://example.com/sheriff-update",
        ),
        source="Martin County Sheriff's Office",
        county="Martin",
    )

    assert result.action is EditorialAction.UPDATE_EXISTING
    assert result.canonical_article_id == "tct-custom-cat-story"
    assert "arrest made" in result.new_facts
    assert "animal cruelty" in result.new_facts
    assert result.relationship == "follow_up"


def test_different_events_remain_separate():
    engine = EditorialEngine(
        default_published_at=DEFAULT_TIME,
    )

    cat_result = engine.process(
        make_cat_story(
            article_id="cat-story",
            title="Deputies rescue 80 cats from Stuart home",
            body="Deputies rescued 80 cats from a Stuart home.",
            url="https://example.com/cat-story",
        ),
        source="WPTV",
        county="Martin",
    )

    crash_result = engine.process(
        {
            "id": "crash-story",
            "title": "Fatal crash closes U.S. 1 in Port St. Lucie",
            "link": "https://example.com/crash-story",
            "summary": (
                "A fatal crash closed U.S. 1 "
                "in Port St. Lucie."
            ),
        },
        source="WPTV",
        county="St. Lucie",
    )

    assert cat_result.event_key == "animal-rescue-stuart-cats"
    assert crash_result.event_key == (
        "traffic-crash-port-st-lucie"
    )
    assert cat_result.canonical_article_id == "cat-story"
    assert crash_result.canonical_article_id == "crash-story"


def test_engine_can_retrieve_existing_event():
    engine = EditorialEngine(
        default_published_at=DEFAULT_TIME,
    )

    result = engine.process(
        make_cat_story(
            article_id="cat-story",
            title="Deputies rescue 80 cats from Stuart home",
            body="Deputies rescued 80 cats from a Stuart home.",
            url="https://example.com/cat-story",
        ),
        source="WPTV",
        county="Martin",
    )

    event = engine.get_event(result.event_key)

    assert event is not None
    assert event.canonical.article_id == "cat-story"

def test_sparse_unknown_articles_do_not_collapse_into_one_event(tmp_path):
    engine = EditorialEngine(
        default_published_at=DEFAULT_TIME,
        registry_path=tmp_path / "registry.json",
    )

    first = engine.process(
        {
            "id": "unknown-one",
            "title": "Stuart commission reviews summer internship program",
            "link": "https://example.com/unknown-one",
            "summary": "Officials reviewed the program during a public meeting.",
        },
        source="WPTV",
        county="Martin",
    )
    second = engine.process(
        {
            "id": "unknown-two",
            "title": "Vero Beach nonprofit announces community fundraiser",
            "link": "https://example.com/unknown-two",
            "summary": "The organization announced a fundraiser for local families.",
        },
        source="WPTV",
        county="Indian River",
    )

    assert first.event_key.startswith("unknown-event-")
    assert second.event_key.startswith("unknown-event-")
    assert first.event_key != second.event_key
    assert first.story_id != second.story_id
    assert first.action is EditorialAction.PUBLISH_NEW
    assert second.action is EditorialAction.PUBLISH_NEW
