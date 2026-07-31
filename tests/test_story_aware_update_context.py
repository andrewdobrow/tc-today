from __future__ import annotations

import importlib
import json
import os
import sys
import types
from datetime import datetime, timezone
from email.utils import format_datetime

import pytest


def _load_generate():
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


CANONICAL = {
    "slug": "2026-07-25-3-arrested-in-death-of-3-month-old-in-st-lucie-county",
    "headline": (
        "3 arrested in death of 3-month-old in St. Lucie County from "
        "dehydration and malnutrition"
    ),
    "teaser": (
        "Three caregivers were arrested nearly a year after a 3-month-old boy "
        "died in Fort Pierce from dehydration and malnutrition."
    ),
    "body": (
        "Three people were arrested nearly a year after a 3-month-old boy died "
        "in Fort Pierce. The medical examiner ruled the death a homicide caused "
        "by dehydration and malnutrition.\n\n"
        "Nicole Maxwell, Robert Maxwell and Vikki Koon were charged with "
        "aggravated manslaughter of a child and aggravated child abuse."
    ),
    "date": "2026-07-25",
    "first_published": "Fri, 24 Jul 2026 21:09:00 -0400",
    "editorial_story_id": "story_001234",
    "legacy_identity_status": "identified",
    "ranking_eligible": True,
}

SOURCE_TITLE = (
    "Neighbor on Silverstream Circle says community worried about child before "
    "Fort Pierce baby death"
)
SOURCE_TEXT = (
    "A neighbor on Silverstream Circle said people in the community had worried "
    "about the child before the case became public. The neighbor described prior "
    "concerns about conditions around the home and the children who lived there."
)

BAD_LEAD = (
    "A neighbor on Silverstream Circle said the community had worried about the "
    "child before the case drew public attention and described concerns around "
    "the Fort Pierce home."
)
GOOD_LEAD = (
    "After a 3-month-old Fort Pierce boy died from dehydration and malnutrition "
    "and three caregivers were arrested, a Silverstream Circle neighbor said "
    "residents had worried about the child before the case became public."
)


def _source():
    return {
        "title": SOURCE_TITLE,
        "article_text": SOURCE_TEXT,
        "summary": SOURCE_TEXT,
        "published": format_datetime(datetime.now(timezone.utc)),
        "source_quality": "full",
        "source_type": "full_source",
        "hero_eligible": "yes",
        "category_match_score": 99,
        "link": "https://example.com/silverstream-neighbor-update",
        "image_url": "https://example.com/photo.jpg",
        "feed_url": "https://example.com/rss",
        "editorial_story_id": "story_001234",
        "_editorial_story_id": "story_001234",
        "_editorial_route": "generate_new",
        "_editorial_relationship": "new_story",
    }


class _Response:
    def __init__(self, text):
        self.content = [types.SimpleNamespace(text=text)]


class _Messages:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Response(self.text)


class _Client:
    def __init__(self, text):
        self.messages = _Messages(text)


def _payload(body):
    return json.dumps({
        "hero": {
            "headline": (
                "Silverstream Circle neighbor says community worried before "
                "Fort Pierce infant death"
            ),
            "body": body + "\n\nThe neighbor described concerns around the home.",
            "urgency_score": 6,
            "published": format_datetime(datetime.now(timezone.utc)),
            "source_index": 1,
        },
        "cards": [],
    })


def test_existing_canonical_makes_headline_reframe_an_update_before_generation():
    generate = _load_generate()
    source = _source()
    identity_index = types.SimpleNamespace(safe_story_ids={"story_001234"})
    ledger = generate._build_canonical_publication_ledger(
        [dict(CANONICAL)], identity_index
    )

    bindings = generate._prepare_story_aware_update_context(
        [source], [dict(CANONICAL)], ledger, identity_index
    )

    assert len(bindings) == 1
    assert source["story_form"] == "update"
    assert source["_canonical_context_slug"] == CANONICAL["slug"]
    assert source["_canonical_context_headline"] == CANONICAL["headline"]
    assert "died" in source["_canonical_context_body"]
    assert bindings[0]["canonical_slug"] == CANONICAL["slug"]


def test_neighbor_reaction_lead_fails_without_original_death_and_arrest_context():
    generate = _load_generate()
    source = _source()
    generate._attach_canonical_update_context(source, dict(CANONICAL), "story")
    item = {
        "headline": SOURCE_TITLE,
        "body": BAD_LEAD,
        "story_form": "update",
    }

    diagnostics = generate._update_lead_diagnostics(item, source)

    assert diagnostics["required"] is True
    assert diagnostics["passed"] is False
    assert diagnostics["novelty_anchor"] == "community_reaction"
    assert diagnostics["novelty_present"] is True
    assert diagnostics["baseline_anchor"] == "fatality"
    assert "original_event_context_missing" in diagnostics["missing"]


def test_contextual_neighbor_reaction_lead_passes_first_time_reader_contract():
    generate = _load_generate()
    source = _source()
    generate._attach_canonical_update_context(source, dict(CANONICAL), "story")
    item = {
        "headline": SOURCE_TITLE,
        "body": GOOD_LEAD,
        "story_form": "update",
    }

    diagnostics = generate._update_lead_diagnostics(item, source)

    assert diagnostics["passed"] is True
    assert diagnostics["baseline_present"] is True
    assert diagnostics["novelty_present"] is True
    assert len(diagnostics["baseline_context_hits"]) >= 2


def test_category_prompt_receives_original_story_and_current_update_separately(monkeypatch):
    generate = _load_generate()
    source = _source()
    generate._attach_canonical_update_context(source, dict(CANONICAL), "story")
    fake = _Client(_payload(GOOD_LEAD))
    monkeypatch.setattr(generate, "client", fake)
    monkeypatch.setattr(generate, "load_archive", lambda *args, **kwargs: [])

    data = generate.generate_category_content("crime", "Crime & Safety", [source])

    prompt = fake.messages.calls[0]["messages"][0]["content"]
    assert "[story_form:update]" in prompt
    assert "ORIGINAL PUBLISHED STORY:" in prompt
    assert CANONICAL["headline"] in prompt
    assert "CURRENT UPDATE SOURCE:" in prompt
    assert data["hero"]["_canonical_context_slug"] == CANONICAL["slug"]


def test_write_barrier_rejects_contextless_replacement_even_when_registry_called_it_new():
    generate = _load_generate()
    item = _source()
    item.update({
        "headline": SOURCE_TITLE,
        "source_headline": SOURCE_TITLE,
        "body": BAD_LEAD,
        "story_form": "update",
    })

    diagnostics = generate._update_replacement_diagnostics(item, dict(CANONICAL))

    assert diagnostics["passed"] is False
    assert "original_event_context_missing" in diagnostics["missing"]


def test_write_barrier_accepts_contextual_replacement():
    generate = _load_generate()
    item = _source()
    item.update({
        "headline": SOURCE_TITLE,
        "source_headline": SOURCE_TITLE,
        "body": GOOD_LEAD,
        "story_form": "update",
    })

    diagnostics = generate._update_replacement_diagnostics(item, dict(CANONICAL))

    assert diagnostics["passed"] is True
