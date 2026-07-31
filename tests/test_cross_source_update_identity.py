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
                self.messages = types.SimpleNamespace(create=lambda **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def _canonical(slug, headline, body, date, story_id):
    return {
        "slug": slug,
        "headline": headline,
        "teaser": body[:220],
        "body": body,
        "date": date,
        "first_published": f"{date}T12:00:00-04:00",
        "editorial_story_id": story_id,
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }


def _incoming(title, text, date, story_id, link):
    return {
        "title": title,
        "headline": title,
        "article_text": text,
        "summary": text,
        "body": text,
        "published": date,
        "date": date,
        "link": link,
        "source_url": link,
        "editorial_story_id": story_id,
        "_editorial_story_id": story_id,
        "_editorial_route": "generate_new",
        "_editorial_relationship": "new_story",
    }


DOUBLE_SHOOTING = _canonical(
    "2026-07-19-two-men-killed-in-early-morning-shooting-on-southeast-rivergreen-circle-in-port",
    "Jealousy over woman sparked double fatal shooting in Port St. Lucie, police say",
    (
        "Port St. Lucie police said Carl Loubeau, 24, shot Juliun Stokes, 22, near the "
        "1300 block of Southeast Rivergreen Circle on July 19. Dwayne Walker returned "
        "fire after Loubeau opened fire, and both Loubeau and Stokes died. Investigators "
        "said Walker acted in self-defense and would not be charged."
    ),
    "2026-07-20",
    "story_double_shooting_canonical",
)

DOUBLE_SHOOTING_911 = _incoming(
    "911 calls reveal panic after double fatal shooting in Port St. Lucie neighborhood",
    (
        "Newly released 911 calls capture residents trying to save Carl Loubeau and "
        "Juliun Stokes after gunfire erupted on Southeast Rivergreen Circle on July 19. "
        "Dwayne Walker told dispatchers that Loubeau shot his cousin and that he returned "
        "fire. Police previously ruled Walker acted in self-defense."
    ),
    "2026-07-30",
    "story_fragment_from_google_rss",
    "https://cbs12.com/news/local/911-calls-deadly-port-st-lucie-shooting",
)

ROOF_CHASE = _canonical(
    "2026-07-28-port-st-lucie-police-find-suspect-hiding-on-roof-after-80-mph-chase",
    "Port St. Lucie men flee police at 80 mph, one found hiding on roof of occupied home",
    (
        "Joseph Gary Harris, 42, and Bryan Shawn Baker, 46, fled Port St. Lucie police "
        "in a white Acura on Southwest Becker Road at nearly 80 mph. They abandoned the "
        "car near Southwest Idol Avenue. A K-9 and drone search found Harris hiding on "
        "the roof of an occupied home."
    ),
    "2026-07-28",
    "story_roof_chase_canonical",
)

ROOF_CHASE_ARRESTS = _incoming(
    "Two arrested after high-speed chase through Port St. Lucie ends with one suspect found on occupied home's roof",
    (
        "Port St. Lucie Police arrested Joseph Gary Harris, 42, and Bryan Shawn Baker, "
        "46, after a white Acura reached nearly 80 mph on Southwest Becker Road. The men "
        "ran near Southwest Idol Avenue, and officers using K-9 and drone teams found "
        "Harris on the roof of an occupied home."
    ),
    "2026-07-30",
    "story_roof_chase_fragment",
    "https://www.hometownnewstc.com/news/st_lucie/two-arrested-after-fleeing-police.html",
)

SHARK_RULES = _canonical(
    "2026-07-29-martin-county-commissioners-move-to-rewrite-shark-fishing-rules-after-public-bea",
    "Martin County moves to rewrite shark fishing rules after complaints about drones, chum",
    (
        "Martin County commissioners directed staff to rewrite beach shark fishing rules "
        "after complaints that anglers use drones and remote-controlled boats to drop chum "
        "near swimmers. The proposed ordinance would rely on public-safety restrictions "
        "while complying with Florida fishing law."
    ),
    "2026-07-29",
    "story_shark_rules_canonical",
)

SHARK_RULES_PUSHBACK = _incoming(
    "Martin County commissioners face pushback on proposed changes to beach shark fishing rules",
    (
        "Residents, surfers and marine experts urged Martin County commissioners not to "
        "weaken proposed beach shark fishing rules. Speakers objected to drones, bait and "
        "chum being carried offshore near swimmers while commissioners reviewed changes "
        "to the same county ordinance."
    ),
    "2026-07-30",
    "story_shark_rules_fragment",
    "https://cbs12.com/news/local/martin-county-shark-fishing-laws-pushback",
)

INFANT_DEATH = _canonical(
    "2026-07-25-3-arrested-in-death-of-3-month-old-in-st-lucie-county",
    "3 arrested in death of 3-month-old in St. Lucie County from dehydration and malnutrition",
    (
        "A 3-month-old boy died at a home on Silverstream Circle in Fort Pierce from "
        "dehydration and malnutrition. Nicole Maxwell, Robert Maxwell and Vikki Koon were "
        "later arrested on aggravated manslaughter and child-abuse charges."
    ),
    "2026-07-25",
    "story_infant_death_canonical",
)

INFANT_NEIGHBOR = _incoming(
    "Neighbor on Silverstream Circle says community worried about child before Fort Pierce baby death",
    (
        "A Silverstream Circle neighbor said residents worried about the 3-month-old boy "
        "before he died from dehydration and malnutrition. The account followed the arrests "
        "of Nicole Maxwell, Robert Maxwell and Vikki Koon in the Fort Pierce case."
    ),
    "2026-07-30",
    "story_infant_death_fragment",
    "https://www.wpbf.com/article/florida-neighbor-fort-pierce-baby-death/73259140",
)


def test_three_july_30_cross_source_updates_match_existing_canonicals():
    g = _load_generate()
    for incoming, canonical in (
        (dict(DOUBLE_SHOOTING_911), dict(DOUBLE_SHOOTING)),
        (dict(ROOF_CHASE_ARRESTS), dict(ROOF_CHASE)),
        (dict(SHARK_RULES_PUSHBACK), dict(SHARK_RULES)),
    ):
        evidence = g._cross_source_same_event_evidence(incoming, canonical)
        assert evidence["matched"] is True, evidence
        assert evidence["confidence"] >= 0.90
        assert len(evidence["evidence_dimensions"]) >= 3


def test_cross_source_match_overrides_generate_new_and_attaches_context():
    g = _load_generate()
    archive = [dict(DOUBLE_SHOOTING)]
    source = dict(DOUBLE_SHOOTING_911)
    ledger = g._build_canonical_publication_ledger(archive)

    bindings = g._prepare_story_aware_update_context([source], archive, ledger)

    assert len(bindings) == 1
    assert source["story_form"] == "update"
    assert source["_editorial_route"] == "update_existing"
    assert source["editorial_story_id"] == DOUBLE_SHOOTING["editorial_story_id"]
    assert source["_incoming_fragmented_story_id"] == "story_fragment_from_google_rss"
    assert source["_canonical_context_slug"] == DOUBLE_SHOOTING["slug"]
    assert bindings[0]["match_confidence"] >= 0.90
    assert bindings[0]["evidence_dimensions"]


def test_google_news_wrapper_and_resolved_publisher_do_not_require_source_equality():
    g = _load_generate()
    source = dict(ROOF_CHASE_ARRESTS)
    source["link"] = "https://news.google.com/rss/articles/wrapper-id?oc=5"
    source["source_url"] = ROOF_CHASE_ARRESTS["source_url"]
    ledger = g._build_canonical_publication_ledger([dict(ROOF_CHASE)])

    canonical, basis, _keys = g._canonical_publication_ledger_target(source, ledger)

    assert canonical is not None
    assert canonical["slug"] == ROOF_CHASE["slug"]
    assert basis == "cross-source-same-event"


def test_infant_neighbor_reaction_remains_same_story_across_publishers():
    g = _load_generate()
    evidence = g._cross_source_same_event_evidence(
        dict(INFANT_NEIGHBOR), dict(INFANT_DEATH)
    )
    assert evidence["matched"] is True
    assert "shared_precise_location" in evidence["evidence_dimensions"]
    assert "shared_named_people" in evidence["evidence_dimensions"]


def test_unrelated_shootings_in_same_city_do_not_merge():
    g = _load_generate()
    unrelated = _incoming(
        "Police investigate separate shooting outside Port St. Lucie convenience store",
        (
            "A 36-year-old man was wounded outside a convenience store on Southwest Port "
            "St. Lucie Boulevard on July 29. Detectives are searching for an unknown suspect."
        ),
        "2026-07-30",
        "story_unrelated_shooting",
        "https://example.com/unrelated-shooting",
    )
    evidence = g._cross_source_same_event_evidence(unrelated, dict(DOUBLE_SHOOTING))
    assert evidence["matched"] is False


def test_unrelated_chases_in_same_city_do_not_merge():
    g = _load_generate()
    unrelated = _incoming(
        "Driver arrested after chase on Crosstown Parkway in Port St. Lucie",
        (
            "Maria Lopez was arrested after a blue pickup reached 65 mph on Crosstown "
            "Parkway on July 29 and stopped near Interstate 95. No one climbed onto a roof."
        ),
        "2026-07-30",
        "story_unrelated_chase",
        "https://example.com/unrelated-chase",
    )
    evidence = g._cross_source_same_event_evidence(unrelated, dict(ROOF_CHASE))
    assert evidence["matched"] is False


def test_different_policy_proposals_by_same_commission_do_not_merge():
    g = _load_generate()
    unrelated = _incoming(
        "Martin County commissioners hear pushback on proposed fire assessment changes",
        (
            "Residents urged Martin County commissioners to reject a proposed fire-rescue "
            "assessment increase during Tuesday's budget meeting. The proposal concerns "
            "emergency-service funding, not beach fishing."
        ),
        "2026-07-30",
        "story_fire_assessment",
        "https://example.com/fire-assessment",
    )
    evidence = g._cross_source_same_event_evidence(unrelated, dict(SHARK_RULES))
    assert evidence["matched"] is False


def test_similar_update_wording_without_common_incident_facts_does_not_merge():
    g = _load_generate()
    unrelated = _incoming(
        "911 calls reveal panic after fatal shooting in Port St. Lucie neighborhood",
        (
            "Dispatchers received calls after a different shooting on Southwest Tulip "
            "Boulevard on July 29. The victim was Marcus Reed and no one named Carl "
            "Loubeau, Juliun Stokes or Dwayne Walker was involved."
        ),
        "2026-07-30",
        "story_unrelated_911_calls",
        "https://example.com/unrelated-911-calls",
    )
    evidence = g._cross_source_same_event_evidence(unrelated, dict(DOUBLE_SHOOTING))
    assert evidence["matched"] is False


def test_missing_story_id_still_reuses_cross_source_canonical():
    g = _load_generate()
    source = dict(SHARK_RULES_PUSHBACK)
    source.pop("editorial_story_id", None)
    source.pop("_editorial_story_id", None)
    ledger = g._build_canonical_publication_ledger([dict(SHARK_RULES)])

    canonical, basis, _keys = g._canonical_publication_ledger_target(source, ledger)

    assert canonical is not None
    assert canonical["slug"] == SHARK_RULES["slug"]
    assert basis == "cross-source-same-event"
    assert source["editorial_story_id"] == SHARK_RULES["editorial_story_id"]
    assert source["_editorial_route"] == "update_existing"


def test_cross_source_observability_uses_resolved_publisher_and_final_action():
    g = _load_generate()
    g.CROSS_SOURCE_IDENTITY_OBSERVATIONS.clear()
    source = dict(ROOF_CHASE_ARRESTS)
    source["link"] = "https://news.google.com/rss/articles/wrapper-id?oc=5"
    source["source_url"] = ROOF_CHASE_ARRESTS["source_url"]
    ledger = g._build_canonical_publication_ledger([dict(ROOF_CHASE)])

    canonical, _basis, _keys = g._canonical_publication_ledger_target(source, ledger)
    assert canonical is not None
    g._finalize_cross_source_identity_observation(
        source, "preserve_existing_page_contextless_update_rejected"
    )
    report = g._build_cross_source_update_identity_report()

    assert report["passed"] is True
    assert report["summary"]["match_count"] == 1
    assert report["summary"]["preserved_or_held_count"] == 1
    row = report["matches"][0]
    assert row["publisher"] == "www.hometownnewstc.com"
    assert row["resolved_url"] == ROOF_CHASE_ARRESTS["source_url"]
    assert row["matched_canonical_slug"] == ROOF_CHASE["slug"]
    assert row["incoming_story_id"] == "story_roof_chase_fragment"
    assert row["canonical_story_id"] == ROOF_CHASE["editorial_story_id"]
    assert row["confidence"] >= 0.90
    assert len(row["evidence_dimensions"]) >= 3
    assert row["relationship"] == "same_event"
    assert row["final_publication_action"] == (
        "preserve_existing_page_contextless_update_rejected"
    )


def test_cross_source_contextless_replacement_is_held():
    g = _load_generate()
    source = dict(INFANT_NEIGHBOR)
    ledger = g._build_canonical_publication_ledger([dict(INFANT_DEATH)])
    bindings = g._prepare_story_aware_update_context(
        [source], [dict(INFANT_DEATH)], ledger
    )
    assert bindings
    generated = dict(source)
    generated["headline"] = INFANT_NEIGHBOR["title"]
    generated["source_headline"] = INFANT_NEIGHBOR["title"]
    generated["body"] = (
        "A Silverstream Circle neighbor said residents had worried about the child "
        "before the case drew public attention."
    )

    diagnostics = g._update_replacement_diagnostics(generated, dict(INFANT_DEATH))

    assert diagnostics["passed"] is False
    assert "original_event_context_missing" in diagnostics["missing"]


def test_validated_cross_source_update_preserves_first_published_and_stamps_freshness():
    from datetime import datetime, timezone

    g = _load_generate()
    existing = dict(INFANT_DEATH)
    existing["first_published"] = "Sat, 25 Jul 2026 09:00:00 -0400"
    original_first_published = existing["first_published"]
    update = dict(INFANT_NEIGHBOR)
    update.update({
        "headline": INFANT_NEIGHBOR["title"],
        "source_headline": INFANT_NEIGHBOR["title"],
        "body": (
            "After a 3-month-old Fort Pierce boy died from dehydration and "
            "malnutrition and three caregivers were arrested, a Silverstream Circle "
            "neighbor said residents had worried about the child before the case "
            "became public.\n\nThe neighbor described concerns around the home."
        ),
        "_editorial_route": "update_existing",
        "story_form": "update",
    })
    diagnostics = g._update_replacement_diagnostics(update, existing)
    assert diagnostics["passed"] is True

    stamped = g._record_validated_meaningful_update(
        existing,
        update,
        diagnostics,
        changed=True,
        now=datetime(2026, 7, 30, 22, 0, tzinfo=timezone.utc),
    )

    assert stamped is True
    assert existing["first_published"] == original_first_published
    assert existing["last_meaningful_update_at"] == "2026-07-30T22:00:00Z"
    assert existing["meaningful_update_validated"] is True


def test_cross_source_match_does_not_stamp_meaningful_update_without_novelty_contract():
    from datetime import datetime, timezone

    g = _load_generate()
    existing = dict(INFANT_DEATH)
    update = dict(INFANT_NEIGHBOR)
    update.update({
        "headline": INFANT_NEIGHBOR["title"],
        "body": "The previously reported case remains under investigation.",
        "_editorial_route": "update_existing",
        "story_form": "update",
    })
    diagnostics = g._update_replacement_diagnostics(update, existing)

    stamped = g._record_validated_meaningful_update(
        existing,
        update,
        diagnostics,
        changed=True,
        now=datetime(2026, 7, 30, 22, 0, tzinfo=timezone.utc),
    )

    assert stamped is False
    assert "last_meaningful_update_at" not in existing


def test_recurring_custom_reports_never_use_cross_source_fallback():
    g = _load_generate()
    prior = dict(SHARK_RULES, is_custom=True, authoritative_custom=True)
    later = dict(SHARK_RULES_PUSHBACK, is_custom=True, authoritative_custom=True)

    evidence = g._cross_source_same_event_evidence(later, prior)

    assert evidence["matched"] is False
    assert evidence["reason"] == "custom_publication_outside_cross_source_fallback"


def test_fentanyl_sentencing_does_not_match_unrelated_sebastian_death_warning():
    g = _load_generate()
    canonical = {
        "slug": "2026-07-09-second-decomposed-body-found-near-us-1-in-sebastian-days-after-first-discovery",
        "headline": "Indian River County Sheriff warns of possible bad drugs on streets after two deaths near Sebastian",
        "teaser": (
            "Sheriff Eric Flowers said it is possible bad fentanyl or "
            "methamphetamine is on the streets and urged drug users to seek treatment."
        ),
        "date": "2026-07-09",
        "editorial_story_id": "story-deaths-drug-drugs-eric-fentanyl-dbbbd58a",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }
    incoming = _incoming(
        "Man sentenced to life in prison for selling fentanyl that killed Vero Beach man in 2023",
        (
            "A Los Angeles man was sentenced to life in federal prison after "
            "prosecutors said fentanyl he sold caused the 2023 overdose death of a "
            "Vero Beach man."
        ),
        "2026-07-30",
        "story-fentanyl-sentencing-fragment",
        "https://example.com/vero-beach-fentanyl-sentencing",
    )

    evidence = g._cross_source_same_event_evidence(incoming, canonical)
    ledger = g._build_canonical_publication_ledger([canonical])
    target, _basis, _keys = g._canonical_publication_ledger_target(incoming, ledger)

    assert evidence["matched"] is False
    assert target is None


def test_candidate_blocking_avoids_full_archive_scan(monkeypatch):
    g = _load_generate()
    matching = dict(DOUBLE_SHOOTING)
    unrelated = [
        {
            "slug": f"2026-06-{index:02d}-unrelated-story-{index}",
            "headline": f"Unrelated business opening number {index} in Florida",
            "teaser": "A different company announced an unrelated opening.",
            "date": f"2026-06-{index:02d}",
            "editorial_story_id": f"story-unrelated-{index}",
            "legacy_identity_status": "identified",
            "ranking_eligible": True,
        }
        for index in range(1, 21)
    ]
    ledger = g._build_canonical_publication_ledger([matching, *unrelated])
    calls = []
    original = g._cross_source_same_event_evidence

    def counted(*args, **kwargs):
        calls.append((args[0].get("headline"), args[1].get("headline")))
        return original(*args, **kwargs)

    monkeypatch.setattr(g, "_cross_source_same_event_evidence", counted)
    target, _basis, _keys = g._canonical_publication_ledger_target(
        dict(DOUBLE_SHOOTING_911), ledger
    )

    assert target["slug"] == DOUBLE_SHOOTING["slug"]
    assert len(calls) <= 2


def test_proven_legacy_canonical_adopts_current_story_id_before_live_validation(tmp_path):
    import json

    g = _load_generate()
    canonical = {
        "slug": "2026-06-27-port-st-lucie-man-arrested-after-holding-teens-at-gunpoint-during-orbeez-prank",
        "headline": "Port St. Lucie man arrested after holding teens at gunpoint during Orbeez prank",
        "teaser": "A Port St. Lucie man was arrested after confronting teens during an Orbeez prank.",
        "date": "2026-06-27",
        "legacy_identity_status": "legacy_unresolved",
        "ranking_eligible": False,
    }
    incoming = {
        "headline": "Charges dropped against Port St. Lucie man who held teens at gunpoint during Orbeez prank",
        "editorial_story_id": "story-orbeez-case-current",
        "_editorial_story_id": "story-orbeez-case-current",
    }
    ledger = g._build_canonical_publication_ledger([canonical])

    adopted = g._adopt_missing_canonical_story_id(
        incoming,
        canonical,
        incoming["editorial_story_id"],
        ledger=ledger,
        basis="canonical_publication_ledger:incident",
    )
    assert adopted == "story-orbeez-case-current"
    assert canonical["editorial_story_id"] == adopted
    assert canonical["ranking_eligible"] is True
    assert ledger["key_to_slug"][f"story:{adopted}"] == canonical["slug"]

    (tmp_path / "archive.json").write_text(json.dumps([canonical]), encoding="utf-8")
    live = dict(incoming, slug=canonical["slug"], _archived_slug=canonical["slug"])
    report = g.validate_forward_live_identity(
        [{"category_key": "crime", "hero": live, "cards": []}],
        output_dir=tmp_path,
    )
    assert report["passed"] is True


def test_separate_i95_crashes_and_wrongful_death_cases_do_not_merge():
    g = _load_generate()
    stuart_crash = {
        "headline": "Five hospitalized after multi-vehicle crash and fire on I-95 in Stuart",
        "teaser": "A crash in Stuart closed northbound lanes and sent five people to hospitals.",
        "date": "2026-06-03",
    }
    vero_crash = {
        "headline": "Multi-vehicle crash closes northbound I-95 lanes near Vero Beach",
        "teaser": "A separate crash near Vero Beach closed northbound lanes eleven days later.",
        "date": "2026-06-14",
    }
    turnpike_lawsuit = {
        "headline": "Stuart daughter files wrongful death suit after Florida Turnpike crash killed three",
        "teaser": "The lawsuit concerns a Turnpike collision in St. Lucie County.",
        "date": "2026-06-13",
    }
    gokart_lawsuit = {
        "headline": "Family files wrongful death lawsuit after girl dies in Port St. Lucie go-kart crash",
        "teaser": "The lawsuit concerns a separate crash at an indoor adventure park.",
        "date": "2026-07-20",
    }

    assert g._cross_source_same_event_evidence(stuart_crash, vero_crash)["matched"] is False
    assert g._cross_source_same_event_evidence(turnpike_lawsuit, gokart_lawsuit)["matched"] is False


def test_supreme_court_name_is_not_a_precise_street_location():
    g = _load_generate()
    item = {
        "headline": "Florida Supreme Court adopts new rules",
        "teaser": "The Florida Supreme Court issued an administrative order.",
    }
    assert "florida-supreme-court" not in g._cross_source_precise_locations(item)


def test_production_fentanyl_story_does_not_reuse_sheriff_spokesperson_as_identity():
    g = _load_generate()
    canonical = {
        "slug": "2026-07-09-second-decomposed-body-found-near-us-1-in-sebastian-days-after-first-discovery",
        "headline": "Indian River County Sheriff warns of possible bad drugs on streets after two deaths near Sebastian",
        "teaser": (
            "Indian River County Sheriff Eric Flowers warned that possible bad fentanyl "
            "or methamphetamine may be circulating after two bodies were found near Sebastian."
        ),
        "date": "2026-07-09",
        "legacy_identity_status": "recent_unresolved",
        "ranking_eligible": False,
    }
    incoming = _incoming(
        "Man sentenced to life in prison for selling fentanyl that killed Vero Beach man in 2023 - WPEC",
        (
            "Alfonso Guerrero, 39, was sentenced to life in federal prison after "
            "fentanyl he sold caused David Eller's 2023 overdose death. Indian River "
            "County Sheriff Eric Flowers said the sheriff's office worked with federal "
            "agents during the prosecution."
        ),
        "2026-07-30",
        "story_001485",
        "https://cbs12.com/news/crime/man-sentenced-to-life-in-prison-for-selling-fentanyl-that-killed-vero-beach-man-in-2023",
    )

    evidence = g._cross_source_same_event_evidence(incoming, canonical)
    ledger = g._build_canonical_publication_ledger([canonical])
    target, _basis, _keys = g._canonical_publication_ledger_target(incoming, ledger)

    assert "eric flowers" not in g._cross_source_person_names(incoming)
    assert evidence["matched"] is False, evidence
    assert target is None


def test_production_police_union_story_does_not_match_parking_impersonation():
    g = _load_generate()
    canonical = {
        "slug": "2026-06-17-west-palm-beach-woman-arrested-for-posing-as-parking-official-in-palm-beach-wort",
        "headline": "West Palm Beach woman charged with posing as parking official in $1 scam on Worth Avenue",
        "teaser": (
            "Palm Beach police charged a West Palm Beach woman accused of posing as a "
            "parking official and collecting one-dollar payments on Worth Avenue."
        ),
        "date": "2026-06-17",
        "legacy_identity_status": "recent_unresolved",
        "ranking_eligible": False,
    }
    incoming = _incoming(
        "West Palm Beach police union pushes back on firing of 3 captains, claims 'different standard' applied",
        (
            "The West Palm Beach Fraternal Order of Police challenged Chief Tony "
            "Araujo's decision to uphold the firing of three captains in a double-"
            "dipping timecard investigation. Mayor Keith James discussed the separate "
            "internal-affairs case."
        ),
        "2026-07-30",
        "story_001406",
        "https://www.wptv.com/news/local-news/west-palm-beach-police-union-firing-captains",
    )

    evidence = g._cross_source_same_event_evidence(incoming, canonical)
    ledger = g._build_canonical_publication_ledger([canonical])
    target, _basis, _keys = g._canonical_publication_ledger_target(incoming, ledger)

    assert "west palm beach" not in g._cross_source_person_names(incoming)
    assert evidence["matched"] is False, evidence
    assert target is None


def test_production_sexual_battery_story_does_not_match_roof_chase_source_brand():
    g = _load_generate()
    canonical = dict(ROOF_CHASE)
    canonical["source_headline"] = (
        "Two arrested after fleeing Port St. Lucie Police in high-speed chase - "
        "Hometown News Treasure Coast"
    )
    incoming = _incoming(
        "Fort Pierce man held without bond on sexual battery charges involving child",
        (
            "James Ronald Owens, 58, was arrested by Fort Pierce police on sexual "
            "battery and lewd or lascivious molestation charges involving a child. "
            "Hometown News Treasure Coast reported the allegations span six years."
        ),
        "2026-07-30",
        "story_001424",
        "https://www.hometownnewstc.com/news/st_lucie/fort-pierce-man-jailed-sexual-battery.html",
    )
    incoming["source_headline"] = (
        "Fort Pierce man jailed on charges of sexual battery - Hometown News Treasure Coast"
    )

    evidence = g._cross_source_same_event_evidence(incoming, canonical)
    ledger = g._build_canonical_publication_ledger([canonical])
    target, _basis, _keys = g._canonical_publication_ledger_target(incoming, ledger)

    assert not ({"hometown news", "hometown news treasure"} & g._cross_source_person_names(incoming))
    assert evidence["matched"] is False, evidence
    assert target is None


def test_v1_12_0_6_false_update_repair_restores_exact_canonical_rows(tmp_path):
    import json

    g = _load_generate()
    corrupted = [
        {
            "slug": "2026-07-09-second-decomposed-body-found-near-us-1-in-sebastian-days-after-first-discovery",
            "headline": "Los Angeles man sentenced to life for selling fentanyl that killed Vero Beach man",
            "source_url": "https://cbs12.com/news/crime/man-sentenced-to-life-in-prison-for-selling-fentanyl",
            "editorial_story_id": "story_001485",
            "identity_origin": "cross_source_canonical_match",
        },
        {
            "slug": "2026-07-30-two-arrested-after-high-speed-chase-through-port-st-lucie-ends-with-one-suspect",
            "headline": "Fort Pierce man held without bond on sexual battery charges involving child",
            "source_url": "https://www.hometownnewstc.com/news/st_lucie/fort-pierce-man-jailed-on-charges-of-sexual-battery.html",
            "editorial_story_id": "story_001427",
            "identity_origin": "cross_source_canonical_match",
        },
        {"slug": "clean-story", "headline": "Clean story", "source_url": "https://example.com/clean"},
    ]
    (tmp_path / "archive.json").write_text(json.dumps(corrupted), encoding="utf-8")

    report = g._repair_v1_12_0_6_false_cross_source_overwrites(tmp_path)
    repaired = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    by_slug = {row["slug"]: row for row in repaired}

    assert report["repaired_count"] == 2
    assert by_slug[corrupted[0]["slug"]]["headline"].startswith("Indian River County Sheriff")
    assert "editorial_story_id" not in by_slug[corrupted[0]["slug"]]
    assert by_slug[corrupted[1]["slug"]]["headline"].startswith("Two arrested after high-speed chase")
    assert by_slug[corrupted[1]["slug"]]["editorial_story_id"] == "story_001427"
    assert by_slug["clean-story"] == corrupted[2]
    saved_report = json.loads(
        (tmp_path / "data" / "cross-source-identity-repair.json").read_text(encoding="utf-8")
    )
    assert saved_report["repaired_count"] == 2
