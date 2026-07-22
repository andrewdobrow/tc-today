from datetime import datetime, timezone

from tct_engine import (
    ExtractedArticleFacts,
    RawArticle,
    extract_article_facts,
)


def make_article(
    *,
    title: str,
    body: str,
    source: str = "WPTV",
    county: str | None = "Martin",
) -> RawArticle:
    return RawArticle(
        article_id="article-1",
        title=title,
        body=body,
        source=source,
        url="https://example.com/article-1",
        published_at=datetime(
            2026,
            7,
            20,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        county=county,
        is_custom=False,
    )


def test_extracts_animal_rescue_facts():
    article = make_article(
        title="Deputies rescue 80 cats from Stuart home",
        body=(
            "Martin County sheriff's deputies rescued 80 cats "
            "from a home in Stuart. The homeowner was arrested "
            "on animal cruelty charges."
        ),
    )

    result = extract_article_facts(article)

    assert isinstance(result, ExtractedArticleFacts)
    assert result.article_id == "article-1"
    assert "80 cats" in result.facts
    assert "cats rescued" in result.facts
    assert "arrest made" in result.facts
    assert "animal cruelty" in result.facts
    assert "Stuart" in result.locations
    assert "Martin County Sheriff's Office" in result.agencies
    assert result.event_types == ("animal rescue",)


def test_extracts_crash_and_road_closure_facts():
    article = make_article(
        title="Fatal crash closes U.S. 1 in Port St. Lucie",
        body=(
            "A fatal crash closed U.S. 1 near Prima Vista Boulevard "
            "in Port St. Lucie. One person died and two people were injured."
        ),
        county="St. Lucie",
    )

    result = extract_article_facts(article)

    assert "road closed" in result.facts
    assert "1 person died" in result.facts
    assert "2 people injured" in result.facts
    assert "Port St. Lucie" in result.locations
    assert result.event_types == ("traffic crash",)


def test_extracts_fire_facts():
    article = make_article(
        title="Fire damages Fort Pierce business",
        body=(
            "St. Lucie County Fire District crews responded to a fire "
            "at a business in Fort Pierce. No injuries were reported."
        ),
        county="St. Lucie",
    )

    result = extract_article_facts(article)

    assert "fire reported" in result.facts
    assert "no injuries reported" in result.facts
    assert "Fort Pierce" in result.locations
    assert "St. Lucie County Fire District" in result.agencies
    assert result.event_types == ("fire",)


def test_extracts_missing_person_facts():
    article = make_article(
        title="Deputies search for missing Jensen Beach teenager",
        body=(
            "The Martin County Sheriff's Office is searching for "
            "a missing 16-year-old from Jensen Beach."
        ),
    )

    result = extract_article_facts(article)

    assert "missing person" in result.facts
    assert "16-year-old" in result.facts
    assert "Jensen Beach" in result.locations
    assert result.event_types == ("missing person",)


def test_custom_flag_is_preserved():
    article = RawArticle(
        article_id="tct-custom-1",
        title="TCT custom report",
        body="Deputies rescued 80 cats from a Stuart home.",
        source="Treasure Coast Today",
        url="https://treasurecoast.today/custom-story",
        published_at=datetime(
            2026,
            7,
            20,
            11,
            0,
            tzinfo=timezone.utc,
        ),
        county="Martin",
        is_custom=True,
    )

    result = extract_article_facts(article)

    assert result.is_custom is True
    assert result.source == "Treasure Coast Today"


def test_extraction_is_deterministic():
    article = make_article(
        title="Deputies rescue 80 cats from Stuart home",
        body=(
            "Martin County sheriff's deputies rescued 80 cats "
            "from a home in Stuart."
        ),
    )

    first = extract_article_facts(article)
    second = extract_article_facts(article)

    assert first == second


def test_duplicate_facts_are_removed():
    article = make_article(
        title="Crash closes road",
        body=(
            "The crash closed the road. The road remains closed "
            "because of the crash."
        ),
    )

    result = extract_article_facts(article)

    assert result.facts.count("road closed") == 1


def test_unknown_article_returns_empty_fact_collections():
    article = make_article(
        title="Community gathers Tuesday",
        body="Residents gathered for a regularly scheduled community meeting.",
        county=None,
    )

    result = extract_article_facts(article)

    assert result.facts == ()
    assert result.locations == ()
    assert result.agencies == ()
    assert result.event_types == ()