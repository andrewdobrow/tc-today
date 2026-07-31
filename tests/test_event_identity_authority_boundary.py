from __future__ import annotations

import importlib
import json
import os
import sys
import types


def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def _candidate_canonical():
    return {
        "slug": "2026-07-20-port-st-lucie-police-investigate-shooting",
        "headline": "Port St. Lucie police investigate shooting after man wounded",
        "teaser": (
            "Port St. Lucie police are investigating a shooting that left a man wounded."
        ),
        "date": "2026-07-20",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }


def _candidate_incoming():
    return {
        "headline": "New details released in Port St. Lucie shooting investigation",
        "title": "New details released in Port St. Lucie shooting investigation",
        "article_text": (
            "Port St. Lucie police released new details in a shooting investigation."
        ),
        "summary": (
            "Port St. Lucie police released new details in a shooting investigation."
        ),
        "date": "2026-07-21",
        "published": "2026-07-21",
        "link": "https://example.com/new-shooting-details",
        "source_url": "https://example.com/new-shooting-details",
        "editorial_story_id": "story_incoming_untrusted",
        "_editorial_story_id": "story_incoming_untrusted",
        "_editorial_route": "generate_new",
        "_editorial_relationship": "new_story",
    }


def test_fuzzy_similarity_is_candidate_only_and_cannot_authorize_write():
    g = _load_generate()
    evidence = g._cross_source_same_event_evidence(
        _candidate_incoming(), _candidate_canonical()
    )

    assert evidence["identity_outcome"] == "possible_relationship"
    assert evidence["evidence_tier"] == "candidate_only"
    assert evidence["write_authorized"] is False
    assert evidence["matched"] is False


def test_legacy_fuzzy_matchers_have_no_destructive_authority(monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "_same_event_items", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(g, "_story_match_confidence", lambda *_args, **_kwargs: 100)

    evidence = g._cross_source_same_event_evidence(
        _candidate_incoming(), _candidate_canonical()
    )

    assert evidence["identity_outcome"] == "possible_relationship"
    assert evidence["write_authorized"] is False
    assert evidence["proof_type"] == "candidate_similarity"


def test_candidate_ledger_lookup_does_not_mutate_route_story_id_or_slug():
    g = _load_generate()
    canonical = _candidate_canonical()
    incoming = _candidate_incoming()
    ledger = g._build_canonical_publication_ledger([canonical])

    target, basis, _keys = g._canonical_publication_ledger_target(incoming, ledger)

    assert target is None
    assert basis == "candidate_only_no_write"
    assert incoming["_editorial_route"] == "generate_new"
    assert incoming["editorial_story_id"] == "story_incoming_untrusted"
    assert "_canonical_write_authorization" not in incoming
    assert incoming["_canonical_identity_candidate"]["canonical_slug"] == canonical["slug"]


def test_authorization_token_is_bound_to_one_canonical_slug():
    g = _load_generate()
    incoming = _candidate_incoming()
    canonical = _candidate_canonical()
    other = dict(canonical, slug="2026-07-20-a-different-story")
    decision = {
        "outcome": "same_event_verified",
        "evidence_tier": "exact_identity",
        "write_authorized": True,
        "proof_type": "exact_source_url",
        "reason": "exact_source_url",
    }

    g._stamp_canonical_write_authorization(incoming, canonical, decision)

    assert g._canonical_write_authorized(incoming, canonical) is True
    assert g._canonical_write_authorized(incoming, other) is False


def test_final_writer_gate_rejects_ledger_target_without_authorization():
    g = _load_generate()
    canonical = dict(_candidate_canonical(), editorial_story_id="story_canonical")
    incoming = _candidate_incoming()
    incoming["_editorial_route"] = "update_existing"
    incoming["editorial_story_id"] = "story_canonical"

    passed, reason = g._forward_publication_target_valid(
        incoming,
        canonical,
        "story_canonical",
        "canonical_publication_ledger:event-identity-authority:candidate_similarity",
    )

    assert passed is False
    assert reason == "canonical_write_authorization_missing"
    assert g._destructive_publication_write_authorized(
        incoming,
        canonical,
        "story_canonical",
        "canonical_publication_ledger:event-identity-authority:candidate_similarity",
    ) is False


def test_exact_source_url_authorizes_canonical_binding():
    g = _load_generate()
    url = "https://www.wptv.com/news/local-news/exact-source-story"
    canonical = dict(
        _candidate_canonical(),
        source_url=url,
        editorial_story_id="story_exact_source",
    )
    incoming = dict(_candidate_incoming(), source_url=url, link=url)
    ledger = g._build_canonical_publication_ledger([canonical])

    target, basis, _keys = g._canonical_publication_ledger_target(incoming, ledger)

    assert target["slug"] == canonical["slug"]
    assert basis == "exact_source_url"
    assert incoming["_editorial_route"] == "update_existing"
    assert incoming["editorial_story_id"] == "story_exact_source"
    assert g._canonical_write_authorized(incoming, canonical) is True


def test_registry_trusted_persistent_story_id_authorizes_binding():
    g = _load_generate()
    story_id = "story_registry_trusted"
    canonical = dict(_candidate_canonical(), editorial_story_id=story_id)
    incoming = _candidate_incoming()
    incoming["editorial_story_id"] = story_id
    incoming["_editorial_story_id"] = story_id
    identity_index = types.SimpleNamespace(safe_story_ids={story_id})
    ledger = g._build_canonical_publication_ledger([canonical], identity_index)

    target, basis, _keys = g._canonical_publication_ledger_target(
        incoming, ledger, identity_index
    )

    assert target["slug"] == canonical["slug"]
    assert basis == "trusted_persistent_story_id"
    assert g._canonical_write_authorized(incoming, canonical) is True


def test_event_identity_is_persisted_once_and_remains_immutable():
    g = _load_generate()
    source = {
        "source_headline": "Carl Loubeau, 24, killed on Southeast Rivergreen Circle",
        "article_text": (
            "Carl Loubeau, 24, was killed on Southeast Rivergreen Circle in "
            "Port St. Lucie."
        ),
        "source_url": "https://example.com/original-event",
        "date": "2026-07-20",
    }
    archive_entry = {"slug": "original-event"}

    first = g._persist_event_identity(source, archive_entry)
    source["source_headline"] = "John Doe arrested on Southwest Becker Road"
    source["article_text"] = (
        "John Doe, 30, was arrested on Southwest Becker Road in another case."
    )
    second = g._persist_event_identity(source, archive_entry)

    assert second == first
    assert archive_entry["event_identity"] == first
    assert "carl loubeau" in first["people"]
    assert "john doe" not in archive_entry["event_identity"]["people"]


def test_generated_background_prose_cannot_change_stored_event_identity():
    g = _load_generate()
    original_source = {
        "source_headline": "Carl Loubeau, 24, killed on Southeast Rivergreen Circle",
        "article_text": (
            "Carl Loubeau, 24, was killed on Southeast Rivergreen Circle in "
            "Port St. Lucie."
        ),
        "date": "2026-07-20",
    }
    canonical = {
        "slug": "rivergreen-shooting",
        "headline": original_source["source_headline"],
        "teaser": original_source["article_text"],
        "body": (
            original_source["article_text"]
            + "\n\nJohn Doe, 30, was arrested on Southwest Becker Road in an unrelated case."
        ),
        "date": "2026-07-20",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
        "event_identity": g._event_identity_snapshot(original_source),
    }
    unrelated = {
        "headline": "John Doe arrested after incident on Southwest Becker Road",
        "article_text": (
            "John Doe, 30, was arrested on Southwest Becker Road in Port St. Lucie."
        ),
        "date": "2026-07-21",
    }

    evidence = g._cross_source_same_event_evidence(unrelated, canonical)

    assert evidence["write_authorized"] is False
    assert evidence["shared_named_people"] == []
    assert "southwest-becker-road" not in evidence["shared_precise_locations"]


def test_authority_report_fails_closed_on_unauthorized_destructive_action(tmp_path):
    g = _load_generate()
    original = list(g.CROSS_SOURCE_IDENTITY_OBSERVATIONS)
    try:
        g.CROSS_SOURCE_IDENTITY_OBSERVATIONS[:] = [{
            "incoming_headline": "Candidate-only story",
            "matched_canonical_slug": "existing-story",
            "identity_outcome": "possible_relationship",
            "evidence_tier": "candidate_only",
            "write_authorized": False,
            "final_publication_action": "update_existing",
        }]
        report = g._write_cross_source_update_identity_report(tmp_path)
    finally:
        g.CROSS_SOURCE_IDENTITY_OBSERVATIONS[:] = original

    assert report["passed"] is False
    assert report["summary"]["unauthorized_destructive_count"] == 1
    assert (tmp_path / "data" / "cross-source-update-identity.json").exists()
    authority = json.loads(
        (tmp_path / "data" / "event-identity-authority.json").read_text()
    )
    assert authority["passed"] is False
