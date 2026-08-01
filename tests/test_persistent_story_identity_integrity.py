from __future__ import annotations

import importlib
import json
import os
import sys
import types
from pathlib import Path

from tct_engine.event_identity_authority import authorize_exact_identity_keys
from tct_engine.event_key import generate_event_key
from tct_engine.fact_extraction import ExtractedArticleFacts
from tct_engine.publication_identity import build_publication_identity_index
from tct_engine.registry_repair import (
    is_broad_event_class_key,
    repair_registry_payload,
)
from tct_engine.story_registry import StoryRegistry


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


def _facts(article_id: str) -> ExtractedArticleFacts:
    return ExtractedArticleFacts(
        article_id=article_id,
        source="WPEC",
        is_custom=False,
        facts=("road closed",),
        locations=("Port St. Lucie",),
        agencies=(),
        event_types=("traffic crash",),
        entities=(),
    )


def test_broad_crash_and_fire_keys_are_not_incident_identity():
    assert is_broad_event_class_key("traffic-crash-port-st-lucie") is True
    assert is_broad_event_class_key("fire-fort-pierce") is True
    assert is_broad_event_class_key("traffic-crash-port-st-lucie-a1b2c3d4e5") is False


def test_same_city_crashes_receive_different_article_specific_event_keys():
    first = generate_event_key(_facts("source-article-one"))
    second = generate_event_key(_facts("source-article-two"))
    assert first.startswith("traffic-crash-port-st-lucie-")
    assert second.startswith("traffic-crash-port-st-lucie-")
    assert first != second


def test_story_registry_never_maps_a_broad_event_key(tmp_path):
    registry = StoryRegistry(tmp_path / "registry.json")
    first = registry.resolve_story("traffic-crash-port-st-lucie")
    second = registry.resolve_story("traffic-crash-port-st-lucie")
    assert first != second
    assert "traffic-crash-port-st-lucie" not in registry.data["event_to_story"]


def test_registry_repair_quarantines_incoherent_broad_story():
    payload = {
        "next_story_id": 2,
        "stories": {
            "story_000001": {
                "story_id": "story_000001",
                "events": ["traffic-crash-port-st-lucie"],
                "titles": [
                    "Family sues after child dies in go-kart crash",
                    "Driver crashes SUV into liquor store and faces DUI charge",
                    "Woman dies in unrelated intersection crash",
                    "Motorcyclist injured in separate highway collision",
                ],
                "sources": [],
                "timeline": [],
            }
        },
        "event_to_story": {"traffic-crash-port-st-lucie": "story_000001"},
        "story_aliases": {},
        "quarantined_stories": {},
    }
    report = repair_registry_payload(payload)
    assert report.changed is True
    assert "story_000001" not in payload["stories"]
    assert "story_000001" in payload["quarantined_stories"]
    assert payload["event_to_story"] == {}


def test_publication_identity_excludes_quarantined_and_broad_stories():
    payload = {
        "stories": {
            "story_broad": {
                "story_id": "story_broad",
                "events": ["traffic-crash-port-st-lucie"],
                "titles": ["A crash"],
                "sources": ["https://www.wptv.com/a-crash"],
            },
            "story_safe": {
                "story_id": "story_safe",
                "events": ["named-person-death:marie-martin"],
                "titles": ["Marie Martin killed in crash"],
                "sources": ["https://www.wptv.com/marie-martin"],
            },
        },
        "quarantined_stories": {"story_old": {"story_id": "story_old"}},
    }
    index = build_publication_identity_index(payload)
    assert "story_broad" not in index.safe_story_ids
    assert "story_safe" in index.safe_story_ids
    assert "story_old" in index.quarantined_story_ids


def test_persistent_story_key_is_candidate_only_even_when_registry_calls_it_safe():
    decision = authorize_exact_identity_keys(
        ["story:story_000011"], trusted_story_ids={"story_000011"}
    )
    assert decision.outcome == "possible_relationship"
    assert decision.write_authorized is False
    assert decision.proof_type == "uncorroborated_persistent_story_id"


def test_matching_story_id_without_independent_facts_cannot_update_permalink():
    g = _load_generate()
    item = {
        "headline": "Woman dies in intersection crash",
        "source_url": "https://www.wptv.com/intersection-crash",
        "editorial_story_id": "story_same",
    }
    entry = {
        "slug": "liquor-store-crash",
        "headline": "Driver crashes SUV into liquor store",
        "source_url": "https://www.cbs12.com/liquor-store-crash",
        "editorial_story_id": "story_same",
    }
    valid, reason = g._forward_publication_target_valid(
        item, entry, "story_same", "persistent_story_id"
    )
    assert valid is False
    assert reason == "uncorroborated_persistent_story_id"


def test_exact_source_url_independently_reproves_update_target():
    g = _load_generate()
    url = "https://www.wptv.com/news/local-news/same-source-story"
    item = {"headline": "Updated headline", "source_url": url, "editorial_story_id": "story_same"}
    entry = {"slug": "existing", "headline": "Original headline", "source_url": url, "editorial_story_id": "story_same"}
    valid, reason = g._forward_publication_target_valid(
        item, entry, "story_same", "persistent_story_id"
    )
    assert valid is True
    assert reason == "exact_source_url"


def test_quarantined_story_ids_are_revoked_from_archive_rows():
    g = _load_generate()
    index = types.SimpleNamespace(quarantined_story_ids={"story_bad"})
    archive = [{"slug": "old-page", "headline": "Still valid article", "editorial_story_id": "story_bad"}]
    cleaned, revoked = g._revoke_quarantined_archive_story_ids(archive, index)
    assert cleaned[0].get("editorial_story_id") is None
    assert cleaned[0]["legacy_identity_status"] == "quarantined_story_id_revoked"
    assert revoked[0]["story_id"] == "story_bad"


def test_cached_editorial_state_cannot_resurrect_quarantined_story_id():
    g = _load_generate()
    prior_denylist = set(g.CURRENT_RUN_QUARANTINED_STORY_IDS)
    prior_identities = dict(g.CURRENT_RUN_EDITORIAL_IDENTITIES)
    try:
        g.CURRENT_RUN_QUARANTINED_STORY_IDS = {"story_000011"}
        g.CURRENT_RUN_EDITORIAL_IDENTITIES = {}
        entry = {
            "title": "86-year-old woman dies after Port St. Lucie intersection crash",
            "link": "https://cbs12.com/news/local/86-year-old-woman-dies-after-port-st-lucie-intersection-crash",
            "editorial_story_id": "story_000011",
            "_editorial_route": "update_existing",
            "story_form": "update",
        }
        row = {
            "source_url": entry["link"],
            "headline": entry["title"],
            "story_id": "story_000011",
            "event_key": "traffic-crash-port-st-lucie",
            "route": "update_existing",
            "relationship": "same_event",
            "relationship_confidence": 1.0,
            "decision_trace": ["Exact event-key mapping: true"],
        }

        remembered = g._remember_current_run_editorial_identity(entry, row)

        assert remembered is False
        assert row["story_id"] == ""
        assert row["route"] == "generate_new"
        assert row["relationship"] == "new_story"
        assert row["rejected_story_id"] == "story_000011"
        assert "editorial_story_id" not in entry
        assert "_editorial_route" not in entry
        assert "story_form" not in entry
        assert g.CURRENT_RUN_EDITORIAL_IDENTITIES == {}
    finally:
        g.CURRENT_RUN_QUARANTINED_STORY_IDS = prior_denylist
        g.CURRENT_RUN_EDITORIAL_IDENTITIES = prior_identities


def test_reused_current_run_identity_refuses_quarantined_story_id():
    g = _load_generate()
    prior_denylist = set(g.CURRENT_RUN_QUARANTINED_STORY_IDS)
    prior_identities = dict(g.CURRENT_RUN_EDITORIAL_IDENTITIES)
    url = "https://cbs12.com/news/local/quarantined-crash"
    try:
        g.CURRENT_RUN_QUARANTINED_STORY_IDS = {"story_bad"}
        g.CURRENT_RUN_EDITORIAL_IDENTITIES = {
            url: {
                "story_id": "story_bad",
                "event_key": "traffic-crash-port-st-lucie",
                "route": "update_existing",
            }
        }
        entry = {"title": "Separate crash", "link": url}

        stamped = g._stamp_known_current_run_identity(entry)

        assert stamped is False
        assert url not in g.CURRENT_RUN_EDITORIAL_IDENTITIES
        assert "editorial_story_id" not in entry
    finally:
        g.CURRENT_RUN_QUARANTINED_STORY_IDS = prior_denylist
        g.CURRENT_RUN_EDITORIAL_IDENTITIES = prior_identities


def test_cached_generation_cannot_reuse_prior_write_authorization():
    g = _load_generate()
    prior_identities = dict(g.CURRENT_RUN_EDITORIAL_IDENTITIES)
    url = "https://www.wptv.com/news/local/safe-current-source"
    try:
        g.CURRENT_RUN_EDITORIAL_IDENTITIES = {
            url: {
                "story_id": "story_safe",
                "event_key": "named-person-death:marie-martin",
                "route": "skip",
                "relationship": "same_event",
                "relationship_confidence": 1.0,
            }
        }
        cached = {
            "headline": "Cached generated headline",
            "source_url": url,
            "_canonical_write_authorization": {"authorization_token": "stale"},
            "_cross_source_identity_match": {
                "write_authorized": True,
                "proof_type": "trusted_persistent_story_id",
            },
            "_canonical_context_slug": "wrong-old-slug",
            "canonical_slug": "wrong-old-slug",
            "canonical_publication_id": "pub:wrong",
        }
        data = {"hero": cached, "cards": []}

        stamped = g._stamp_current_run_story_ids(data, [])

        assert stamped == 1
        assert cached["editorial_story_id"] == "story_safe"
        assert "_canonical_write_authorization" not in cached
        assert "_cross_source_identity_match" not in cached
        assert "_canonical_context_slug" not in cached
        assert "canonical_slug" not in cached
        assert "canonical_publication_id" not in cached
    finally:
        g.CURRENT_RUN_EDITORIAL_IDENTITIES = prior_identities


def test_integrity_contract_detects_broad_mapping_and_quarantine_reference():
    g = _load_generate()
    registry = {
        "stories": {},
        "event_to_story": {"traffic-crash-port-st-lucie": "story_bad"},
        "quarantined_stories": {"story_bad": {"story_id": "story_bad"}},
    }
    archive = [{"slug": "bad", "headline": "Bad binding", "editorial_story_id": "story_bad"}]
    report = g._build_persistent_story_identity_integrity_report(archive, registry)
    assert report["passed"] is False
    assert report["summary"]["broad_event_mapping_count"] == 1
    assert report["summary"]["archive_quarantine_reference_count"] == 1


def test_repository_migration_separates_and_restores_all_three_incidents():
    root = Path(__file__).resolve().parents[1]
    registry = json.loads((root / "data" / "editorial_story_registry.json").read_text())
    archive = json.loads((root / "archive.json").read_text())
    by_slug = {row["slug"]: row for row in archive}

    assert "story_000011" not in registry["stories"]
    assert "story_000011" in registry["quarantined_stories"]
    assert not any(is_broad_event_class_key(key) for key in registry["event_to_story"])

    go_kart = by_slug["2026-07-20-family-files-wrongful-death-lawsuit-after-6-year-old-dies-at-urban-air-adventure"]
    liquor = by_slug["2026-07-29-man-crashes-suv-into-port-st-lucie-liquor-store-charged-with-dui"]
    fatal = by_slug["2026-07-31-woman-86-dies-in-port-st-lucie-crash-after-failing-to-yield-at-intersection"]
    assert len({go_kart["editorial_story_id"], liquor["editorial_story_id"], fatal["editorial_story_id"]}) == 3
    assert "liquor store" in liquor["headline"].lower()
    assert "86-year-old" in fatal["headline"].lower()
    assert "go-kart" in go_kart["headline"].lower()

    liquor_html = (root / "articles" / f"{liquor['slug']}.html").read_text()
    fatal_html = (root / "articles" / f"{fatal['slug']}.html").read_text()
    assert "Man accused of DUI" in liquor_html
    assert "86-year-old woman dies" in fatal_html
