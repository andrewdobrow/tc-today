from tct_engine.story_registry import StoryRegistry
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


def test_duplicate_arrest_coverage_is_not_a_follow_up():
    existing = story(
        facts=["80 cats", "animal cruelty", "arrest made"],
        canonical_title="Woman arrested after 80 cats rescued from Stuart home",
        titles=["Woman arrested after 80 cats rescued from Stuart home"],
    )
    result = StoryRelationshipEngine().classify(
        event_key="stuart-hoarding-arrest-coverage",
        title="Stuart woman arrested after deputies rescue 80 cats from home",
        facts=("80 cats", "animal cruelty", "arrest made"),
        locations=("Stuart",),
        agencies=("Martin County Sheriff's Office",),
        event_types=("animal rescue",),
        stories=(existing,),
    )
    assert result.relationship is StoryRelationshipType.NEW_STORY


def test_registry_prioritizes_follow_up_over_resolver_merge(tmp_path):
    registry = StoryRegistry(tmp_path / "registry.json")
    first_story = registry.resolve_article(
        event_key="stuart-cat-rescue",
        title="Deputies rescue 80 cats from Stuart home",
        facts=("80 cats", "cats rescued", "animal cruelty"),
        locations=("Stuart",),
        agencies=("Martin County Sheriff's Office",),
        event_types=("animal rescue",),
        entities=("Gail Giustino",),
    )
    second_story = registry.resolve_article(
        event_key="stuart-animal-cruelty-arrest",
        title="Woman arrested after 80 cats rescued from Stuart home",
        facts=("80 cats", "animal cruelty", "arrest made"),
        locations=("Stuart",),
        agencies=("Martin County Sheriff's Office",),
        event_types=("animal rescue",),
        entities=("Gail Giustino",),
    )

    assert second_story == first_story
    assert registry.last_decision["relationship"] == "follow_up"
    assert registry.get_story(first_story)["relationship_history"][-1]["relationship"] == "follow_up"


def test_registry_keeps_duplicate_milestone_as_same_event(tmp_path):
    registry = StoryRegistry(tmp_path / "registry.json")
    first_story = registry.resolve_article(
        event_key="stuart-hoarding-arrest-primary",
        title="Woman arrested after 80 cats rescued from Stuart home",
        facts=("80 cats", "animal cruelty", "arrest made"),
        locations=("Stuart",),
        agencies=("Martin County Sheriff's Office",),
        event_types=("animal rescue",),
        entities=("Gail Giustino",),
    )
    second_story = registry.resolve_article(
        event_key="stuart-hoarding-arrest-syndicated",
        title="Stuart woman arrested after deputies rescue 80 cats from home",
        facts=("80 cats", "animal cruelty", "arrest made"),
        locations=("Stuart",),
        agencies=("Martin County Sheriff's Office",),
        event_types=("animal rescue",),
        entities=("Gail Giustino",),
    )

    assert second_story == first_story
    assert registry.last_decision["relationship"] == "same_event"
