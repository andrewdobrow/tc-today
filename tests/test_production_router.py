from tct_engine import (
    EditorialAction,
    EditorialEngineResult,
    ProductionInstruction,
    ProductionRoute,
    route_editorial_result,
)


def make_result(
    *,
    action: EditorialAction,
    article_id: str = "incoming-story",
    canonical_article_id: str = "canonical-story",
    new_facts: tuple[str, ...] = (),
) -> EditorialEngineResult:
    return EditorialEngineResult(
        action=action,
        article_id=article_id,
        canonical_article_id=canonical_article_id,
        event_key="animal-rescue-stuart-cats",
        extracted_facts=("80 cats", "cats rescued"),
        new_facts=new_facts,
        is_custom=False,
    )


def test_publish_new_routes_to_article_generation():
    result = make_result(
        action=EditorialAction.PUBLISH_NEW,
        canonical_article_id="incoming-story",
    )

    instruction = route_editorial_result(result)

    assert isinstance(instruction, ProductionInstruction)
    assert instruction.route is ProductionRoute.GENERATE_NEW
    assert instruction.should_generate is True
    assert instruction.should_update is False
    assert instruction.should_skip is False
    assert instruction.target_article_id == "incoming-story"


def test_ignore_routes_to_skip():
    result = make_result(
        action=EditorialAction.IGNORE,
    )

    instruction = route_editorial_result(result)

    assert instruction.route is ProductionRoute.SKIP
    assert instruction.should_generate is False
    assert instruction.should_update is False
    assert instruction.should_skip is True
    assert instruction.target_article_id == "canonical-story"


def test_update_existing_routes_to_update():
    result = make_result(
        action=EditorialAction.UPDATE_EXISTING,
        new_facts=(
            "animal cruelty",
            "arrest made",
        ),
    )

    instruction = route_editorial_result(result)

    assert instruction.route is ProductionRoute.UPDATE_EXISTING
    assert instruction.should_generate is False
    assert instruction.should_update is True
    assert instruction.should_skip is False
    assert instruction.target_article_id == "canonical-story"
    assert instruction.new_facts == (
        "animal cruelty",
        "arrest made",
    )


def test_replace_canonical_routes_to_replacement_generation():
    result = make_result(
        action=EditorialAction.REPLACE_CANONICAL,
        article_id="tct-custom-story",
        canonical_article_id="tct-custom-story",
        new_facts=("arrest made",),
    )

    instruction = route_editorial_result(result)

    assert instruction.route is ProductionRoute.REPLACE_CANONICAL
    assert instruction.should_generate is True
    assert instruction.should_update is False
    assert instruction.should_skip is False
    assert instruction.target_article_id == "tct-custom-story"


def test_instruction_preserves_event_key():
    result = make_result(
        action=EditorialAction.IGNORE,
    )

    instruction = route_editorial_result(result)

    assert instruction.event_key == "animal-rescue-stuart-cats"


def test_instruction_preserves_incoming_article_id():
    result = make_result(
        action=EditorialAction.UPDATE_EXISTING,
        article_id="sheriff-update",
    )

    instruction = route_editorial_result(result)

    assert instruction.incoming_article_id == "sheriff-update"