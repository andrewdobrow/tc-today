from __future__ import annotations

import importlib
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
                self.messages = types.SimpleNamespace(
                    create=lambda **kwargs: (_ for _ in ()).throw(
                        RuntimeError("unexpected model call")
                    )
                )

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def test_exact_trash_fee_resolution_lead_is_semantically_self_contained():
    g = _load_generate()
    body = (
        "Port St. Lucie residents will pay $482.16 annually for trash service after the "
        "City Council approved a $14.83 increase to the solid waste assessment Monday night. "
        "The council approved Resolution 26-R70, raising the annual assessment from $467.33 "
        "per dwelling unit for the fiscal year beginning in October. There was no public "
        "comment or council discussion before the item was read and approved.\n\n"
        "The assessment pays for garbage collection, disposal services, facilities and "
        "related solid waste programs."
    )
    item = {
        "headline": "Port St. Lucie approves $14.83 annual trash fee increase with no public comment",
        "source_title": "Port St. Lucie approves higher annual trash fee for residents despite pickup woes - WPEC",
        "body": body,
        "article_text": body,
        "feed_url": "https://example.com/local.rss",
    }

    diagnostics = g._article_framing_diagnostics(item, item)

    assert diagnostics["passed"] is True
    assert diagnostics["lead_independence"]["undefined_references"] == []
    assert "named_measure_undefined_in_lead" not in diagnostics["missing"]


def test_bare_resolution_mention_without_effect_still_fails_closed():
    g = _load_generate()
    body = (
        "The Port St. Lucie City Council approved Resolution 26-R70 Monday night during its "
        "regular meeting. Council members voted unanimously after the item was read.\n\n"
        "Additional implementation details will be published separately."
    )
    item = {
        "headline": "Port St. Lucie City Council approves Resolution 26-R70",
        "source_title": "Port St. Lucie City Council approves Resolution 26-R70",
        "body": body,
        "article_text": body,
        "feed_url": "https://example.com/local.rss",
    }

    diagnostics = g._article_framing_diagnostics(item, item)

    assert diagnostics["passed"] is False
    assert "named_measure_undefined_in_lead" in diagnostics["missing"]


def test_exact_border_collie_surrender_update_contains_original_rescue_context():
    g = _load_generate()
    canonical_headline = (
        "36 dogs rescued from Palm City home face long recovery at Humane Society of Treasure Coast"
    )
    canonical_body = (
        "The Humane Society of the Treasure Coast is caring for 36 Border Collies rescued "
        "from a Palm City home after investigators found the dogs living in poor conditions. "
        "Paige O'Donnell was arrested on animal-cruelty charges."
    )
    body = (
        "All 36 Border Collies removed from a Palm City home on Southwest Alligator Street "
        "earlier this month have been legally surrendered to the Humane Society of the "
        "Treasure Coast, allowing the shelter to move forward with medical evaluations and "
        "adoptions starting Sept. 1. The dogs were rescued Aug. 10 from conditions where "
        "investigators said they were living without air conditioning and surrounded by feces, "
        "urine-soaked materials and debris.\n\n"
        "Paige O'Donnell, 62, was arrested in the case and faces 72 charges."
    )
    source = {
        "title": "All 36 Border Collies surrendered after Palm City case; adoption applications open Sept. 1 - WPEC",
        "story_form": "update",
        "article_text": body,
        "_canonical_context_headline": canonical_headline,
        "_canonical_context_body": canonical_body,
    }
    item = {
        "headline": "All 36 Border Collies from Palm City cruelty case legally surrendered; adoption applications open Sept. 1",
        "story_form": "update",
        "body": body,
        "_canonical_context_headline": canonical_headline,
        "_canonical_context_body": canonical_body,
    }

    diagnostics = g._update_lead_diagnostics(item, source)

    assert diagnostics["required"] is True
    assert diagnostics["baseline_anchor"] == "abuse_or_neglect"
    assert diagnostics["baseline_anchor_present"] is True
    assert diagnostics["baseline_present"] is True
    assert diagnostics["novelty_present"] is True
    assert diagnostics["passed"] is True
    assert diagnostics["missing"] == []


def test_enforced_crime_contract_cannot_be_vetoed_by_stale_classifier_label(monkeypatch):
    g = _load_generate()
    title = "Man charged with manslaughter after BB gun shooting in Fort Pierce - WPBF"
    item = {
        "title": title,
        "source_title": title,
        "headline": "Fort Pierce man charged with manslaughter after fatal BB gun shooting near elementary school",
        "teaser": "Jabari Cowart faces a manslaughter charge after Fort Pierce police say a 34-year-old man died in a BB gun shooting.",
        "body": (
            "Fort Pierce police charged Jabari Cowart with manslaughter after a 34-year-old "
            "man died in a BB gun shooting in the 2900 block of Avenue G. Cowart is being held "
            "at the St. Lucie County jail."
        ),
        "source_quality": "full",
        "feed_url": "https://www.wpbf.com/local.rss",
    }
    monkeypatch.setattr(g, "STORY_CLASSIFICATION", {title.lower(): {"st_lucie"}})

    contract = g._category_eligibility_contract_assessment("crime", item)
    assert contract["mode"] == "enforce"
    assert contract["eligible"] is True
    assert g._hero_eligible("crime", item) is True


def test_enforced_crime_contract_still_rejects_noncrime_weather_even_if_classifier_says_crime(monkeypatch):
    g = _load_generate()
    title = "NWS confirms EF0 tornado touched down Sunday in Port St. Lucie"
    item = {
        "title": title,
        "source_title": title,
        "headline": title,
        "teaser": "The National Weather Service confirmed an EF0 tornado in Port St. Lucie.",
        "body": "The tornado crossed the St. Lucie River as a waterspout and damaged fences.",
        "source_quality": "full",
        "feed_url": "https://example.com/local.rss",
    }
    monkeypatch.setattr(g, "STORY_CLASSIFICATION", {title.lower(): {"crime"}})

    contract = g._category_eligibility_contract_assessment("crime", item)
    assert contract["eligible"] is False
    assert g._hero_eligible("crime", item) is False


def test_county_hero_is_not_demoted_just_because_topic_section_uses_same_fresh_story():
    g = _load_generate()
    headline = "Vero Beach man crashes while fleeing deputies, K9 finds him hiding under brush"
    top = {
        "category_key": "crime",
        "category_label": "Crime & Safety",
        "hero": {"headline": headline},
        "cards": [],
    }
    county = {
        "category_key": "indian_river",
        "category_label": "Indian River County",
        "hero": {"headline": headline},
        "cards": [
            {
                "headline": "Gun used in Vero Beach homicide belonged to suspect's ex-wife, sheriff says"
            }
        ],
    }

    g.promote_duplicate_heroes(top, [top, county])

    assert county["hero"]["headline"] == headline
    assert county["cards"][0]["headline"].startswith("Gun used in Vero Beach homicide")


def _shadow_source(index, title, body, url, *, story_id="", independent=False):
    return {
        "source_index": index,
        "title": title,
        "published": "Mon, 24 Aug 2026 21:31:00 GMT",
        "source_type": "full_source",
        "source_quality": "full",
        "hero_eligible": "yes",
        "category_match_score": 10,
        "story_form": "standard",
        "article_text": body,
        "summary": body[:400],
        "source_url": url,
        "link": url,
        "editorial_story_id": story_id,
        "publication_relationship": "independent_followup" if independent else "",
        "_semantic_independent_followup": independent,
    }


def test_shadow_reuses_live_publication_identity_to_collapse_same_event_angles():
    g = _load_generate()
    g.SEMANTIC_PUBLICATION_SOURCE_OUTCOMES.clear()
    main_url = "https://example.com/nws-confirmation"
    cleanup_url = "https://example.com/resident-cleanup"
    canonical = "2026-08-25-authoritative-port-st-lucie-tornado"
    g.SEMANTIC_PUBLICATION_SOURCE_OUTCOMES[main_url] = {
        "action": "update_existing_canonical",
        "selected_candidate_slug": canonical,
        "independent_followup_authorized": False,
    }
    g.SEMANTIC_PUBLICATION_SOURCE_OUTCOMES[cleanup_url] = {
        "action": "update_existing_canonical",
        "selected_candidate_slug": canonical,
        "independent_followup_authorized": False,
    }
    packet = {
        "source_inputs": [
            _shadow_source(1, "Fort Pierce manslaughter charge", "A separate crime story.", "https://example.com/crime"),
            _shadow_source(2, "NWS confirms EF0 tornado in Port St. Lucie", "NWS confirmed a 75 mph EF0 tornado crossed the St. Lucie River and damaged fences.", main_url),
            _shadow_source(3, "Port St. Lucie residents clean up tornado damage", "Residents cleaned up fences and debris after the same EF0 tornado crossed the St. Lucie River.", cleanup_url),
        ]
    }
    data = {
        "hero": {"headline": "Fort Pierce manslaughter charge", "source_index": 1},
        "cards": [
            {"headline": "NWS confirms EF0 tornado", "source_index": 2},
            {"headline": "Residents clean up tornado damage", "source_index": 3},
        ],
    }

    diagnostics = g._assignment_shadow_consolidate_event_cluster_angles(data, packet)

    assert [card["source_index"] for card in data["cards"]] == [2]
    assert diagnostics == [
        {
            "dropped_source_index": 3,
            "dropped_headline": "Residents clean up tornado damage",
            "retained_source_index": 2,
            "retained_headline": "NWS confirms EF0 tornado",
            "reason": "shared_live_publication_canonical",
            "material_update_replaced_prior": False,
        }
    ]


def test_shadow_preserves_publication_authorized_independent_followup():
    g = _load_generate()
    g.SEMANTIC_PUBLICATION_SOURCE_OUTCOMES.clear()
    main_url = "https://example.com/nws-confirmation-2"
    alert_url = "https://example.com/late-alert-accountability"
    canonical = "2026-08-25-authoritative-port-st-lucie-tornado"
    g.SEMANTIC_PUBLICATION_SOURCE_OUTCOMES[main_url] = {
        "action": "update_existing_canonical",
        "selected_candidate_slug": canonical,
        "independent_followup_authorized": False,
    }
    g.SEMANTIC_PUBLICATION_SOURCE_OUTCOMES[alert_url] = {
        "action": "new_story",
        "selected_candidate_slug": canonical,
        "independent_followup_authorized": True,
    }
    packet = {
        "source_inputs": [
            _shadow_source(1, "NWS confirms EF0 tornado in Port St. Lucie", "NWS confirmed the EF0 tornado and its 75 mph winds.", main_url),
            _shadow_source(
                2,
                "Port St. Lucie residents question why tornado alerts arrived late",
                "Residents say emergency alerts arrived after the EF0 tornado passed, raising an accountability question about warnings.",
                alert_url,
                story_id="story_alert_accountability",
                independent=True,
            ),
        ]
    }
    data = {
        "hero": {"headline": "NWS confirms EF0 tornado", "source_index": 1},
        "cards": [{"headline": "Residents question late alerts", "source_index": 2}],
    }

    diagnostics = g._assignment_shadow_consolidate_event_cluster_angles(data, packet)

    assert [card["source_index"] for card in data["cards"]] == [2]
    assert diagnostics == []


def test_actual_tornado_angle_shift_reaches_semantic_adjudication_and_collapses(monkeypatch):
    g = _load_generate()
    g.SEMANTIC_PUBLICATION_SOURCE_OUTCOMES.clear()
    g.ASSIGNMENT_SHADOW_SEMANTIC_PAIR_CACHE.clear()
    # These are the actual generated facts from the contaminated Aug. 25 bakeoff,
    # reduced only for quote length while preserving the natural vocabulary split.
    nws_body = (
        "An EF0 tornado touched down in Port St. Lucie Sunday evening, with maximum estimated "
        "wind gusts between 65 and 75 mph. It moved over the St. Lucie River, where it was "
        "seen as a waterspout. According to the National Weather Service, the tornado began "
        "at 6:10 p.m. near SE Kitchen Cove Lane and SE Morningside Boulevard. The track length "
        "was 2.1 miles, with a maximum width of 200 yards. Several residents submitted photos "
        "and videos of funnel clouds, and the weather service conducted a storm survey Monday."
    )
    cleanup_body = (
        "Aaron Christiansen said he was home around 6 p.m. Sunday when he noticed something "
        "strange through his window near Southbend Boulevard and Southeast Navy Avenue. He saw "
        "dark clouds and debris and had about 10 seconds to take cover before the storm hit. "
        "His patio furniture was submerged in his pool, his pool fence was blown toward his "
        "home, debris was scattered across the ground and plants were blown away. Christiansen "
        "said he received the emergency alert after the storm had already hit and planned to "
        "begin cleanup Monday and have his roof inspected."
    )
    packet = {
        "source_inputs": [
            _shadow_source(1, "Fort Pierce manslaughter charge", "Separate crime story.", "https://example.com/crime-2"),
            _shadow_source(2, "NWS confirms EF0 tornado touched down Sunday in Port St. Lucie", nws_body, "https://example.com/nws-natural"),
            _shadow_source(3, "Port St. Lucie residents clean up tornado damage near Southbend Boulevard", cleanup_body, "https://example.com/cleanup-natural"),
        ]
    }
    calls = []

    def _adjudicate(*args, **kwargs):
        calls.append(kwargs)
        candidate_slug = kwargs["candidates"][0]["slug"]
        return {
            "status": "validated",
            "action": g.SEMANTIC_ACTION_DUPLICATE,
            "selected_candidate_slug": candidate_slug,
            "same_real_world_event": True,
            "material_new_update": False,
            "independently_newsworthy_followup": False,
            "confidence": 0.98,
            "shared_anchors": ["same Port St. Lucie tornado"],
            "novel_facts": [],
            "reason": "Resident cleanup is another angle on the same tornado.",
            "validation_errors": [],
        }

    monkeypatch.setattr(g, "adjudicate_semantic_publication_candidates", _adjudicate)
    data = {
        "hero": {"headline": "Fort Pierce manslaughter charge", "source_index": 1},
        "cards": [
            {"headline": "NWS confirms EF0 tornado", "source_index": 2},
            {"headline": "Residents clean up tornado damage", "source_index": 3},
        ],
    }

    diagnostics = g._assignment_shadow_consolidate_event_cluster_angles(data, packet)

    assert len(calls) == 1
    evidence = calls[0]["candidates"][0]["evidence"]
    assert evidence["eligible"] is True
    assert evidence["angle_shift_candidate_continuity"] is True
    assert [card["source_index"] for card in data["cards"]] == [2]
    assert diagnostics[0]["reason"] == "semantic_publication_gate_same_event"


def test_shadow_material_update_replaces_prior_same_event_representation(monkeypatch):
    g = _load_generate()
    g.SEMANTIC_PUBLICATION_SOURCE_OUTCOMES.clear()
    g.ASSIGNMENT_SHADOW_SEMANTIC_PAIR_CACHE.clear()
    old_body = (
        "A tornado touched down in Port St. Lucie near Morningside Boulevard Sunday. "
        "The National Weather Service said a damage survey would be conducted Monday. "
        "Residents reported storm damage near the St. Lucie River."
    )
    update_body = (
        "The National Weather Service confirmed the Port St. Lucie tornado was an EF0 with "
        "winds up to 75 mph. It began near Morningside Boulevard, traveled 2.1 miles and "
        "crossed the St. Lucie River as a waterspout after Sunday's storm."
    )
    packet = {
        "source_inputs": [
            _shadow_source(1, "Tornado touches down in Port St. Lucie; survey Monday", old_body, "https://example.com/pre-survey"),
            _shadow_source(2, "NWS confirms EF0 tornado touched down in Port St. Lucie", update_body, "https://example.com/confirmed-update"),
        ]
    }

    def _adjudicate(*args, **kwargs):
        candidate_slug = kwargs["candidates"][0]["slug"]
        return {
            "status": "validated",
            "action": g.SEMANTIC_ACTION_UPDATE,
            "selected_candidate_slug": candidate_slug,
            "same_real_world_event": True,
            "material_new_update": True,
            "independently_newsworthy_followup": False,
            "confidence": 0.99,
            "shared_anchors": ["same tornado", "same Port St. Lucie location"],
            "novel_facts": ["official EF0 classification", "75 mph winds"],
            "reason": "Official findings materially update the same tornado event.",
            "validation_errors": [],
        }

    monkeypatch.setattr(g, "adjudicate_semantic_publication_candidates", _adjudicate)
    data = {
        "hero": {"headline": "Tornado touches down; survey Monday", "source_index": 1},
        "cards": [{"headline": "NWS confirms EF0 tornado", "source_index": 2}],
    }

    diagnostics = g._assignment_shadow_consolidate_event_cluster_angles(data, packet)

    assert data["hero"]["source_index"] == 2
    assert data["cards"] == []
    assert diagnostics[0]["material_update_replaced_prior"] is True
    assert diagnostics[0]["retained_source_index"] == 2


def test_shadow_angle_shift_recall_does_not_compare_unrelated_same_city_event_family(monkeypatch):
    g = _load_generate()
    g.SEMANTIC_PUBLICATION_SOURCE_OUTCOMES.clear()
    g.ASSIGNMENT_SHADOW_SEMANTIC_PAIR_CACHE.clear()
    tornado = _shadow_source(
        1,
        "NWS confirms EF0 tornado touched down in Port St. Lucie",
        "The National Weather Service confirmed an EF0 tornado crossed Port St. Lucie with 75 mph winds.",
        "https://example.com/tornado-unrelated-check",
    )
    fire = _shadow_source(
        2,
        "Port St. Lucie firefighters contain garage fire on East Erie Drive",
        "Firefighters contained a detached garage fire in Port St. Lucie. The state fire marshal is investigating.",
        "https://example.com/fire-unrelated-check",
    )
    calls = []

    def _unexpected(*args, **kwargs):
        calls.append(kwargs)
        raise AssertionError("unrelated event families must not reach semantic adjudication")

    monkeypatch.setattr(g, "adjudicate_semantic_publication_candidates", _unexpected)
    data = {
        "hero": {"headline": tornado["title"], "source_index": 1},
        "cards": [{"headline": fire["title"], "source_index": 2}],
    }
    diagnostics = g._assignment_shadow_consolidate_event_cluster_angles(
        data, {"source_inputs": [tornado, fire]}
    )

    assert calls == []
    assert [card["source_index"] for card in data["cards"]] == [2]
    assert diagnostics == []


def test_shadow_uses_pre_generation_canonical_context_when_live_gate_has_no_outcome():
    g = _load_generate()
    g.SEMANTIC_PUBLICATION_SOURCE_OUTCOMES.clear()
    canonical = "2026-08-25-authoritative-tornado"
    first = _shadow_source(
        1,
        "NWS confirms EF0 tornado in Port St. Lucie",
        "NWS confirmed the tornado was EF0 with winds up to 75 mph.",
        "https://example.com/context-main",
    )
    second = _shadow_source(
        2,
        "Residents clean up Port St. Lucie tornado damage",
        "Residents cleaned up damage after the same Port St. Lucie tornado.",
        "https://example.com/context-cleanup",
    )
    first["_canonical_context_slug"] = canonical
    second["_canonical_context_slug"] = canonical
    data = {
        "hero": {"headline": first["title"], "source_index": 1},
        "cards": [{"headline": second["title"], "source_index": 2}],
    }

    diagnostics = g._assignment_shadow_consolidate_event_cluster_angles(
        data, {"source_inputs": [first, second]}
    )

    assert data["cards"] == []
    assert diagnostics[0]["reason"] == "shared_live_publication_canonical"
