from tct_engine.story_relationship import StoryRelationshipEngine, StoryRelationshipType


def story(**overrides):
    base = {
        "story_id": "story_000001",
        "status": "developing",
        "facts": ["80 cats", "cats rescued", "animal cruelty"],
        "locations": ["Stuart"],
        "agencies": ["Martin County Sheriff's Office"],
        "event_types": ["animal rescue"],
        "entities": [],
        "canonical_title": "Deputies rescue 80 cats from Stuart home",
        "title_tokens": [],
        "events": ["stuart-cat-rescue"],
    }
    base.update(overrides)
    return base


def test_later_arrest_is_follow_up():
    result = StoryRelationshipEngine().classify(
        event_key="stuart-animal-cruelty-arrest",
        title="Woman arrested after 80 cats rescued from Stuart home",
        facts=("80 cats", "animal cruelty", "arrest made"),
        locations=("Stuart",),
        agencies=("Martin County Sheriff's Office",),
        event_types=("animal rescue",),
        stories=(story(),),
    )
    assert result.relationship is StoryRelationshipType.FOLLOW_UP
    assert result.story_id == "story_000001"


def test_conflicting_injury_counts_are_new_story():
    result = StoryRelationshipEngine().classify(
        event_key="us1-evening-crash",
        title="Evening crash closes US 1 in Stuart",
        facts=("road closed", "2 people injured"),
        locations=("Stuart",),
        event_types=("traffic crash",),
        stories=(story(
            facts=["road closed", "1 person injured"],
            locations=["Stuart"],
            agencies=[],
            event_types=["traffic crash"],
            canonical_title="Morning crash closes US 1 in Stuart",
            events=["us1-morning-crash"],
        ),),
    )
    assert result.relationship is StoryRelationshipType.NEW_STORY
