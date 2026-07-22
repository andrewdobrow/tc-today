def test_shadow_and_publisher_can_share_one_identity_contract(engine):
    """Contract test for the upcoming refactor.

    The production resolver and shadow diagnostics should consume this same result,
    rather than recomputing event identity independently.
    """
    existing = {
        "slug": "2026-07-20-child-killed-another-injured-in-bicycle-crash-with-fedex-truck-in-fort-pierce",
        "headline": "Community holds vigil for 9-year-old killed in East Midway Road dirt bike crash",
        "teaser": "The FedEx collision killed a 9-year-old and injured a 12-year-old.",
        "body": "The crash happened on East Midway Road."
    }
    incoming = {
        "headline": "12-year-old released from hospital after East Midway Road dirt bike crash",
        "teaser": "The child was injured in the FedEx collision that killed a 9-year-old.",
        "body": "The same St. Lucie County incident remains under investigation."
    }
    result = {
        "known_event_key": engine._known_event_key(engine._story_text(incoming)),
        "canonical_valid": engine._published_slug_still_matches_entry(existing),
        "identity_gate": engine._hard_canonical_identity_gate(incoming, existing),
        "relationship": engine.classify_story_relationship(incoming, existing),
    }
    assert result == {
        "known_event_key": "2026-07-east-midway-dirt-bike-fedex-crash",
        "canonical_valid": True,
        "identity_gate": True,
        "relationship": "SAME_EVENT",
    }
