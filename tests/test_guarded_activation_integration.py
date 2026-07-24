from __future__ import annotations

from copy import deepcopy
import importlib
import os
import sys
import types

from tct_engine import ActivationConfig, EngineMode, build_activation_run


def _load_generate_module():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser

    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(
                    create=lambda *args, **kwargs: None
                )

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic

    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def _clean_health():
    return {
        "status": "clean",
        "quarantined_story_count": 0,
        "remaining_exact_duplicate_title_groups": 0,
        "remaining_publisher_title_duplicate_groups": 0,
        "remaining_source_identity_groups": 0,
        "remaining_incident_identity_groups": 0,
    }


def _run(mode: EngineMode, *, max_actions: int = 8, kill_switch: bool = False):
    return build_activation_run(
        [],
        config=ActivationConfig(
            requested_mode=mode,
            max_actions_per_run=max_actions,
            kill_switch=kill_switch,
        ),
        previous_regression_report={"production_gate_passed": True},
        registry_health=_clean_health(),
    )


def _archive_story():
    return {
        "headline": "Stuart woman arrested in animal hoarding case",
        "slug": "prior-hoarding-arrest",
        "date": "2026-07-23",
        "category": "crime",
        "category_key": "crime",
        "teaser": (
            "A Stuart woman was arrested on animal cruelty charges after "
            "deputies rescued 80 cats."
        ),
        "link": "https://example.com/prior-hoarding-arrest",
    }


def _duplicate_item(slug: str = "live-hoarding-arrest"):
    return {
        "headline": "Stuart woman arrested in animal hoarding case",
        "source_title": "Stuart woman arrested in animal hoarding case",
        "slug": slug,
        "date": "2026-07-24",
        "category": "crime",
        "category_key": "crime",
        "teaser": (
            "A Stuart woman was arrested on animal cruelty charges after "
            "deputies rescued 80 cats."
        ),
        "link": f"https://example.com/{slug}",
    }


def test_quiet_cycle_can_produce_zero_recommendations_and_actions():
    generate = _load_generate_module()
    categories = [{
        "category_key": "crime",
        "hero": {
            "headline": "Fort Pierce opens a new neighborhood park",
            "slug": "new-park",
            "date": "2026-07-24",
            "category_key": "crime",
            "teaser": "A new neighborhood park opened after a ribbon cutting.",
            "link": "https://example.com/new-park",
        },
        "cards": [],
    }]

    run, suppressions = generate._apply_editorial_activation(
        categories,
        _run(EngineMode.ENFORCE),
        published_archive=[_archive_story()],
        current_customs=[],
    )

    assert run.recommendations == []
    assert run.applied == []
    assert suppressions == []
    assert categories[0]["hero"]["slug"] == "new-park"


def test_guarded_duplicate_is_enforced_and_logged_by_activation_controller():
    generate = _load_generate_module()
    categories = [{
        "category_key": "crime",
        "hero": _duplicate_item(),
        "cards": [],
    }]

    run, suppressions = generate._apply_editorial_activation(
        categories,
        _run(EngineMode.ENFORCE),
        published_archive=[_archive_story()],
        current_customs=[],
    )

    assert categories[0]["hero"] is None
    assert len(run.recommendations) == 1
    assert run.recommendations[0].evidence == "guarded_same_story_stage_95"
    assert len(run.applied) == 1
    assert run.applied[0]["activation_managed"] is True
    assert run.applied[0]["placement"] == "hero"
    assert len(suppressions) == 1
    assert suppressions[0]["action_taken"] is True
    assert suppressions[0]["activation_evidence"] == "guarded_same_story_stage_95"


def test_recommend_mode_surfaces_guarded_action_without_mutating_publication():
    generate = _load_generate_module()
    categories = [{
        "category_key": "crime",
        "hero": _duplicate_item(),
        "cards": [],
    }]
    original = deepcopy(categories)

    run, suppressions = generate._apply_editorial_activation(
        categories,
        _run(EngineMode.RECOMMEND),
        published_archive=[_archive_story()],
        current_customs=[],
    )

    assert categories == original
    assert len(run.recommendations) == 1
    assert run.applied == []
    assert suppressions == []


def test_kill_switch_disables_guarded_publication_actions():
    generate = _load_generate_module()
    categories = [{
        "category_key": "crime",
        "hero": _duplicate_item(),
        "cards": [],
    }]
    original = deepcopy(categories)

    run, suppressions = generate._apply_editorial_activation(
        categories,
        _run(EngineMode.ENFORCE, kill_switch=True),
        published_archive=[_archive_story()],
        current_customs=[],
    )

    assert run.preflight.effective_mode is EngineMode.SHADOW
    assert categories == original
    assert len(run.recommendations) == 1
    assert run.applied == []
    assert suppressions == []


def test_combined_guarded_actions_respect_circuit_breaker_without_partial_mutation():
    generate = _load_generate_module()
    categories = [
        {
            "category_key": category_key,
            "hero": _duplicate_item(f"duplicate-{category_key}"),
            "cards": [],
        }
        for category_key in ("crime", "martin")
    ]
    original = deepcopy(categories)

    run, suppressions = generate._apply_editorial_activation(
        categories,
        _run(EngineMode.ENFORCE, max_actions=1),
        published_archive=[_archive_story()],
        current_customs=[],
    )

    assert run.circuit_breaker_tripped is True
    assert run.preflight.effective_mode is EngineMode.SHADOW
    assert categories == original
    assert run.applied == []
    assert suppressions == []
