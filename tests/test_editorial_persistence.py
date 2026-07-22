import json
from datetime import datetime, timezone

import pytest

from tct_engine import (
    EditorialAction,
    EditorialEngine,
    EditorialStateError,
)


DEFAULT_TIME = datetime(
    2026,
    7,
    20,
    12,
    0,
    tzinfo=timezone.utc,
)


def make_story(
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


def test_engine_state_survives_save_and_load(tmp_path):
    state_path = tmp_path / "editorial_state.json"

    engine = EditorialEngine(
        default_published_at=DEFAULT_TIME,
    )

    first = engine.process(
        make_story(
            article_id="wptv-cat-story",
            title="Deputies rescue 80 cats from Stuart home",
            body="Deputies rescued 80 cats from a Stuart home.",
            url="https://example.com/wptv-cat-story",
        ),
        source="WPTV",
        county="Martin",
    )

    assert first.action is EditorialAction.PUBLISH_NEW

    engine.save(state_path)

    restored = EditorialEngine.load(
        state_path,
        default_published_at=DEFAULT_TIME,
    )

    duplicate = restored.process(
        make_story(
            article_id="tcpalm-cat-story",
            title="Dozens of cats rescued from Stuart home",
            body="Authorities rescued 80 cats from a Stuart home.",
            url="https://example.com/tcpalm-cat-story",
        ),
        source="TCPalm",
        county="Martin",
    )

    assert duplicate.action is EditorialAction.IGNORE
    assert duplicate.canonical_article_id == "wptv-cat-story"


def test_custom_story_remains_canonical_after_reload(tmp_path):
    state_path = tmp_path / "editorial_state.json"

    engine = EditorialEngine(
        default_published_at=DEFAULT_TIME,
    )

    engine.process(
        make_story(
            article_id="wptv-cat-story",
            title="Deputies rescue 80 cats from Stuart home",
            body="Deputies rescued 80 cats from a Stuart home.",
            url="https://example.com/wptv-cat-story",
        ),
        source="WPTV",
        county="Martin",
    )

    replacement = engine.process(
        make_story(
            article_id="tct-cat-story",
            title="Stuart woman arrested after 80 cats rescued",
            body=(
                "Deputies rescued 80 cats from a Stuart home. "
                "The homeowner was arrested on animal cruelty charges."
            ),
            url="https://treasurecoast.today/tct-cat-story",
        ),
        source="Treasure Coast Today",
        county="Martin",
    )

    assert replacement.action is EditorialAction.REPLACE_CANONICAL

    engine.save(state_path)

    restored = EditorialEngine.load(
        state_path,
        default_published_at=DEFAULT_TIME,
    )

    result = restored.process(
        make_story(
            article_id="external-copy",
            title="Woman arrested after cats removed from home",
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
    assert result.canonical_article_id == "tct-cat-story"


def test_save_creates_valid_json_file(tmp_path):
    state_path = tmp_path / "editorial_state.json"

    engine = EditorialEngine(
        default_published_at=DEFAULT_TIME,
    )

    engine.process(
        make_story(
            article_id="story-1",
            title="Deputies rescue 80 cats from Stuart home",
            body="Deputies rescued 80 cats from a Stuart home.",
            url="https://example.com/story-1",
        ),
        source="WPTV",
        county="Martin",
    )

    engine.save(state_path)

    data = json.loads(
        state_path.read_text(encoding="utf-8")
    )

    assert data["version"] == 1
    assert len(data["articles"]) == 1
    assert data["articles"][0]["source"] == "WPTV"
    assert data["articles"][0]["county"] == "Martin"


def test_load_missing_state_file_returns_empty_engine(tmp_path):
    state_path = tmp_path / "missing-state.json"

    engine = EditorialEngine.load(
        state_path,
        default_published_at=DEFAULT_TIME,
    )

    result = engine.process(
        make_story(
            article_id="new-story",
            title="Deputies rescue 80 cats from Stuart home",
            body="Deputies rescued 80 cats from a Stuart home.",
            url="https://example.com/new-story",
        ),
        source="WPTV",
        county="Martin",
    )

    assert result.action is EditorialAction.PUBLISH_NEW


def test_invalid_json_raises_state_error(tmp_path):
    state_path = tmp_path / "editorial_state.json"
    state_path.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(
        EditorialStateError,
        match="valid JSON",
    ):
        EditorialEngine.load(
            state_path,
            default_published_at=DEFAULT_TIME,
        )


def test_unsupported_state_version_raises_error(tmp_path):
    state_path = tmp_path / "editorial_state.json"

    state_path.write_text(
        json.dumps(
            {
                "version": 999,
                "articles": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        EditorialStateError,
        match="version",
    ):
        EditorialEngine.load(
            state_path,
            default_published_at=DEFAULT_TIME,
        )


def test_loading_does_not_duplicate_saved_history(tmp_path):
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"

    engine = EditorialEngine(
        default_published_at=DEFAULT_TIME,
    )

    engine.process(
        make_story(
            article_id="story-1",
            title="Deputies rescue 80 cats from Stuart home",
            body="Deputies rescued 80 cats from a Stuart home.",
            url="https://example.com/story-1",
        ),
        source="WPTV",
        county="Martin",
    )

    engine.save(first_path)

    restored = EditorialEngine.load(
        first_path,
        default_published_at=DEFAULT_TIME,
    )

    restored.save(second_path)

    data = json.loads(
        second_path.read_text(encoding="utf-8")
    )

    assert len(data["articles"]) == 1