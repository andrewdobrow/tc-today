from __future__ import annotations

import importlib
import os
import sys
import types
from datetime import datetime, timezone


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


def _event_identity(locality="port_st_lucie", family="weather"):
    return {
        "locality": [locality],
        "event_families": [family],
        "people": [],
        "precise_locations": [],
        "agencies": [],
    }


def test_publication_permalink_date_uses_treasure_coast_calendar_day():
    g = _load_generate()
    # 00:30 UTC Wednesday is still 8:30 p.m. Tuesday in Port St. Lucie.
    now = datetime(2026, 8, 26, 0, 30, tzinfo=timezone.utc)
    assert g._today_eastern_iso(now) == "2026-08-25"


def test_validated_material_update_keeps_evolved_canonical_live_safe():
    g = _load_generate()
    evolved = {
        "slug": "2026-08-20-port-st-lucie-to-consider-1483-annual-trash-fee-increase",
        "headline": "Port St. Lucie raises annual trash fee to $482 despite ongoing pickup complaints",
        "date": "2026-08-20",
        "lastmod": "2026-08-26",
        "meaningful_update_validated": True,
        "meaningful_update_basis": "semantic_material_update_gate",
        "last_meaningful_update_at": "2026-08-26T00:20:00Z",
        "editorial_story_id": "story_trash_fee",
    }
    result = g._archive_headline_slug_alignment(evolved)
    assert result["aligned"] is True
    assert result["reason"] == "validated_canonical_headline_evolution"
    assert g._archive_entry_live_identity_safe(evolved) is True




def test_permalink_origin_headline_allows_normal_canonical_evolution_without_update_metadata():
    g = _load_generate()
    evolved = {
        "slug": "2026-08-20-port-st-lucie-to-consider-1483-annual-trash-fee-increase",
        "permalink_origin_headline": "Port St. Lucie to consider $14.83 annual trash fee increase",
        "headline": "Port St. Lucie raises annual trash fee to $482 despite ongoing pickup complaints",
        "date": "2026-08-20",
        "lastmod": "2026-08-26",
        "editorial_story_id": "story_trash_fee",
    }
    result = g._archive_headline_slug_alignment(evolved)
    assert result["aligned"] is True

def test_unvalidated_old_headline_slug_overwrite_still_quarantines():
    g = _load_generate()
    unsafe = {
        "slug": "2026-08-20-port-st-lucie-to-consider-trash-fee",
        "headline": "Vero Beach homicide suspect arrested after interstate manhunt",
        "date": "2026-08-20",
        "lastmod": "2026-08-26",
        "editorial_story_id": "story_bad_overwrite",
    }
    result = g._archive_headline_slug_alignment(unsafe)
    assert result["aligned"] is False
    assert result["reason"] == "headline_slug_event_drift"


def test_terminal_shortlist_includes_evolved_tornado_canonical_for_reaction_angle(monkeypatch):
    g = _load_generate()
    canonical_slug = "2026-08-25-port-st-lucie-residents-receive-tornado-emergency-alert-20-minutes-after-storm-p"
    canonical = {
        "slug": canonical_slug,
        "headline": "National Weather Service confirms EF-0 tornado touched down in Port St. Lucie Sunday evening",
        "teaser": "An EF-0 tornado with 75 mph winds touched down in Port St. Lucie Sunday evening and damaged homes.",
        "date": "2026-08-25",
        "lastmod": "2026-08-26",
        "first_published": "Mon, 24 Aug 2026 22:23:00 -0400",
        "meaningful_update_validated": True,
        "meaningful_update_basis": "semantic_material_update_gate",
        "last_meaningful_update_at": "2026-08-25T10:49:00Z",
        "editorial_story_id": "story_psl_tornado",
        "event_identity": _event_identity(),
        "category_key": "st_lucie",
    }
    incoming = {
        "headline": "Port St. Lucie resident takes cover as possible tornado hits neighborhood Sunday",
        "teaser": "A resident near Southbend Boulevard had seconds to take cover before debris hit his home.",
        "body": "Aaron Christiansen saw debris flying near Southbend Boulevard and took cover before the Sunday tornado damaged his patio and pool fence.",
        "published": "Wed, 26 Aug 2026 08:00:00 -0400",
        "source_url": "https://example.com/reaction-angle",
        "event_identity": _event_identity(),
        "category_key": "st_lucie",
    }
    monkeypatch.setattr(g, "_archive_article_body", lambda row: canonical["teaser"])
    rows = g._terminal_permalink_recent_archive_rows(incoming, [canonical])
    assert [row["slug"] for row in rows] == [canonical_slug]


def test_terminal_gate_can_block_duplicate_even_if_earlier_gate_missed(monkeypatch):
    g = _load_generate()
    canonical_slug = "2026-08-25-port-st-lucie-residents-receive-tornado-emergency-alert-20-minutes-after-storm-p"
    canonical = {
        "slug": canonical_slug,
        "headline": "National Weather Service confirms EF-0 tornado touched down in Port St. Lucie Sunday evening",
        "teaser": "An EF-0 tornado with 75 mph winds touched down in Port St. Lucie Sunday evening.",
        "date": "2026-08-25",
        "first_published": "Mon, 24 Aug 2026 22:23:00 -0400",
        "editorial_story_id": "story_psl_tornado",
        "meaningful_update_validated": True,
        "meaningful_update_basis": "semantic_material_update_gate",
        "last_meaningful_update_at": "2026-08-25T10:49:00Z",
        "event_identity": _event_identity(),
        "category_key": "st_lucie",
    }
    incoming = {
        "headline": "Port St. Lucie residents clean up debris, damaged structures after Sunday tornado",
        "teaser": "Residents cleaned up patios, pools and debris after the same Sunday tornado.",
        "body": "Residents cleaned up damaged patios, pool fencing and debris after the Port St. Lucie tornado.",
        "published": "Wed, 26 Aug 2026 08:00:00 -0400",
        "source_url": "https://example.com/cleanup-angle",
        "editorial_story_id": "story_fragment_cleanup",
        "event_identity": _event_identity(),
        "category_key": "st_lucie",
    }
    monkeypatch.setattr(g, "_archive_article_body", lambda row: canonical["teaser"])

    called = {}
    def _adjudicate(client, **kwargs):
        called["model"] = kwargs["model"]
        called["candidate_slugs"] = [row["slug"] for row in kwargs["candidates"]]
        return {
            "status": "validated",
            "action": g.SEMANTIC_ACTION_DUPLICATE,
            "selected_candidate_slug": canonical_slug,
            "same_real_world_event": True,
            "material_new_update": False,
            "independently_newsworthy_followup": False,
            "confidence": 0.97,
            "shared_anchors": ["same Port St. Lucie Sunday EF0 tornado"],
            "novel_facts": [],
            "reason": "Cleanup and resident reaction are the same tornado event, not a new story.",
            "validation_errors": [],
        }

    monkeypatch.setattr(g, "adjudicate_semantic_publication_candidates", _adjudicate)
    cache = {"entries": {}}
    report = g._new_semantic_publication_gate_report()
    decision, selected, candidates = g._run_terminal_permalink_gate(
        incoming, [canonical], cache, report
    )
    assert decision["action"] == g.SEMANTIC_ACTION_DUPLICATE
    assert selected is canonical
    assert called["model"] == g.TERMINAL_PERMALINK_MODEL
    assert canonical_slug in called["candidate_slugs"]
    assert report["summary"]["terminal_permalink_duplicates_blocked"] == 1


def test_terminal_gate_fails_closed_on_model_hold(monkeypatch):
    g = _load_generate()
    canonical = {
        "slug": "2026-08-25-port-st-lucie-approves-trash-fee-increase",
        "headline": "Port St. Lucie approves annual trash fee increase",
        "teaser": "The City Council approved a solid waste assessment increase.",
        "date": "2026-08-25",
        "first_published": "Tue, 25 Aug 2026 12:00:00 -0400",
        "editorial_story_id": "story_trash_fee",
        "event_identity": _event_identity("port_st_lucie", "government_action"),
        "category_key": "local_gov",
    }
    incoming = {
        "headline": "Port St. Lucie raises annual trash fee to $482 despite ongoing pickup complaints",
        "teaser": "The council raised the annual solid waste assessment to $482.16.",
        "body": "Port St. Lucie City Council approved Resolution 26-R70 raising the assessment to $482.16.",
        "published": "Wed, 26 Aug 2026 08:00:00 -0400",
        "source_url": "https://example.com/trash-update",
        "event_identity": _event_identity("port_st_lucie", "government_action"),
        "category_key": "local_gov",
    }
    monkeypatch.setattr(g, "_archive_article_body", lambda row: canonical["teaser"])
    monkeypatch.setattr(
        g,
        "adjudicate_semantic_publication_candidates",
        lambda *args, **kwargs: {
            "status": "validated",
            "action": g.SEMANTIC_ACTION_HOLD,
            "selected_candidate_slug": "",
            "same_real_world_event": False,
            "material_new_update": False,
            "independently_newsworthy_followup": False,
            "confidence": 0.5,
            "shared_anchors": [],
            "novel_facts": [],
            "reason": "Ambiguous identity.",
            "validation_errors": [],
        },
    )
    report = g._new_semantic_publication_gate_report()
    decision, _, _ = g._run_terminal_permalink_gate(incoming, [canonical], {"entries": {}}, report)
    assert decision["action"] == g.SEMANTIC_ACTION_HOLD
    assert report["summary"]["terminal_permalink_holds"] == 1



def _terminal_hold(g, reason="First pass uncertain."):
    return {
        "status": "validated",
        "action": g.SEMANTIC_ACTION_HOLD,
        "selected_candidate_slug": "",
        "same_real_world_event": False,
        "material_new_update": False,
        "independently_newsworthy_followup": False,
        "confidence": 0.55,
        "shared_anchors": [],
        "novel_facts": [],
        "reason": reason,
        "validation_errors": [],
    }


def _terminal_candidate(slug, headline, category_key="florida"):
    article = {
        "slug": slug,
        "headline": headline,
        "teaser": headline,
        "body": headline,
        "date": "2026-08-25",
        "first_published": "Tue, 25 Aug 2026 12:00:00 -0400",
        "editorial_story_id": f"story_{slug}",
        "category_key": category_key,
    }
    return {"slug": slug, "headline": headline, "article": article, "evidence": {"terminal_recall_tier": 1, "terminal_recall_score": 0.5}}


def test_giustino_material_update_keeps_new_headline_and_freezes_legacy_permalink_origin(monkeypatch):
    g = _load_generate()
    old_headline = "More Than 70 Animals Found in Stuart Home During Large-Scale Hoarding Response"
    new_headline = "Martin County woman pleads no contest in animal hoarding case, receives probation"
    canonical = {
        "slug": "2026-07-20-more-than-70-animals-found-in-stuart-home-during-large-scale-hoarding-response",
        "headline": old_headline,
        "teaser": "More than 70 animals were found at a Stuart home in July.",
        "body": "Deputies found more than 70 animals at a Stuart home in July and arrested the homeowner.",
        "date": "2026-07-20",
        "first_published": "Mon, 20 Jul 2026 12:00:00 -0400",
        "editorial_story_id": "story_giustino_hoarding",
    }
    incoming = {
        "headline": new_headline,
        "teaser": "The defendant entered a no-contest plea and received probation.",
        "body": "The defendant entered a no-contest plea in Martin County and received probation in the same animal-hoarding case.",
        "published": "Wed, 26 Aug 2026 16:00:00 -0400",
        "source_url": "https://example.com/giustino-plea",
    }
    monkeypatch.setattr(g, "compose_semantic_material_update", lambda *args, **kwargs: {
        "status": "validated",
        "headline": new_headline,
        "teaser": "The defendant entered a no-contest plea and received probation after the July animal-hoarding arrest.",
        "body": "The defendant entered a no-contest plea and received probation after deputies found more than 70 animals at the Stuart home in July.\n\nThe plea is the latest development in the same Martin County animal-hoarding case.",
        "word_count": 38,
        "paragraph_count": 2,
        "baseline_lead_hits": ["July animal-hoarding arrest"],
        "novelty_lead_hits": ["no-contest plea", "probation"],
        "validation_errors": [],
    })
    monkeypatch.setattr(g, "_update_replacement_diagnostics", lambda *args, **kwargs: {
        "required": True, "passed": True, "baseline_present": True, "novelty_present": True, "missing": []
    })
    report = g._new_semantic_publication_gate_report()
    decision = {"confidence": 0.98, "novel_facts": ["no-contest plea", "probation"], "shared_anchors": ["same animal-hoarding case"]}

    merged, result = g._semantic_material_update_composition(canonical, incoming, decision, report, phase="forward_publication")

    assert result["status"] == "validated"
    assert merged["headline"] == new_headline
    assert "headline_preserved_for_permalink_alignment" not in result
    g._apply_semantic_material_update_metadata(canonical, incoming, merged, decision, result["context_diagnostics"], today="2026-08-26")
    assert canonical["headline"] == new_headline
    assert canonical["permalink_origin_headline"] == old_headline
    assert canonical["canonical_first_published_at"] == "Mon, 20 Jul 2026 12:00:00 -0400"
    assert canonical["canonical_last_material_update_at"] == canonical["last_meaningful_update_at"]
    assert merged["canonical_last_material_update_at"] == canonical["canonical_last_material_update_at"]


def test_semantic_material_update_still_rejects_unrelated_overwrite_after_headline_evolution_fix(monkeypatch):
    g = _load_generate()
    canonical = {
        "slug": "2026-08-20-port-st-lucie-trash-fee",
        "headline": "Port St. Lucie considers annual trash fee increase",
        "body": "The City Council considered a solid-waste assessment increase.",
        "teaser": "The City Council considered a solid-waste assessment increase.",
        "date": "2026-08-20",
        "first_published": "Thu, 20 Aug 2026 12:00:00 -0400",
    }
    incoming = {"headline": "Vero Beach homicide suspect arrested", "body": "Police arrested a homicide suspect in Vero Beach.", "source_url": "https://example.com/unrelated"}
    monkeypatch.setattr(g, "compose_semantic_material_update", lambda *args, **kwargs: {
        "status": "validated", "headline": incoming["headline"], "teaser": incoming["body"], "body": incoming["body"],
        "word_count": 10, "paragraph_count": 1, "baseline_lead_hits": [], "novelty_lead_hits": ["arrest"], "validation_errors": []
    })
    monkeypatch.setattr(g, "_update_replacement_diagnostics", lambda *args, **kwargs: {
        "required": True, "passed": False, "baseline_present": False, "novelty_present": True, "missing": ["original_event_context_missing"]
    })
    merged, result = g._semantic_material_update_composition(canonical, incoming, {"confidence": 0.9}, g._new_semantic_publication_gate_report(), phase="forward_publication")
    assert merged is None
    assert result["status"] == "context_contract_failed"
    assert "original_event_context_missing" in result["validation_errors"]


def test_byron_donalds_running_mate_terminal_hold_resolves_new_when_no_candidate_is_same_event(monkeypatch):
    g = _load_generate()
    candidate = _terminal_candidate("2026-08-25-florida-campaign-finance-report", "Florida candidates file campaign finance reports")
    incoming = {"headline": "Byron Donalds selects Miami-Dade Sen. Bryan Avila as running mate", "body": "Donalds selected Bryan Avila as his running mate.", "source_url": "https://www.wptv.com/news/political/byron-donalds-avila", "category_key": "florida"}
    monkeypatch.setattr(g, "_terminal_permalink_recent_archive_rows", lambda incoming, archive: [candidate])
    monkeypatch.setattr(g, "adjudicate_semantic_publication_candidates", lambda *args, **kwargs: _terminal_hold(g))
    calls = []
    def resolve(*args, **kwargs):
        calls.append(kwargs)
        return {"status": "validated", "action": g.SEMANTIC_ACTION_NEW, "selected_candidate_slug": "", "same_real_world_event": False, "material_new_update": False, "independently_newsworthy_followup": False, "confidence": 0.96, "shared_anchors": [], "novel_facts": ["Bryan Avila selected"], "reason": "No candidate is the same event.", "validation_errors": [], "resolution_pass": True}
    monkeypatch.setattr(g, "resolve_semantic_publication_hold", resolve)
    report = g._new_semantic_publication_gate_report()
    decision, selected, _ = g._run_terminal_permalink_gate(incoming, [candidate["article"]], {"entries": {}}, report)
    assert decision["action"] == g.SEMANTIC_ACTION_NEW
    assert decision["resolved_from_initial_terminal_hold"] is True
    assert selected is None
    assert len(calls) == 1
    assert report["summary"]["terminal_permalink_holds_resolved"] == 1
    assert g.SEMANTIC_PUBLICATION_SOURCE_OUTCOMES[g._normalized_external_source_url(incoming["source_url"]) or incoming["source_url"]]["authority_stage"] == "terminal_permalink_authority"


def test_martin_burglary_arrests_terminal_hold_resolves_new_after_duplicate_sources_are_already_collapsed(monkeypatch):
    g = _load_generate()
    candidate = _terminal_candidate("2026-08-25-martin-county-unrelated-burglary", "Martin County deputies investigate unrelated residential burglary", "crime")
    incoming = {"headline": "Two St. Lucie County men arrested in Martin County burglary", "body": "Deputies arrested two St. Lucie County men in a Martin County burglary case.", "source_url": "https://example.com/martin-burglary-arrests", "category_key": "crime"}
    monkeypatch.setattr(g, "_terminal_permalink_recent_archive_rows", lambda incoming, archive: [candidate])
    monkeypatch.setattr(g, "adjudicate_semantic_publication_candidates", lambda *args, **kwargs: _terminal_hold(g))
    monkeypatch.setattr(g, "resolve_semantic_publication_hold", lambda *args, **kwargs: {"status": "validated", "action": g.SEMANTIC_ACTION_NEW, "selected_candidate_slug": "", "same_real_world_event": False, "material_new_update": False, "independently_newsworthy_followup": False, "confidence": 0.94, "shared_anchors": [], "novel_facts": ["two named arrests"], "reason": "No shortlisted canonical is this burglary arrest event.", "validation_errors": [], "resolution_pass": True})
    decision, _, _ = g._run_terminal_permalink_gate(incoming, [candidate["article"]], {"entries": {}}, g._new_semantic_publication_gate_report())
    assert decision["action"] == g.SEMANTIC_ACTION_NEW


def test_nws_tornado_warning_explanation_terminal_hold_resolves_to_existing_canonical(monkeypatch):
    g = _load_generate()
    canonical_slug = "2026-08-25-port-st-lucie-residents-receive-tornado-emergency-alert-20-minutes-after-storm-p"
    candidate = _terminal_candidate(canonical_slug, "National Weather Service confirms EF-0 tornado touched down in Port St. Lucie Sunday evening", "st_lucie")
    candidate["article"]["editorial_story_id"] = "story_psl_tornado"
    incoming = {"headline": "National Weather Service explains Port St. Lucie tornado warning delay", "body": "The National Weather Service explained why the warning arrived after the same Sunday tornado touched down.", "source_url": "https://example.com/nws-warning-explanation", "category_key": "st_lucie", "editorial_story_id": "story_fragment_nws"}
    monkeypatch.setattr(g, "_terminal_permalink_recent_archive_rows", lambda incoming, archive: [candidate])
    monkeypatch.setattr(g, "adjudicate_semantic_publication_candidates", lambda *args, **kwargs: _terminal_hold(g))
    monkeypatch.setattr(g, "resolve_semantic_publication_hold", lambda *args, **kwargs: {"status": "validated", "action": g.SEMANTIC_ACTION_UPDATE, "selected_candidate_slug": canonical_slug, "same_real_world_event": True, "material_new_update": True, "independently_newsworthy_followup": False, "confidence": 0.97, "shared_anchors": ["same Sunday Port St. Lucie tornado and warning"], "novel_facts": ["NWS explanation"], "reason": "The explanation belongs in the retained tornado accountability canonical.", "validation_errors": [], "resolution_pass": True})
    decision, selected, _ = g._run_terminal_permalink_gate(incoming, [candidate["article"]], {"entries": {}}, g._new_semantic_publication_gate_report())
    assert decision["action"] == g.SEMANTIC_ACTION_UPDATE
    assert selected["slug"] == canonical_slug
