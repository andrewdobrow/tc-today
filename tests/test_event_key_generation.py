from tct_engine import (
    ExtractedArticleFacts,
    generate_event_key,
)


def make_facts(
    *,
    facts=(),
    locations=(),
    agencies=(),
    event_types=(),
):
    return ExtractedArticleFacts(
        article_id="1",
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

    assert (
        generate_event_key(facts)
        == "animal-rescue-stuart-cats"
    )


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

    assert (
        generate_event_key(first)
        ==
        generate_event_key(second)
    )


def test_crash_key():

    facts = make_facts(
        facts=("road closed",),
        locations=("Port St. Lucie",),
        event_types=("traffic crash",),
    )

    assert (
        generate_event_key(facts)
        ==
        "traffic-crash-port-st-lucie"
    )


def test_unknown_event():

    facts = make_facts()

    assert generate_event_key(facts) == "unknown-event"