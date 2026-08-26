from __future__ import annotations

import importlib
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime


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


def test_exact_bb_gun_manslaughter_is_not_rejected_because_prevents_contains_event(monkeypatch):
    g = _load_generate()
    title = "Man charged with manslaughter after BB gun shooting in Fort Pierce - WPBF"
    item = {
        "title": title,
        "source_title": title,
        "headline": "Fort Pierce man charged with manslaughter after BB gun shooting near elementary school",
        "teaser": "A Fort Pierce man faces manslaughter after police say a BB gun shooting killed a 34-year-old man.",
        "body": (
            "Fort Pierce police charged Jabari Cowart with manslaughter after a fatal BB gun shooting "
            "in the 2900 block of Avenue G near an elementary school. A firearms expert said following "
            "basic safety procedures prevents accidents when handling projectile weapons."
        ),
        "article_text": (
            "Fort Pierce police charged Jabari Cowart with manslaughter after a fatal BB gun shooting."
        ),
        "source_quality": "full",
        "feed_url": "https://www.wpbf.com/local.rss",
    }
    monkeypatch.setattr(g, "STORY_CLASSIFICATION", {title.lower(): {"st_lucie"}})

    assert g._category_eligibility_contract_assessment("crime", item)["eligible"] is True
    assert g._has_any_bounded_term(g._text_for_category_match(item), ["event"]) is False
    assert g._hero_eligible("crime", item) is True


def test_crime_hard_negative_still_matches_real_event_word():
    g = _load_generate()
    item = {
        "title": "Fort Pierce community event features food and live music",
        "source_title": "Fort Pierce community event features food and live music",
        "headline": "Fort Pierce community event features food and live music",
        "teaser": "The community event will take place Saturday in Fort Pierce.",
        "body": "The event includes vendors, food and live music for local families.",
        "article_text": "The event includes vendors, food and live music for local families.",
        "source_quality": "full",
        "feed_url": "https://example.com/local.rss",
    }
    assert g._has_any_bounded_term(g._text_for_category_match(item), ["event"]) is True
    assert g._hero_eligible("crime", item) is False


def test_fresh_stuart_commission_story_about_monday_meeting_is_not_stale():
    g = _load_generate()
    now = datetime(2026, 8, 26, 0, 45, tzinfo=timezone.utc)
    item = {
        "headline": "Stuart city commission fires city manager, appoints new mayor in overnight leadership shake-up",
        "teaser": "The Stuart City Commission voted Monday night to replace the mayor and fire the city manager.",
        "body": (
            "The Stuart City Commission appointed Eula Clarke as mayor and fired City Manager Michael "
            "Giardino Monday night, less than a week after a new commissioner was elected."
        ),
        "source_url": "https://www.wptv.com/news/treasure-coast/region-martin-county/stuart-city-commission-appoints-new-mayor-fires-city-manager-in-sweeping-overnight-changes",
    }
    published = "Wed, 26 Aug 2026 00:18:46 GMT"
    assert g._category_story_is_stale(item, [], published_raw=published, now=now) is False


def test_fresh_timestamp_is_stale_only_with_older_same_source_receipt():
    g = _load_generate()
    now = datetime(2026, 8, 26, 0, 45, tzinfo=timezone.utc)
    source_url = "https://www.wptv.com/news/local/recycled-old-arrest"
    item = {
        "headline": "Vero Beach man arrested after birthday party assault",
        "teaser": "Deputies said the assault happened Monday.",
        "body": "Investigators said the assault happened Monday and the suspect was arrested after the incident.",
        "source_url": source_url,
    }
    published = format_datetime(now - timedelta(hours=2))
    assert g._category_story_is_stale(item, [], published_raw=published, now=now) is False
    archive = [{
        "headline": item["headline"],
        "source_url": source_url,
        "first_published": (now - timedelta(days=4)).isoformat(),
    }]
    assert g._category_story_is_stale(item, archive, published_raw=published, now=now) is True


def test_exact_border_collie_surrender_and_adoption_is_new_development():
    g = _load_generate()
    canonical_headline = "36 dogs rescued from Palm City home face long recovery at Humane Society of Treasure Coast"
    canonical_body = (
        "Thirty-six Border Collies were rescued Aug. 10 from a Palm City home on Southwest Alligator Street "
        "after investigators found the dogs living without air conditioning and surrounded by waste."
    )
    source_title = "All 36 Border Collies surrendered after Palm City case; adoption applications open Sept. 1 - WPEC"
    lead = (
        "All 36 Border Collies removed from a Palm City home earlier this month have been legally surrendered "
        "to the Humane Society of the Treasure Coast. The dogs were rescued Aug. 10 from a home on Southwest "
        "Alligator Street, where investigators said they found them living without air conditioning and surrounded "
        "by feces, urine-soaked materials and debris."
    )
    source = {
        "title": source_title,
        "story_form": "update",
        "article_text": lead + " Adoption applications will be available beginning Sept. 1.",
        "_canonical_context_headline": canonical_headline,
        "_canonical_context_body": canonical_body,
    }
    item = {
        "headline": "Palm City Border Collie cruelty case: All 36 dogs surrendered, adoptions open Sept. 1",
        "story_form": "update",
        "body": lead + "\n\nAdoption applications open Sept. 1.",
        "_canonical_context_headline": canonical_headline,
        "_canonical_context_body": canonical_body,
    }
    diagnostics = g._update_lead_diagnostics(item, source)
    assert diagnostics["novelty_anchor"] == "legal_or_control_status"
    assert diagnostics["novelty_present"] is True
    assert "new_development_missing" not in diagnostics["missing"]
    assert diagnostics["passed"] is True


def test_assignment_editor_no_hero_eligible_source_is_deterministic_noop(monkeypatch):
    g = _load_generate()

    class _Messages:
        def create(self, **kwargs):
            raise AssertionError("assignment editor must not be called when no source may be hero")

    monkeypatch.setattr(g, "client", types.SimpleNamespace(messages=_Messages()))
    packet = {
        "category_key": "florida",
        "category_label": "Florida",
        "source_inputs": [{
            "source_index": 1,
            "title": "Byron Donalds selects Bryan Avila as running mate in Florida governor's race",
            "published": "Tue, 25 Aug 2026 15:02:49 GMT",
            "source_quality": "full",
            "hero_eligible": "no",
            "category_match_score": 10,
            "story_form": "standard",
            "article_text": "Byron Donalds selected Bryan Avila as his running mate in Florida's governor race.",
        }],
    }
    plan, diagnostics, actual_model, duration = g._run_assignment_editor(packet)
    assert plan == {"hero": None, "cards": []}
    assert diagnostics["no_eligible_hero_source"] is True
    assert diagnostics["source_mapping_valid"] is True
    assert actual_model == "deterministic_noop"
    assert duration == 0.0


def test_dense_same_event_tornado_cleanup_angles_reach_semantic_adjudication():
    from tct_engine.semantic_publication_gate import candidate_evidence

    common = {
        "locality": ["port st lucie"],
        "event_families": ["weather"],
        "published_at": "Tue, 25 Aug 2026 20:44:55 -0400",
    }
    left = {
        **common,
        "headline": "Port St. Lucie residents clean up debris, damaged structures after Sunday tornado",
        "body": (
            "Port St. Lucie residents spent Monday cleaning up after an EF0 tornado. Aron Christiansen pulled "
            "debris and patio furniture from his pool after seeing debris flying near Southbend Boulevard. He had "
            "about 10 seconds to take cover. The storm damaged his backyard fence and patio."
        ),
    }
    right = {
        **common,
        "headline": "Port St. Lucie resident takes cover as possible tornado hits neighborhood Sunday",
        "body": (
            "Aaron Christiansen was near Southbend Boulevard when he saw debris flying and had about 10 seconds "
            "to take cover. After the tornado hit, his patio furniture was in the pool, his pool fence was damaged, "
            "and debris covered his backyard while residents began cleaning up."
        ),
    }
    evidence = candidate_evidence(left, right, window_days=7)
    assert evidence["dense_shared_fact_continuity"] is True
    assert evidence["strong_content_event_continuity"] is True
    assert evidence["eligible"] is True


def test_unrelated_same_city_fire_does_not_enter_dense_tornado_recall():
    from tct_engine.semantic_publication_gate import candidate_evidence

    tornado = {
        "headline": "Port St. Lucie residents clean up debris after Sunday tornado",
        "body": "Residents cleared tornado debris, patio furniture and damaged pool fencing near Southbend Boulevard.",
        "locality": ["port st lucie"],
        "event_families": ["weather"],
        "published_at": "Tue, 25 Aug 2026 20:44:55 -0400",
    }
    fire = {
        "headline": "Port St. Lucie garage fire destroys vehicles as crews protect nearby home",
        "body": "Firefighters contained a detached garage blaze that destroyed a motorhome and Jeep. The fire marshal is investigating.",
        "locality": ["port st lucie"],
        "event_families": ["fire"],
        "published_at": "Tue, 25 Aug 2026 20:50:00 -0400",
    }
    evidence = candidate_evidence(tornado, fire, window_days=7)
    assert evidence["dense_shared_fact_continuity"] is False
    assert evidence["eligible"] is False
