from tct_engine import (
    ExtractedArticleFacts,
    generate_event_key,
)


def make_facts(
    *,
    article_id="1",
    facts=(),
    locations=(),
    agencies=(),
    event_types=(),
):
    return ExtractedArticleFacts(
        article_id=article_id,
        source="WPTV",
        is_custom=False,
        facts=facts,
        locations=locations,
        agencies=agencies,
        event_types=event_types,
    )


def test_cat_rescue_key():
    facts = make_facts(
        facts=("80 cats", "cats rescued"),
        locations=("Stuart",),
        event_types=("animal rescue",),
    )

    assert generate_event_key(facts) == "animal-rescue-stuart-cats"


def test_order_does_not_matter():
    first = make_facts(
        facts=("80 cats", "cats rescued"),
        locations=("Stuart",),
        event_types=("animal rescue",),
    )

    second = make_facts(
        facts=("cats rescued", "80 cats"),
        locations=("Stuart",),
        event_types=("animal rescue",),
    )

    assert generate_event_key(first) == generate_event_key(second)


def test_crash_key():
    facts = make_facts(
        facts=("road closed",),
        locations=("Port St. Lucie",),
        event_types=("traffic crash",),
    )

    event_key = generate_event_key(facts)
    assert event_key.startswith("traffic-crash-port-st-lucie-")
    assert event_key == generate_event_key(facts)


def test_unknown_events_do_not_share_one_global_key():
    first = make_facts(article_id="rss-alpha")
    second = make_facts(article_id="rss-beta")

    first_key = generate_event_key(first)
    second_key = generate_event_key(second)

    assert first_key.startswith("unknown-event-")
    assert second_key.startswith("unknown-event-")
    assert first_key != second_key


def test_unlocated_recurrent_events_do_not_share_one_key():
    first = make_facts(
        article_id="fire-one",
        facts=("fire reported",),
        event_types=("fire",),
    )
    second = make_facts(
        article_id="fire-two",
        facts=("fire reported",),
        event_types=("fire",),
    )

    first_key = generate_event_key(first)
    second_key = generate_event_key(second)

    assert first_key.startswith("fire-")
    assert second_key.startswith("fire-")
    assert first_key != second_key


def test_same_sparse_article_keeps_same_event_key_across_runs():
    first = make_facts(article_id="stable-rss-id")
    second = make_facts(article_id="stable-rss-id")

    assert generate_event_key(first) == generate_event_key(second)


def test_same_city_missing_person_articles_receive_distinct_event_keys():
    first = make_facts(
        article_id="missing-alpha",
        facts=("missing person",),
        locations=("Port St. Lucie",),
        event_types=("missing person",),
    )
    second = make_facts(
        article_id="missing-beta",
        facts=("missing person",),
        locations=("Port St. Lucie",),
        event_types=("missing person",),
    )

    first_key = generate_event_key(first)
    second_key = generate_event_key(second)

    assert first_key.startswith("missing-person-port-st-lucie-")
    assert second_key.startswith("missing-person-port-st-lucie-")
    assert first_key != second_key
    assert first_key == generate_event_key(first)
