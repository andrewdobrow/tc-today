from __future__ import annotations

import importlib
import json
import os
import sys
import types
from datetime import datetime, timezone
from email.utils import format_datetime

import pytest


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
                    create=lambda **kwargs: (_ for _ in ()).throw(
                        RuntimeError("unexpected model call")
                    )
                )

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic

    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


class _Response:
    def __init__(self, text: str):
        self.content = [types.SimpleNamespace(text=text)]


class _Messages:
    def __init__(self, text: str):
        self.text = text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Response(self.text)


class _Client:
    def __init__(self, text: str):
        self.messages = _Messages(text)


SOURCE_TITLE = (
    "Investigators reveal horrific home conditions in Fort Pierce baby death "
    "case; arrests made - WPEC"
)
SOURCE_URL = (
    "https://cbs12.com/news/local/investigators-reveal-horrific-home-conditions-"
    "in-fort-pierce-baby-death-case-arrests-made-three-month-old-3-mobile-"
    "july-27-2026"
)
SOURCE_TEXT = (
    "The St. Lucie County Sheriff's Office is sharing new details about the "
    "investigation into the death of a three-month-old boy in Fort Pierce, "
    "including why it took nearly a year to make arrests and the conditions "
    "investigators say they found inside the mobile home where the child lived. "
    "The infant's mother, Nicole Maxwell, her father Robert Maxwell, and his "
    "girlfriend Vikki Koon were arrested and charged with aggravated manslaughter "
    "and child abuse. Investigators say the baby died from dehydration and "
    "malnutrition last August, and the medical examiner later ruled the death a "
    "homicide. Detective Jennifer Diaz said the home was extremely hot, had a bug "
    "infestation and lacked food."
)
BAD_BODY = (
    "Detective Jennifer Diaz of the St. Lucie County Sheriff's Office described "
    "the mobile home in the 800 block of Silverstream Circle in Fort Pierce as "
    "mostly uninhabitable. The house was extremely hot, there was a bug "
    "infestation in the home, a lack of food, and the home was unsafe for walking."
    "\n\nDiaz said it took nearly a year for charges to be brought against the caregivers."
)
GOOD_BODY = (
    "Nearly a year after a 3-month-old boy died from dehydration and malnutrition "
    "in a Fort Pierce mobile home, St. Lucie County investigators are revealing "
    "new details about the conditions inside the residence and why three caregivers "
    "were not arrested until this month."
    "\n\nDetective Jennifer Diaz said the home was extremely hot, infested with bugs and "
    "unsafe to walk through."
)


def _source(title: str = SOURCE_TITLE):
    return {
        "title": title,
        "summary": SOURCE_TEXT,
        "article_text": SOURCE_TEXT,
        "published": format_datetime(datetime.now(timezone.utc)),
        "source_quality": "full",
        "source_type": "full_source",
        "hero_eligible": "yes",
        "category_match_score": 99,
        "link": SOURCE_URL,
        "image_url": "https://example.com/story-photo.jpg",
        "feed_url": "https://example.com/rss",
    }


def _generated_payload(body: str):
    return json.dumps(
        {
            "hero": {
                "headline": (
                    "St. Lucie detective describes conditions in Fort Pierce "
                    "mobile home where infant died"
                ),
                "body": body,
                "urgency_score": 8,
                "published": format_datetime(datetime.now(timezone.utc)),
                "source_index": 1,
            },
            "cards": [],
        }
    )


def test_exact_fort_pierce_source_is_classified_as_update():
    generate = _load_generate_module()
    assert generate._source_story_form(_source()) == "update"


def test_exact_live_article_lead_fails_original_event_context():
    generate = _load_generate_module()
    item = {
        "headline": (
            "St. Lucie detective describes conditions in Fort Pierce mobile home "
            "where infant died"
        ),
        "source_title": SOURCE_TITLE,
        "article_text": SOURCE_TEXT,
        "story_form": "update",
        "body": BAD_BODY,
    }

    diagnostics = generate._update_lead_diagnostics(item, item)

    assert diagnostics["required"] is True
    assert diagnostics["passed"] is False
    assert diagnostics["baseline_anchor"] == "fatality"
    assert diagnostics["baseline_present"] is False
    assert diagnostics["novelty_present"] is True
    assert "original_event_context_missing" in diagnostics["missing"]


def test_contextual_lead_states_original_incident_and_update():
    generate = _load_generate_module()
    item = {
        "headline": (
            "St. Lucie detective describes conditions in Fort Pierce mobile home "
            "where infant died"
        ),
        "source_title": SOURCE_TITLE,
        "article_text": SOURCE_TEXT,
        "story_form": "update",
        "body": GOOD_BODY,
    }

    diagnostics = generate._update_lead_diagnostics(item, item)

    assert diagnostics["required"] is True
    assert diagnostics["passed"] is True
    assert diagnostics["baseline_present"] is True
    assert diagnostics["novelty_present"] is True


def test_generation_prompt_marks_update_and_requires_self_contained_lead(monkeypatch):
    generate = _load_generate_module()
    fake = _Client(_generated_payload(GOOD_BODY))
    monkeypatch.setattr(generate, "client", fake)
    monkeypatch.setattr(generate, "load_archive", lambda *args, **kwargs: [])

    data = generate.generate_category_content("crime", "Crime & Safety", [_source()])

    prompt = fake.messages.calls[0]["messages"][0]["content"]
    assert "[story_form:update]" in prompt
    assert "the FIRST paragraph must explicitly state BOTH" in prompt
    assert "The lead must make sense without the headline" in prompt
    assert data["hero"]["story_form"] == "update"
    assert data["hero"]["headline"].startswith("St. Lucie detective")


def test_contextless_update_hero_triggers_fail_closed_retry_signal(monkeypatch):
    generate = _load_generate_module()
    fake = _Client(_generated_payload(BAD_BODY))
    monkeypatch.setattr(generate, "client", fake)
    monkeypatch.setattr(generate, "load_archive", lambda *args, **kwargs: [])

    with pytest.raises(generate.ContextualUpdateLeadError, match="original_event_context_missing"):
        generate.generate_category_content("crime", "Crime & Safety", [_source()])


def test_error_code_is_specific_to_contextless_update_lead():
    generate = _load_generate_module()
    exc = generate.ContextualUpdateLeadError("Contextless update lead for hero")
    assert generate._category_generation_error_code(exc) == "contextless_update_lead"


def test_homepage_guard_suppresses_existing_bad_generated_article():
    generate = _load_generate_module()
    bad = {
        "headline": (
            "St. Lucie detective describes conditions in Fort Pierce mobile home "
            "where infant died"
        ),
        "body": BAD_BODY,
        "teaser": BAD_BODY,
        "category_key": "crime",
        "slug": (
            "2026-07-28-st-lucie-detective-describes-conditions-in-fort-pierce-"
            "mobile-home-where-infant"
        ),
    }
    ordinary = {
        "headline": "Fort Pierce police arrest two after traffic stop",
        "body": "Fort Pierce police arrested two people Tuesday after a traffic stop.",
        "category_key": "crime",
    }

    kept, rejected = generate._filter_contextless_update_live_placements([bad, ordinary])

    assert kept == [ordinary]
    assert len(rejected) == 1
    assert rejected[0]["reason"] == "contextless_update_lead"
    assert rejected[0]["baseline_anchor"] == "fatality"


def test_custom_article_is_never_suppressed_by_update_lead_guard():
    generate = _load_generate_module()
    custom = {
        "headline": (
            "St. Lucie detective describes conditions in Fort Pierce mobile home "
            "where infant died"
        ),
        "body": BAD_BODY,
        "is_custom": True,
        "authoritative_custom": True,
    }

    kept, rejected = generate._filter_contextless_update_live_placements([custom])

    assert kept == [custom]
    assert rejected == []


def test_category_cache_version_is_scoped_to_article_prompt_change():
    generate = _load_generate_module()
    assert generate.GENERATION_PROMPT_VERSION == "v1.9.4-incremental-generation-1"
    assert generate.CATEGORY_GENERATION_PROMPT_VERSION == "v1.11.8.4-contextual-update-leads"


def test_standard_archive_entry_does_not_read_article_body(monkeypatch):
    generate = _load_generate_module()
    monkeypatch.setattr(
        generate,
        "_archive_article_body",
        lambda entry: (_ for _ in ()).throw(AssertionError("standard story should not read HTML")),
    )
    entry = {
        "headline": "Fort Pierce police arrest two after traffic stop",
        "slug": "ordinary-story",
    }

    assert generate._archive_entry_has_contextless_update_lead(entry) is False


def test_budgeted_generation_retries_contextless_update_hero(monkeypatch):
    generate = _load_generate_module()
    calls = []

    def fake_generate(*args, **kwargs):
        calls.append(kwargs["request_timeout_seconds"])
        if len(calls) == 1:
            raise generate.ContextualUpdateLeadError(
                "Contextless update lead for hero: original_event_context_missing"
            )
        return {
            "hero": {"headline": "Corrected update", "body": GOOD_BODY},
            "cards": [],
            "_contextual_update_lead_rejections": [],
        }

    monkeypatch.setattr(generate, "generate_category_content", fake_generate)
    monkeypatch.setattr(generate, "CATEGORY_GENERATION_BUDGET_SECONDS", 30.0)
    monkeypatch.setattr(generate, "CATEGORY_MODEL_CALL_TIMEOUT_SECONDS", 20.0)
    monkeypatch.setattr(generate, "CATEGORY_GENERATION_MIN_RETRY_SECONDS", 1.0)

    data, diagnostics = generate._run_category_generation_with_budget(
        "crime", "Crime & Safety", [_source()]
    )

    assert data["hero"]["headline"] == "Corrected update"
    assert diagnostics["status"] == "success"
    assert diagnostics["attempt_count"] == 2
    assert diagnostics["attempts"][0]["result"] == "contextless_update_lead"
    assert diagnostics["attempts"][1]["result"] == "success"


def test_category_generation_report_counts_contextual_lead_rejections():
    generate = _load_generate_module()
    report = generate._build_category_generation_report(
        [
            {
                "category_key": "crime",
                "status": "generated_live",
                "attempt_count": 2,
                "model_elapsed_seconds": 12.0,
                "archive_recovery_requested": False,
                "contextual_update_lead_rejection_count": 1,
            }
        ]
    )

    assert report["summary"]["contextual_update_lead_rejection_count"] == 1


def test_release_version_and_report_schema_are_bumped():
    generate = _load_generate_module()
    observability = importlib.import_module("tct_engine.observability")

    assert generate.CATEGORY_GENERATION_REPORT_SCHEMA_VERSION == 3
    assert observability.ENGINE_VERSION == "1.11.8.4.1"
    assert observability.ENGINE_RELEASE == "first-responder-image-fallback-hotfix"
    assert observability.OBSERVABILITY_SCHEMA_VERSION == 16
