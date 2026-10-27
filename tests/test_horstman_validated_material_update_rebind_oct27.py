"""Regression for Oct 27 Horstman custom canonical material update failure.

A validated new source can carry a fragmented feed-registry story ID while the
published custom article owns a different immutable `custom:...` story ID.
The canonical slug must come from the signed current-run materiality receipt,
not a headline similarity or speculative new-permalink path.
"""
from __future__ import annotations

import copy
import importlib

CUSTOM = "2026-10-26-st-lucie-detective-tyler-horstman-felony-dui-arrest"


def _canonical():
    return {
        "slug": CUSTOM,
        "canonical_slug": CUSTOM,
        "headline": "St. Lucie County Detective Tyler Horstman Arrested on Felony DUI Charge",
        "teaser": "Detective Tyler Horstman was arrested following a crash in an agency vehicle.",
        "body": "Investigators reported a crash involving a St. Lucie County detective.",
        "is_custom": True,
        "authoritative_custom": True,
        "editorial_story_id": "custom:820af698fc04d4ecc61c58f341673b64",
        "legacy_identity_status": "identified",
        "source_url": "",
    }


def _signed_source(g, canonical):
    decision = {
        "status": "validated",
        "action": g.SEMANTIC_ACTION_UPDATE,
        "recommended_action": g.SEMANTIC_ACTION_UPDATE,
        "selected_candidate_slug": canonical["slug"],
        "same_real_world_event": True,
        "material_new_update": True,
        "confidence": .97,
        "shared_anchors": ["St. Lucie County", "same October 26 DUI case"],
        "novel_facts": ["Sheriff's office reported a subsequent release on bond"],
        "reason": "The verified source advances the same named DUI case.",
        "validation_errors": [],
    }
    source = {
        "title": "St. Lucie County sheriff's deputy arrested on DUI charge after off-duty crash",
        "headline": "St. Lucie County Detective Horstman Released on $15,000 Bond",
        "source_url": "https://example.com/local/horstman-oct26-case-update",
        "link": "https://example.com/local/horstman-oct26-case-update",
        # A different registry ID was exactly what caused October 27's lock
        # mismatch. This must never be written over the custom story ID.
        "editorial_story_id": "story_999999",
        "_editorial_story_id": "story_999999",
        "_editorial_route": "update_existing",
        "editorial_route": "update_existing",
        "_semantic_material_update": True,
        "_semantic_material_update_decision": decision,
        "_pre_generation_material_update_promotion": True,
        "_pre_generation_material_update_canonical_slug": canonical["slug"],
        "canonical_slug": canonical["slug"],
    }
    g._attach_canonical_update_context(source, canonical, "independently_verified_material_update")
    g._stamp_canonical_write_authorization(source, canonical, {
        "outcome": g.IDENTITY_OUTCOME_VERIFIED,
        "identity_outcome": g.IDENTITY_OUTCOME_VERIFIED,
        "evidence_tier": "known_canonical_plus_semantic_materiality",
        "write_authorized": True,
        "proof_type": "validated_pre_generation_material_update",
        "reason": "Verified material change to the same October 26 incident.",
        "reason_codes": ["semantic_material_update_validated"],
    }, basis="pre_generation_material_update_promotion")
    assert g._has_self_consistent_pre_generation_material_update_authority(source)
    return source


def test_validated_horstman_update_rebinds_custom_slug_not_feed_story_id():
    g = importlib.import_module("scripts.generate")
    canonical = _canonical()
    source = _signed_source(g, canonical)
    matched, basis = g._find_forward_publication_target(
        source, [canonical], source["editorial_story_id"]
    )
    assert matched is canonical
    assert basis == "validated_selected_material_update_target_lock"
    assert matched["slug"] == CUSTOM
    assert matched["editorial_story_id"].startswith("custom:")
    valid, reason = g._forward_publication_target_valid(
        source, matched, matched["editorial_story_id"], basis
    )
    assert valid, reason
    assert reason == "pre_generation_material_update_authorized"
    assert g._authorized_custom_material_update(source, matched)


def test_unsigned_or_unvalidated_horstman_source_never_fuzzy_claims_custom():
    g = importlib.import_module("scripts.generate")
    canonical = _canonical()
    verified = _signed_source(g, canonical)
    cases = []
    unsigned = copy.deepcopy(verified)
    unsigned.pop("_canonical_write_authorization")
    cases.append(unsigned)
    wrong_target = copy.deepcopy(verified)
    wrong_target["_semantic_material_update_decision"]["selected_candidate_slug"] = "different-story"
    cases.append(wrong_target)
    no_materiality = copy.deepcopy(verified)
    no_materiality["_semantic_material_update_decision"]["material_new_update"] = False
    cases.append(no_materiality)
    conflicting_context = copy.deepcopy(verified)
    conflicting_context["_canonical_context_slug"] = "another-canonical"
    cases.append(conflicting_context)
    for source in cases:
        matched, basis = g._find_forward_publication_target(
            source, [canonical], source["editorial_story_id"]
        )
        assert matched is None, (basis, source)
        assert basis == "new_publication"
        # The unsigned source cannot write to the custom article.
        assert not g._authorized_custom_material_update(source, canonical)


def test_signed_update_cannot_redirect_to_different_custom_permalink():
    g = importlib.import_module("scripts.generate")
    canonical = _canonical()
    source = _signed_source(g, canonical)
    unrelated = {
        **canonical,
        "slug": "2026-10-26-another-unrelated-felony-incident",
        "canonical_slug": "2026-10-26-another-unrelated-felony-incident",
        "editorial_story_id": "custom:unrelated",
    }
    matched, basis = g._find_forward_publication_target(
        source, [unrelated], source["editorial_story_id"]
    )
    assert matched is None and basis == "new_publication"
    assert not g._canonical_write_authorized(source, unrelated)
    # The final forward gate itself blocks a missing/different signed target.
    valid, reason = g._forward_publication_target_valid(
        source, None, source["editorial_story_id"], basis
    )
    assert not valid and reason == "verified_canonical_destination_mismatch"
