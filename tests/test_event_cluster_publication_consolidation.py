from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tct_engine.semantic_publication_gate import (
    ACTION_NEW,
    ACTION_UPDATE,
    candidate_evidence,
    retrieve_recent_candidates,
    validate_model_decision,
)

MAIN_SLUG = "2026-08-25-port-st-lucie-residents-receive-tornado-emergency-alert-20-minutes-after-storm-p"
ALERT_SLUG = "2026-08-25-port-st-lucie-residents-question-why-tornado-alerts-arrived-late-or-never-came-a"
REDUNDANT_SLUGS = {
    "2026-08-25-port-st-lucie-residents-describe-frightening-sounds-and-damage-from-ef-0-tornado": MAIN_SLUG,
    "2026-08-25-tornado-moves-through-port-st-lucie-neighborhood-on-hurricane-andrew-anniversary": MAIN_SLUG,
    "2026-08-24-tornado-touches-down-in-port-st-lucie-national-weather-service-surveys-damage-mo": MAIN_SLUG,
    "2026-08-25-ef0-tornado-touches-down-in-port-st-lucie-damages-20-to-30-homes-along-2-mile-pa": MAIN_SLUG,
    "2026-08-25-radar-limitations-made-it-difficult-to-detect-port-st-lucie-tornado-meteorologis": ALERT_SLUG,
}


def _tornado_article(slug: str, headline: str, body: str, *, story_id="story_tornado_main"):
    return {
        "slug": slug,
        "headline": headline,
        "source_headline": headline,
        "published_at": "2026-08-24T21:31:00-04:00",
        "first_published": "2026-08-24T21:31:00-04:00",
        "date": "2026-08-24",
        "lead": body.split(".", 1)[0] + ".",
        "teaser": body[:300],
        "body": body,
        "source_url": f"https://example.com/{slug}",
        "locality": ["port-st-lucie", "st-lucie-county"],
        "event_families": ["weather", "tornado"],
        "people": [],
        "precise_locations": ["st-lucie-river", "southbend"],
        "agencies": ["national-weather-service"],
        "incident_anchor": "weather-port-st-lucie-ef0-2026-08-23",
        "known_event_key": "",
        "editorial_story_id": story_id,
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
        "article_word_count": 220,
        "article_paragraph_count": 4,
    }


MAIN_BODY = (
    "The National Weather Service confirmed an EF0 tornado touched down in Port St. Lucie "
    "Sunday evening with peak winds of 75 mph. The tornado began at 6:10 p.m. near Southeast "
    "Kitching Cove Lane and Southeast Morningside Boulevard near Tarpon Bay Club and traveled "
    "more than two miles over 14 to 15 minutes. The tornado moved over the St. Lucie River, "
    "where it became a waterspout, before moving back onshore near Bay St. Lucie and Southbend. "
    "Trees were down, fences were blown over and pool screen enclosures and roofs were damaged."
)
REACTION_BODY = (
    "Residents in Port St. Lucie described watching debris fly as the EF0 tornado damaged "
    "fences, sheds and roofs Sunday evening. Allison Rogers lost her fence and shed near "
    "Southbend Boulevard. The tornado crossed the St. Lucie River as a waterspout. Aron "
    "Christiansen saw debris before the storm hit. National Weather Service meteorologist Will "
    "Ulrich said peak winds reached 75 mph. The tornado traveled about two miles and damaged "
    "pool screen enclosures and trees."
)


def _load_generate(tmp_path: Path):
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
    path = ROOT / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_event_cluster_consolidation", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    module.OUTPUT_DIR = tmp_path
    module.SEMANTIC_GATE_CACHE_PATH = tmp_path / "data" / "semantic-publication-gate-cache.json"
    module.SEMANTIC_GATE_REPORT_PATH = tmp_path / "data" / "semantic-publication-gate.json"
    return module


def test_angle_shifted_tornado_reporting_is_retrieved_by_content_continuity():
    main = _tornado_article(
        MAIN_SLUG,
        "National Weather Service confirms EF0 tornado with 75 mph winds in Port St. Lucie",
        MAIN_BODY,
    )
    incoming = _tornado_article(
        "",
        "Port St. Lucie residents describe frightening sounds and damage from EF-0 tornado",
        REACTION_BODY,
        story_id="story_fragment_reaction",
    )
    evidence = candidate_evidence(incoming, main, window_days=7)
    assert evidence["headline_similarity"]["score"] < 0.64
    assert evidence["strong_content_event_continuity"] is True
    assert "strong_content_event_continuity" in evidence["reasons"]
    candidates = retrieve_recent_candidates(incoming, [main], window_days=7, max_candidates=4)
    assert [row["slug"] for row in candidates] == [MAIN_SLUG]


def test_same_county_unrelated_fire_is_not_retrieved_as_tornado_event():
    main = _tornado_article(MAIN_SLUG, "NWS confirms EF0 tornado in Port St. Lucie", MAIN_BODY)
    fire = {
        **_tornado_article(
            "",
            "Fire crews contain Fort Pierce structure blaze before it spreads to mobile homes",
            (
                "St. Lucie County Fire District contained a residential structure fire on East "
                "Erie Drive in Fort Pierce before flames reached nearby mobile homes. The State "
                "Fire Marshal is investigating the cause."
            ),
            story_id="story_fire",
        ),
        "locality": ["fort-pierce", "st-lucie-county"],
        "event_families": ["fire"],
        "precise_locations": ["east-erie-drive"],
        "agencies": ["st-lucie-county-fire-district"],
        "incident_anchor": "fire-fort-pierce-east-erie-drive",
    }
    evidence = candidate_evidence(fire, main, window_days=7)
    assert evidence["strong_content_event_continuity"] is False
    assert evidence["eligible"] is False


def test_same_event_angle_defaults_to_update_not_new_permalink():
    candidates = [{"slug": MAIN_SLUG, "article": {"slug": MAIN_SLUG}}]
    decision = validate_model_decision(
        {
            "selected_candidate_slug": MAIN_SLUG,
            "same_real_world_event": True,
            "material_new_update": True,
            "independently_newsworthy_followup": False,
            "confidence": 0.96,
            "shared_anchors": ["same EF0 tornado"],
            "novel_facts": ["additional resident damage accounts"],
            "reason": "Same tornado with more reporting.",
            "recommended_action": ACTION_NEW,
        },
        candidates,
    )
    assert decision["action"] == ACTION_UPDATE


def test_model_can_request_rare_independently_newsworthy_same_event_followup():
    candidates = [{"slug": MAIN_SLUG, "article": {"slug": MAIN_SLUG}}]
    decision = validate_model_decision(
        {
            "selected_candidate_slug": MAIN_SLUG,
            "same_real_world_event": True,
            "material_new_update": True,
            "independently_newsworthy_followup": True,
            "confidence": 0.95,
            "shared_anchors": ["same EF0 tornado"],
            "novel_facts": ["alerts arrived after the tornado passed"],
            "reason": "A separate public-safety accountability question now exists.",
            "recommended_action": ACTION_NEW,
        },
        candidates,
    )
    assert decision["action"] == ACTION_NEW
    assert decision["independently_newsworthy_followup"] is True


def test_same_story_identity_cannot_mint_independent_followup_permalink(tmp_path, monkeypatch):
    generate = _load_generate(tmp_path)
    canonical = _tornado_article(MAIN_SLUG, "NWS confirms EF0 tornado", MAIN_BODY)
    incoming = _tornado_article(
        "",
        "Why Port St. Lucie tornado alerts arrived late",
        REACTION_BODY,
        story_id="story_tornado_main",
    )
    decision = {
        "status": "validated",
        "action": ACTION_NEW,
        "recommended_action": ACTION_NEW,
        "selected_candidate_slug": MAIN_SLUG,
        "same_real_world_event": True,
        "material_new_update": True,
        "independently_newsworthy_followup": True,
        "confidence": 0.95,
        "shared_anchors": ["same tornado"],
        "novel_facts": ["alert delay"],
        "reason": "accountability angle",
        "validation_errors": [],
    }
    monkeypatch.setattr(
        generate,
        "retrieve_semantic_publication_candidates",
        lambda *args, **kwargs: [
            {"slug": MAIN_SLUG, "headline": canonical["headline"], "article": canonical, "evidence": {}}
        ],
    )
    monkeypatch.setattr(
        generate,
        "adjudicate_semantic_publication_candidates",
        lambda *args, **kwargs: dict(decision),
    )
    monkeypatch.setattr(generate, "_semantic_gate_recent_archive_rows", lambda *args, **kwargs: [canonical])
    cache = {"schema_version": 1, "entries": {}}
    report = generate._new_semantic_publication_gate_report()
    resolved, selected, _ = generate._run_semantic_publication_gate(
        incoming, [canonical], cache, report, phase="forward_publication"
    )
    assert selected is canonical
    assert resolved["action"] == ACTION_UPDATE
    assert resolved["independent_followup_authorized"] is False
    assert incoming.get("publication_relationship") != "independent_followup"


def test_distinct_story_identity_can_authorize_independent_followup_and_ledger_separates_it(tmp_path, monkeypatch):
    generate = _load_generate(tmp_path)
    canonical = _tornado_article(MAIN_SLUG, "NWS confirms EF0 tornado", MAIN_BODY)
    incoming = _tornado_article(
        "",
        "Port St. Lucie residents question why tornado alerts arrived late",
        REACTION_BODY,
        story_id="story_tornado_alert_accountability",
    )
    decision = {
        "status": "validated",
        "action": ACTION_NEW,
        "recommended_action": ACTION_NEW,
        "selected_candidate_slug": MAIN_SLUG,
        "same_real_world_event": True,
        "material_new_update": True,
        "independently_newsworthy_followup": True,
        "confidence": 0.95,
        "shared_anchors": ["same tornado"],
        "novel_facts": ["late or missing alerts"],
        "reason": "independent accountability question",
        "validation_errors": [],
    }
    monkeypatch.setattr(
        generate,
        "retrieve_semantic_publication_candidates",
        lambda *args, **kwargs: [
            {"slug": MAIN_SLUG, "headline": canonical["headline"], "article": canonical, "evidence": {}}
        ],
    )
    monkeypatch.setattr(
        generate,
        "adjudicate_semantic_publication_candidates",
        lambda *args, **kwargs: dict(decision),
    )
    monkeypatch.setattr(generate, "_semantic_gate_recent_archive_rows", lambda *args, **kwargs: [canonical])
    resolved, selected, _ = generate._run_semantic_publication_gate(
        incoming,
        [canonical],
        {"schema_version": 1, "entries": {}},
        generate._new_semantic_publication_gate_report(),
        phase="forward_publication",
    )
    assert selected is canonical
    assert resolved["action"] == ACTION_NEW
    assert resolved["independent_followup_authorized"] is True
    assert incoming["publication_relationship"] == "independent_followup"
    assert incoming["related_parent_slug"] == MAIN_SLUG
    keys = generate._publication_ledger_identity_keys(incoming)
    assert "story:story_tornado_alert_accountability" in keys
    assert not any(key.startswith("incident:") for key in keys)


def test_top_stories_event_cluster_caps_same_event_at_two(tmp_path):
    generate = _load_generate(tmp_path)
    cards = []
    archive = []
    for index in range(5):
        slug = f"2026-08-25-tornado-angle-{index}"
        card = {
            "slug": slug,
            "headline": f"Port St. Lucie tornado angle {index}",
            "urgency_score": 8 - min(index, 3),
            "category_key": "st_lucie",
            "editorial_story_id": "story_tornado_main",
            "first_published": "Tue, 25 Aug 2026 10:00:00 -0400",
        }
        cards.append(card)
        archive.append(dict(card))
    for index in range(3):
        slug = f"2026-08-25-unrelated-{index}"
        card = {
            "slug": slug,
            "headline": f"Unrelated Treasure Coast story {index}",
            "urgency_score": 7,
            "category_key": "business",
            "editorial_story_id": f"story_other_{index}",
            "first_published": "Tue, 25 Aug 2026 09:30:00 -0400",
        }
        cards.append(card)
        archive.append(dict(card))
    selected, report = generate._select_top_story_cards(
        cards,
        archive,
        limit=8,
        now=generate.datetime(2026, 8, 25, 16, 0, tzinfo=generate.timezone.utc),
    )
    tornado_selected = [row for row in selected if row.get("editorial_story_id") == "story_tornado_main"]
    assert len(tornado_selected) == 2
    assert any(row.get("reason") == "event_cluster_diversity_cap" for row in report["excluded"])
    assert len([row for row in selected if str(row.get("editorial_story_id", "")).startswith("story_other_")]) == 3


def test_current_tornado_cleanup_preserves_two_canonicals_and_redirects_five():
    payload = json.loads((ROOT / "data" / "source-retirement-cleanup.json").read_text())
    rows = {row["slug"]: row for row in payload["retirements"]}
    # Preserve all three pre-existing retirement policies.
    assert "2026-08-22-martin-county-deputy-stops-600000-gold-bar-scam-targeting-senior" in rows
    assert "2026-08-22-indian-river-county-creates-attainable-housing-trust-to-support-development" in rows
    assert "2026-08-22-vero-beach-man-arrested-on-attempted-murder-charge-after-birthday-party-assault" in rows
    for source_slug, target_slug in REDUNDANT_SLUGS.items():
        assert rows[source_slug]["action"] == "canonical_redirect"
        assert rows[source_slug]["target_slug"] == target_slug
    assert MAIN_SLUG not in REDUNDANT_SLUGS
    assert ALERT_SLUG not in REDUNDANT_SLUGS


def test_tornado_cleanup_transaction_leaves_exactly_main_and_accountability_canonicals(tmp_path):
    generate = _load_generate(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "source-retirement-cleanup.json").write_text(
        (ROOT / "data" / "source-retirement-cleanup.json").read_text(),
        encoding="utf-8",
    )
    archive = [
        {"slug": MAIN_SLUG, "headline": "NWS confirms EF0 tornado", "editorial_story_id": "story_main"},
        {"slug": ALERT_SLUG, "headline": "Residents question late tornado alerts", "editorial_story_id": "story_alert"},
    ]
    for source_slug, target_slug in REDUNDANT_SLUGS.items():
        archive.append({
            "slug": source_slug,
            "headline": f"redundant tornado angle {source_slug[-8:]}",
            "editorial_story_id": "story_fragment",
        })
    kept, redirects, report = generate.apply_source_retirement_cleanup_to_archive(
        archive,
        tmp_path / "articles",
        tmp_path,
    )
    assert {row["slug"] for row in kept} == {MAIN_SLUG, ALERT_SLUG}
    assert report["retired_count"] == 5
    assert report["redirect_count"] == 5
    assert {(row["source_slug"], row["target_slug"]) for row in redirects} == set(REDUNDANT_SLUGS.items())
