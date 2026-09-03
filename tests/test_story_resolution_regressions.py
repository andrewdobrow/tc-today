from pathlib import Path

from tct_engine.story_registry import StoryRegistry


def resolve(registry, *, event_key, title, facts, locations=(), agencies=(), event_types=()):
    return registry.resolve_article(
        event_key=event_key,
        title=title,
        facts=tuple(facts),
        locations=tuple(locations),
        agencies=tuple(agencies),
        event_types=tuple(event_types),
    )


def test_cat_rescue_and_later_arrest_merge(tmp_path):
    registry = StoryRegistry(Path(tmp_path) / "registry.json")

    first = resolve(
        registry,
        event_key="stuart-cat-rescue",
        title="Deputies rescue 80 cats from Stuart home",
        facts=("80 cats", "cats rescued", "animal cruelty"),
        locations=("Stuart",),
        agencies=("Martin County Sheriff's Office",),
        event_types=("animal rescue",),
    )
    follow_up = resolve(
        registry,
        event_key="stuart-animal-cruelty-arrest",
        title="Woman arrested after 80 cats rescued from Stuart home",
        facts=("80 cats", "animal cruelty", "arrest made"),
        locations=("Stuart",),
        agencies=("Martin County Sheriff's Office",),
        event_types=("animal rescue",),
    )

    assert first == follow_up


def test_crash_closure_and_reopening_merge(tmp_path):
    registry = StoryRegistry(Path(tmp_path) / "registry.json")

    first = resolve(
        registry,
        event_key="us1-crash-closure",
        title="Crash closes US 1 in Stuart",
        facts=("road closed", "2 people injured"),
        locations=("Stuart",),
        event_types=("traffic crash",),
    )
    follow_up = resolve(
        registry,
        event_key="us1-reopens-after-crash",
        title="US 1 reopens after earlier Stuart crash",
        facts=("road closed", "2 people injured"),
        locations=("Stuart",),
        event_types=("traffic crash",),
    )

    assert first == follow_up


def test_separate_crashes_on_same_road_do_not_merge_when_injury_counts_conflict(tmp_path):
    registry = StoryRegistry(Path(tmp_path) / "registry.json")

    morning = resolve(
        registry,
        event_key="us1-morning-crash",
        title="Morning crash closes US 1 in Stuart",
        facts=("road closed", "1 person injured"),
        locations=("Stuart",),
        event_types=("traffic crash",),
    )
    evening = resolve(
        registry,
        event_key="us1-evening-crash",
        title="Evening crash closes US 1 in Stuart",
        facts=("road closed", "2 people injured"),
        locations=("Stuart",),
        event_types=("traffic crash",),
    )

    assert morning != evening


def test_fires_at_different_businesses_do_not_merge(tmp_path):
    registry = StoryRegistry(Path(tmp_path) / "registry.json")

    walmart = resolve(
        registry,
        event_key="walmart-fire",
        title="Fire reported at Walmart in Stuart",
        facts=("fire reported", "no injuries reported"),
        locations=("Stuart",),
        event_types=("fire",),
    )
    publix = resolve(
        registry,
        event_key="publix-fire",
        title="Fire reported at Publix in Stuart",
        facts=("fire reported", "no injuries reported"),
        locations=("Stuart",),
        event_types=("fire",),
    )

    assert walmart != publix


def test_budget_meetings_in_different_counties_do_not_merge(tmp_path):
    registry = StoryRegistry(Path(tmp_path) / "registry.json")

    martin = resolve(
        registry,
        event_key="martin-budget-meeting",
        title="Martin County holds budget meeting",
        facts=("budget meeting",),
        locations=("Stuart",),
        agencies=("Martin County",),
        event_types=("government meeting",),
    )
    st_lucie = resolve(
        registry,
        event_key="st-lucie-budget-meeting",
        title="St. Lucie County holds budget meeting",
        facts=("budget meeting",),
        locations=("Port St. Lucie",),
        agencies=("St. Lucie County",),
        event_types=("government meeting",),
    )

    assert martin != st_lucie


def test_same_city_and_agency_without_shared_facts_is_not_enough(tmp_path):
    registry = StoryRegistry(Path(tmp_path) / "registry.json")

    crash = resolve(
        registry,
        event_key="stuart-bridge-crash",
        title="Crash reported near Stuart bridge",
        facts=("road closed",),
        locations=("Stuart",),
        agencies=("Martin County Sheriff's Office",),
        event_types=("traffic crash",),
    )
    arrest = resolve(
        registry,
        event_key="stuart-burglary-arrest",
        title="Deputies arrest burglary suspect in Stuart",
        facts=("arrest made",),
        locations=("Stuart",),
        agencies=("Martin County Sheriff's Office",),
        event_types=("burglary",),
    )

    assert crash != arrest


def test_exact_incident_specific_event_key_always_returns_existing_story(tmp_path):
    registry = StoryRegistry(Path(tmp_path) / "registry.json")

    # Missing-person city keys are a broad class and intentionally cannot own a
    # story mapping. Once the source/article-specific suffix establishes one
    # incident key, exact follow-up use of that key remains stable.
    event_key = "missing-person-vero-beach-a1b2c3d4e5"
    first = resolve(
        registry,
        event_key=event_key,
        title="Police search for missing Vero Beach resident",
        facts=("missing person",),
        locations=("Vero Beach",),
        event_types=("missing person",),
    )
    update = resolve(
        registry,
        event_key=event_key,
        title="Search continues for missing Vero Beach resident",
        facts=("missing person", "search continues"),
        locations=("Vero Beach",),
        event_types=("missing person",),
    )

    assert first == update


def test_registry_persists_story_grouping_across_reload(tmp_path):
    path = Path(tmp_path) / "registry.json"
    registry = StoryRegistry(path)

    first = resolve(
        registry,
        event_key="stuart-cat-rescue",
        title="Deputies rescue 80 cats from Stuart home",
        facts=("80 cats", "cats rescued", "animal cruelty"),
        locations=("Stuart",),
        agencies=("Martin County Sheriff's Office",),
        event_types=("animal rescue",),
    )

    reloaded = StoryRegistry(path)
    follow_up = resolve(
        reloaded,
        event_key="stuart-animal-cruelty-arrest",
        title="Woman arrested after 80 cats rescued from Stuart home",
        facts=("80 cats", "animal cruelty", "arrest made"),
        locations=("Stuart",),
        agencies=("Martin County Sheriff's Office",),
        event_types=("animal rescue",),
    )

    assert first == follow_up
