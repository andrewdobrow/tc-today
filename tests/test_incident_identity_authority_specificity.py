from __future__ import annotations

import importlib
import os
import sys
import types

from tct_engine.event_identity_authority import authorize_exact_identity_keys
from tct_engine.incident_identity import incident_anchor_write_authoritative
from tct_engine.registry_repair import is_broad_event_class_key


def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda *args, **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def _stuart_custom():
    return {
        "slug": "2026-07-20-more-than-70-animals-found-in-stuart-home-during-large-scale-hoarding-response",
        "headline": "More Than 70 Animals Found in Stuart Home During Large-Scale Hoarding Response",
        "teaser": (
            "77-year-old Gail Giustino was arrested after Martin County authorities "
            "found more than 70 animals at a Stuart home."
        ),
        "body": (
            "Gail Giustino was arrested after deputies found more than 70 animals "
            "at her Stuart home in Martin County. Authorities described the case as "
            "a large-scale animal hoarding response."
        ),
        "date": "2026-07-20",
        "first_published": "Mon, 20 Jul 2026 12:00:00 -0400",
        "source_url": "https://example.com/gail-giustino-stuart-hoarding",
        "category_key": "martin",
        "is_custom": True,
        "authoritative_custom": True,
        "incident_anchor_key": "mass-animal-hoarding:martin-county",
        "editorial_story_id": "custom:giustino",
        "ranking_eligible": True,
        "legacy_identity_status": "identified",
    }


def _palm_city_collies():
    return {
        "slug": "2026-08-25-all-36-border-collies-surrendered-in-palm-city-cruelty-case-adoptions-open-sept",
        "headline": (
            "Woman facing 72 charges in Palm City hoarding case pleads not guilty "
            "after surrender of 36 Border Collies"
        ),
        "teaser": (
            "Paige O'Donnell pleaded not guilty after 36 Border Collies were removed "
            "from a Southwest Alligator Street home in Palm City."
        ),
        "body": (
            "Paige O'Donnell is facing 72 charges in a separate Palm City animal "
            "hoarding case. Thirty-six Border Collies were removed from the Southwest "
            "Alligator Street home in Martin County and later surrendered for adoption."
        ),
        "date": "2026-09-03",
        "first_published": "Thu, 03 Sep 2026 12:00:00 -0400",
        "source_url": "https://example.com/palm-city-border-collies-plea",
        "category_key": "martin",
        "incident_anchor_key": "mass-animal-hoarding:martin-county",
        "editorial_story_id": "story_palm_city_collies",
        "ranking_eligible": True,
        "legacy_identity_status": "identified",
    }


def test_area_only_mass_hoarding_anchor_is_candidate_only_everywhere():
    anchor = "mass-animal-hoarding:martin-county"
    assert incident_anchor_write_authoritative(anchor) is False
    assert is_broad_event_class_key(anchor) is True
    decision = authorize_exact_identity_keys([f"incident:{anchor}"])
    assert decision.outcome == "possible_relationship"
    assert decision.write_authorized is False
    assert decision.proof_type == "broad_structured_incident_key"


def test_named_missing_person_anchor_remains_exact_write_authority():
    anchor = "missing-person:michael-debevec"
    assert incident_anchor_write_authoritative(anchor) is True
    decision = authorize_exact_identity_keys([f"incident:{anchor}"])
    assert decision.outcome == "same_event_verified"
    assert decision.write_authorized is True
    assert decision.proof_type == "exact_structured_incident_key"


def test_exact_production_martin_hoarding_cases_do_not_custom_merge_or_redirect(tmp_path):
    g = _load_generate()
    custom = _stuart_custom()
    collies = _palm_city_collies()

    match, confidence, basis = g._find_authoritative_custom_incident_match(
        collies, archived_customs=[custom], current_customs=[]
    )
    assert match is None
    assert confidence == 0
    assert basis == ""

    (tmp_path / "articles").mkdir()
    cleaned, redirects = g.apply_canonical_story_cleanup(
        [custom.copy(), collies.copy()], tmp_path / "articles", tmp_path
    )
    assert {row["slug"] for row in cleaned} == {custom["slug"], collies["slug"]}
    assert not any(
        row.get("source_slug") == collies["slug"] for row in redirects
    )


def test_broad_incident_anchor_cannot_own_publication_ledger_or_final_surface(tmp_path):
    g = _load_generate()
    custom = _stuart_custom()
    collies = _palm_city_collies()
    ledger = g._build_canonical_publication_ledger([custom])

    target, basis, keys = g._canonical_publication_ledger_target(collies.copy(), ledger)
    assert f"incident:{custom['incident_anchor_key']}" in keys
    assert target is None
    assert basis == "candidate_only_uncorroborated_persistent_story_id"

    context = g._build_final_canonical_surface_context(
        [custom, collies],
        tmp_path,
        identity_index=types.SimpleNamespace(safe_story_ids=set(), all_story_ids=set()),
        redirect_map={},
    )
    assert custom["incident_anchor_key"] not in context["incident_anchor_canonical_slugs"]
    custom_identity = g._final_canonical_surface_identity(
        custom,
        f"https://treasurecoast.today/articles/{custom['slug']}.html",
        context,
    )
    collies_identity = g._final_canonical_surface_identity(
        collies,
        f"https://treasurecoast.today/articles/{collies['slug']}.html",
        context,
    )
    assert custom_identity["canonical_slug"] == custom["slug"]
    assert collies_identity["canonical_slug"] == collies["slug"]
