import json
from pathlib import Path


def _cases():
    path = Path(__file__).parent / "fixtures" / "canonical_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_known_event_keys_are_stable(engine):
    for case in _cases():
        existing_text = engine._story_text(case["existing"])
        incoming_text = engine._story_text(case["incoming"])
        assert engine._known_event_key(existing_text) == case["expected_key"], case["id"]
        assert engine._known_event_key(incoming_text) == case["expected_key"], case["id"]


def test_evolved_headline_does_not_invalidate_permanent_slug(engine):
    case = _cases()[0]
    assert engine._published_slug_still_matches_entry(case["existing"]) is True


def test_hard_identity_gate_accepts_known_same_events(engine):
    for case in _cases():
        assert engine._hard_canonical_identity_gate(case["incoming"], case["existing"]) is case["expected_gate"], case["id"]


def test_relationship_classifier_short_circuits_known_events_without_ai(engine):
    for case in _cases():
        assert engine.classify_story_relationship(case["incoming"], case["existing"]) == case["expected_relationship"], case["id"]


def test_unrelated_similar_local_crashes_do_not_merge(engine):
    existing = {
        "slug": "2026-07-20-child-killed-another-injured-in-bicycle-crash-with-fedex-truck-in-fort-pierce",
        "headline": "Community holds vigil for 9-year-old killed in East Midway Road dirt bike crash",
        "teaser": "The crash involved a FedEx truck and two children.",
        "body": "The collision happened on East Midway Road."
    }
    incoming = {
        "headline": "Motorcyclist injured in crash on U.S. 1 in Vero Beach",
        "teaser": "Police investigated a separate traffic crash in Indian River County.",
        "body": "The adult rider was taken to a hospital."
    }
    assert engine._hard_canonical_identity_gate(incoming, existing) is False


def test_slug_drift_is_rejected_for_unrelated_replacement_content(engine):
    corrupted = {
        "slug": "2026-07-20-child-killed-another-injured-in-bicycle-crash-with-fedex-truck-in-fort-pierce",
        "headline": "Port St. Lucie approves new downtown development plan",
        "teaser": "City Council approved a mixed-use project.",
        "body": "The development includes apartments, retail space and road improvements."
    }
    assert engine._published_slug_still_matches_entry(corrupted) is False
