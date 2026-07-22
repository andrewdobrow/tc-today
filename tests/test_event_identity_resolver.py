from tct_engine import (
    ArticleIdentityInput,
    EventIdentity,
    resolve_event_identity,
)

def test_event_identity_defaults_are_safe():
    identity = EventIdentity()

    assert identity.same_event is False
    assert identity.confidence == 0.0
    assert identity.event_key is None
    assert identity.reason == ""
    assert identity.shared_entities == []
    assert identity.shared_locations == []
    assert identity.stage_transition is None
    assert identity.metadata == {}


def test_event_identity_can_hold_match_details():
    identity = EventIdentity(
        same_event=True,
        confidence=98.0,
        event_key="east-midway-road-dirt-bike-crash",
        reason="same road, incident type, and reporting progression",
        shared_entities=["FedEx truck", "dirt bike rider"],
        shared_locations=["East Midway Road"],
        stage_transition="initial_report_to_identity_update",
        metadata={"county": "St. Lucie"},
    )

    assert identity.same_event is True
    assert identity.confidence == 98.0
    assert identity.event_key == "east-midway-road-dirt-bike-crash"
    assert "FedEx truck" in identity.shared_entities
    assert "East Midway Road" in identity.shared_locations
    assert identity.metadata["county"] == "St. Lucie"


def test_matching_event_keys_are_an_absolute_match():
    left = ArticleIdentityInput(
        title="Dirt bike rider killed in East Midway Road crash",
        event_key="east-midway-road-dirt-bike-crash",
    )

    right = ArticleIdentityInput(
        title="Deputies identify rider killed in Fort Pierce collision",
        event_key="east-midway-road-dirt-bike-crash",
    )

    result = resolve_event_identity(left, right)

    assert result.same_event is True
    assert result.confidence == 100.0
    assert result.event_key == "east-midway-road-dirt-bike-crash"
    assert result.metadata["matched_by"] == "event_key"


def test_same_location_event_type_and_entity_resolve_as_same_event():
    left = ArticleIdentityInput(
        title="Dirt bike rider killed in crash with FedEx truck",
        location="East Midway Road",
        county="St. Lucie",
        entities=["FedEx truck"],
        event_type="fatal crash",
    )

    right = ArticleIdentityInput(
        title="Rider identified after East Midway Road crash",
        location="East Midway Road",
        county="St. Lucie",
        entities=["FedEx truck"],
        event_type="fatal crash",
    )

    result = resolve_event_identity(left, right)

    assert result.same_event is True
    assert result.confidence >= 70.0
    assert "fedex truck" in result.shared_entities
    assert "east midway road" in result.shared_locations


def test_similar_crashes_in_same_county_remain_separate():
    left = ArticleIdentityInput(
        title="Motorcyclist killed in crash on East Midway Road",
        location="East Midway Road",
        county="St. Lucie",
        entities=["motorcyclist"],
        event_type="fatal crash",
    )

    right = ArticleIdentityInput(
        title="Driver killed in crash on Okeechobee Road",
        location="Okeechobee Road",
        county="St. Lucie",
        entities=["pickup truck"],
        event_type="fatal crash",
    )

    result = resolve_event_identity(left, right)

    assert result.same_event is False
    assert result.metadata["county_match"] is True
    assert result.metadata["event_type_match"] is True
    assert result.metadata["location_match"] is False


def test_shared_location_without_event_type_or_entity_is_not_enough():
    left = ArticleIdentityInput(
        title="Road closure announced on U.S. 1",
        location="U.S. 1",
        county="Martin",
        event_type="road closure",
    )

    right = ArticleIdentityInput(
        title="New restaurant opens along U.S. 1",
        location="U.S. 1",
        county="Martin",
        event_type="business opening",
    )

    result = resolve_event_identity(left, right)

    assert result.same_event is False


def test_dictionary_article_inputs_are_supported():
    left = {
        "title": "Missing Stuart woman found safe",
        "location": "Stuart",
        "county": "Martin",
        "entities": ["Jane Doe"],
        "event_type": "missing person",
        "is_custom": True,
    }

    right = {
        "title": "Authorities locate missing woman from Stuart",
        "location": "Stuart",
        "county": "Martin",
        "entities": ["Jane Doe"],
        "event_type": "missing person",
    }

    result = resolve_event_identity(left, right)

    assert result.same_event is True
    assert result.metadata["custom_article_present"] is True


def test_unrelated_articles_return_no_identity_match():
    left = ArticleIdentityInput(
        title="Mets defeat Mighty Mussels at Clover Park",
        location="Clover Park",
        county="St. Lucie",
        entities=["St. Lucie Mets"],
        event_type="baseball game",
    )

    right = ArticleIdentityInput(
        title="City Council approves annual budget",
        location="Port St. Lucie City Hall",
        county="St. Lucie",
        entities=["Port St. Lucie City Council"],
        event_type="government decision",
    )

    result = resolve_event_identity(left, right)

    assert result.same_event is False
    assert result.confidence < 70.0
    assert result.event_key is None