from tct_engine.story_resolver import StoryResolver
from tct_engine.local_relevance import classify_local_relevance

def story(**kw):
    base={"story_id":"story_1","status":"developing","facts":[],"locations":[],"agencies":[],"event_types":[],"entities":[],"events":[],"canonical_title":""}
    base.update(kw); return base

def test_rejects_same_topic_different_city():
    r=StoryResolver().resolve(event_key="fatal-crash-fort-pierce",title="Fatal crash in Fort Pierce",facts=["1 person died"],locations=["Fort Pierce"],agencies=["FHP"],event_types=["traffic crash"],entities=["US 1"],stories=[story(locations=["Stuart"],agencies=["FHP"],event_types=["traffic crash"],facts=["1 person died"],entities=["US 1"],canonical_title="Fatal crash in Stuart")])
    assert not r.merge

def test_merges_strong_same_incident():
    s=story(facts=["80 cats","cats rescued"],locations=["Stuart"],agencies=["Martin County Sheriff's Office"],event_types=["animal rescue"],entities=["Martin County Sheriff's Office"],events=["stuart-cat-hoarding"],canonical_title="80 cats rescued from Stuart home")
    r=StoryResolver().resolve(event_key="stuart-cat-hoarding-arrest",title="Woman arrested after 80 cats rescued from Stuart home",facts=["80 cats","cats rescued","arrest made"],locations=["Stuart"],agencies=["Martin County Sheriff's Office"],event_types=["animal rescue"],entities=["Martin County Sheriff's Office"],stories=[s])
    assert r.merge and r.confidence >= .78
    assert r.decision_trace

def test_local_relevance():
    assert classify_local_relevance(locations=["Port St. Lucie"]).score == 100
    assert classify_local_relevance(text="Florida lawmakers").score == 65
