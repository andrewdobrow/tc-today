from copy import deepcopy

from tct_engine import (
    ActivationAction,
    ActivationConfig,
    EngineMode,
    apply_activation_to_categories,
    build_activation_preflight,
    build_activation_run,
    recommend_activation_action,
)


def clean_health():
    return {
        "status": "clean",
        "quarantined_story_count": 0,
        "remaining_exact_duplicate_title_groups": 0,
        "remaining_publisher_title_duplicate_groups": 0,
        "remaining_source_identity_groups": 0,
        "remaining_incident_identity_groups": 0,
    }


def row(**overrides):
    value = {
        "route": "skip",
        "relationship": "same_event",
        "relationship_confidence": 1.0,
        "headline": "Big Taste of Martin County returns - WPTV",
        "source_url": "https://news.google.com/rss/articles/example?oc=5",
        "incoming_article_id": "incoming",
        "target_article_id": "canonical",
        "story_id": "story_000001",
        "incoming_is_custom": False,
        "canonical_is_custom": False,
        "decision_trace": ["Exact normalized title match: true", "Confidence: 1.00"],
    }
    value.update(overrides)
    return value


def test_environment_defaults_to_shadow_and_parses_controls():
    default = ActivationConfig.from_environment({})
    assert default.requested_mode is EngineMode.SHADOW
    assert default.max_actions_per_run == 8
    assert default.kill_switch is False

    configured = ActivationConfig.from_environment({
        "TCT_ENGINE_MODE": "ENFORCE",
        "TCT_ENGINE_MAX_ACTIONS": "3",
        "TCT_ENGINE_KILL_SWITCH": "true",
    })
    assert configured.requested_mode is EngineMode.ENFORCE
    assert configured.max_actions_per_run == 3
    assert configured.kill_switch is True


def test_enforce_preflight_requires_previous_gate_and_clean_registry():
    config = ActivationConfig(requested_mode=EngineMode.ENFORCE)
    failed = build_activation_preflight(
        config,
        previous_regression_report={"production_gate_passed": False},
        registry_health=clean_health(),
    )
    assert failed.effective_mode is EngineMode.SHADOW
    assert "previous production regression gate did not pass" in failed.reasons

    passed = build_activation_preflight(
        config,
        previous_regression_report={"production_gate_passed": True},
        registry_health=clean_health(),
    )
    assert passed.passed is True
    assert passed.effective_mode is EngineMode.ENFORCE


def test_kill_switch_forces_enforce_request_back_to_shadow():
    config = ActivationConfig(requested_mode=EngineMode.ENFORCE, kill_switch=True)
    preflight = build_activation_preflight(
        config,
        previous_regression_report={"production_gate_passed": True},
        registry_health=clean_health(),
    )
    assert preflight.effective_mode is EngineMode.SHADOW
    assert "kill switch enabled" in preflight.reasons


def test_custom_canonical_protection_is_enforceable_even_with_exact_event_trace():
    recommendation = recommend_activation_action(row(
        canonical_is_custom=True,
        decision_trace=["Exact event-key mapping: true"],
    ))
    assert recommendation.action is ActivationAction.PROTECT_CUSTOM_CANONICAL
    assert recommendation.enforceable is True
    assert recommendation.evidence == "custom_canonical_protection"


def test_exact_title_and_source_article_identity_are_allowlisted():
    title = recommend_activation_action(row())
    assert title.action is ActivationAction.SUPPRESS_DUPLICATE
    assert title.evidence == "exact_normalized_title_identity"

    source = recommend_activation_action(row(
        decision_trace=["Exact source article identity: true", "Confidence: 1.00"],
    ))
    assert source.action is ActivationAction.SUPPRESS_DUPLICATE
    assert source.evidence == "exact_safe_source_article_identity"


def test_semantic_and_same_canonical_candidate_remain_observe_only():
    for trace in (
        ["Resolver confidence: 0.99", "Shared facts: 4"],
        ["Exact event-key mapping: true", "Confidence: 1.00"],
        ["Deterministic incident identity: true", "Confidence: 1.00"],
    ):
        recommendation = recommend_activation_action(row(decision_trace=trace))
        assert recommendation.action is ActivationAction.NONE

    canonical_repeat = recommend_activation_action(row(
        incoming_article_id="same",
        target_article_id="same",
    ))
    assert canonical_repeat.action is ActivationAction.NONE


def test_recommend_mode_never_mutates_live_categories():
    categories = [{
        "category_key": "business",
        "hero": {
            "headline": "Rewritten headline",
            "source_title": "Big Taste of Martin County returns - WPTV",
            "link": "https://news.google.com/rss/articles/example?oc=5",
        },
        "cards": [],
    }]
    original = deepcopy(categories)
    run = build_activation_run(
        [row()],
        config=ActivationConfig(requested_mode=EngineMode.RECOMMEND),
        previous_regression_report={},
        registry_health={},
    )
    apply_activation_to_categories(categories, run)
    assert categories == original
    assert run.applied == []
    assert run.recommendations


def test_enforce_removes_allowlisted_hero_and_promotes_next_card():
    categories = [{
        "category_key": "business",
        "hero": {
            "headline": "Rewritten duplicate",
            "source_title": "Big Taste of Martin County returns - WPTV",
            "link": "https://news.google.com/rss/articles/example?oc=5",
        },
        "cards": [{
            "headline": "Different local story",
            "source_title": "Different local story",
            "link": "https://example.com/news/different-story",
        }],
    }]
    run = build_activation_run(
        [row()],
        config=ActivationConfig(requested_mode=EngineMode.ENFORCE),
        previous_regression_report={"production_gate_passed": True},
        registry_health=clean_health(),
    )
    apply_activation_to_categories(categories, run)
    assert categories[0]["hero"]["headline"] == "Different local story"
    assert categories[0]["cards"] == []
    assert len(run.applied) == 1
    assert run.applied[0]["placement"] == "hero"
    assert run.publication_behavior_changed is True


def test_actual_placement_circuit_breaker_restores_original_categories():
    categories = [
        {
            "category_key": key,
            "hero": {
                "headline": "Rewritten duplicate",
                "source_title": "Big Taste of Martin County returns - WPTV",
                "link": "https://news.google.com/rss/articles/example?oc=5",
            },
            "cards": [],
        }
        for key in ("business", "martin")
    ]
    original = deepcopy(categories)
    run = build_activation_run(
        [row()],
        config=ActivationConfig(requested_mode=EngineMode.ENFORCE, max_actions_per_run=1),
        previous_regression_report={"production_gate_passed": True},
        registry_health=clean_health(),
    )
    apply_activation_to_categories(categories, run)
    assert run.circuit_breaker_tripped is True
    assert run.preflight.effective_mode is EngineMode.SHADOW
    assert categories == original
    assert run.applied == []
