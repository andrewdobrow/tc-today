from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
import sys
import types
from pathlib import Path


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
    path = Path(__file__).parents[1] / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_published_skip_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _canonical():
    return {
        "slug": "2026-07-23-big-taste-of-martin-county-returns-oct-6-to-support-youth-mentoring-programs",
        "headline": "Big Taste of Martin County returns to Stuart in October to support youth mentoring programs",
        "teaser": (
            "Big Brothers Big Sisters of Palm Beach and Martin Counties is preparing "
            "for the Oct. 6 fundraiser at Atlantic Aviation in Stuart."
        ),
        "category_key": "things_to_do",
        "date": "2026-07-23",
        "lastmod": "2026-07-28",
        "source_url": (
            "https://www.wptv.com/shining-a-light/"
            "big-taste-of-martin-county-returns-to-support-big-brothers-big-sisters-mentoring-programs"
        ),
        "editorial_story_id": "story_000253",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }


def _incoming():
    return {
        "title": "Big Taste of Martin County returns to support Big Brothers Big Sisters mentoring programs",
        "headline": "Big Taste of Martin County fundraiser set for October in Stuart",
        "teaser": (
            "The Big Taste fundraiser returns Oct. 6 at Atlantic Aviation in Stuart "
            "to support youth mentoring programs."
        ),
        "link": _canonical()["source_url"] + "?utm_source=rss",
        "source_url": _canonical()["source_url"] + "?utm_source=rss",
        "editorial_story_id": "story_000253",
        "_editorial_story_id": "story_000253",
        "_editorial_route": "skip",
        "_editorial_relationship": "same_event",
        "_editorial_relationship_confidence": 1.0,
    }


def test_exact_big_taste_registry_skip_is_removed_before_model_generation():
    g = _load_generate()
    kept, suppressed = g._filter_published_skip_candidates(
        [_incoming()], [_canonical()], "things_to_do"
    )
    assert kept == []
    assert len(suppressed) == 1
    assert suppressed[0]["canonical_slug"] == g.BIG_TASTE_CANONICAL_SLUG
    assert suppressed[0]["basis"] == "exact_source_and_persistent_story_skip"



def test_google_wrapper_skip_uses_high_confidence_registry_same_event():
    g = _load_generate()
    item = _incoming()
    item["link"] = "https://news.google.com/rss/articles/BIGTASTE?oc=5"
    item["source_url"] = item["link"]
    item["headline"] = "October fundraiser returns to Atlantic Aviation"
    item["teaser"] = "A community fundraiser is planned this fall."
    canonical, basis = g._published_skip_canonical(item, [_canonical()])
    assert canonical["slug"] == g.BIG_TASTE_CANONICAL_SLUG
    assert basis == "registry_same_event_and_persistent_story_skip"


def test_low_confidence_registry_relationship_cannot_suppress_unproven_source():
    g = _load_generate()
    item = _incoming()
    item["link"] = "https://news.google.com/rss/articles/UNRELATED?oc=5"
    item["source_url"] = item["link"]
    item["headline"] = "Unrelated community fundraiser"
    item["teaser"] = "A different event is planned elsewhere."
    item["_editorial_relationship_confidence"] = 0.7
    canonical, basis = g._published_skip_canonical(item, [_canonical()])
    assert canonical is None
    assert basis == ""

def test_update_existing_route_is_not_suppressed_by_no_change_guard():
    g = _load_generate()
    item = _incoming()
    item["_editorial_route"] = "update_existing"
    kept, suppressed = g._filter_published_skip_candidates(
        [item], [_canonical()], "things_to_do"
    )
    assert kept == [item]
    assert suppressed == []


def test_skip_route_preserves_existing_permalink_without_prospective_drift_quarantine():
    g = _load_generate()
    item = _incoming()
    target, basis = g._find_forward_publication_target(
        item, [_canonical()], "story_000253"
    )
    valid, reason = g._forward_publication_target_valid(
        item,
        target,
        "story_000253",
        basis,
        now=datetime(2026, 7, 29, tzinfo=timezone.utc),
    )
    assert valid is True
    assert reason == "published_skip_preserve_existing"


def test_cached_big_taste_rewrite_is_removed_before_live_reuse():
    g = _load_generate()
    data = {
        "hero": _incoming(),
        "cards": [{"headline": "Different event", "enriched": True}],
    }
    removed = g._suppress_published_skip_placements(
        data, [_canonical()], "things_to_do"
    )
    assert len(removed) == 1
    assert data["hero"]["headline"] == "Different event"




def test_generated_same_story_major_update_reaches_late_materiality_before_suppression(monkeypatch):
    g = _load_generate()
    canonical = _canonical()
    generated = _incoming()
    generated.update({
        "headline": "Body found after search for missing man",
        "body": "Authorities recovered a body during the search and are awaiting positive identification.",
        "published": "2026-09-01T15:00:00+00:00",
    })
    data = {"hero": generated, "cards": []}
    report = {"summary": {}}

    def late_material_update(item, resolved, basis, cache, semantic_report):
        assert resolved["slug"] == canonical["slug"]
        updated = dict(item)
        updated["headline"] = "Canonical refreshed with body recovery"
        updated["_late_published_skip_material_update_promotion"] = True
        return updated, {
            "evaluated": True,
            "promoted": True,
            "action": "update_existing_canonical",
        }

    monkeypatch.setattr(
        g, "_late_published_skip_material_update_promotion", late_material_update
    )
    removed = g._suppress_published_skip_placements(
        data,
        [canonical],
        "martin",
        semantic_cache={},
        semantic_report=report,
    )

    assert removed == []
    assert data["hero"]["headline"] == "Canonical refreshed with body recovery"
    assert report["summary"]["late_published_skip_materiality_evaluations"] == 1
    assert report["summary"]["late_published_skip_materiality_promotions"] == 1


def test_generated_same_story_no_update_is_still_suppressed_after_late_materiality(monkeypatch):
    g = _load_generate()
    canonical = _canonical()
    data = {"hero": _incoming(), "cards": [{"headline": "Different event", "enriched": True}]}
    report = {"summary": {}}

    monkeypatch.setattr(
        g,
        "_late_published_skip_material_update_promotion",
        lambda *args, **kwargs: (None, {
            "evaluated": True,
            "promoted": False,
            "action": "preserve_existing_canonical",
        }),
    )
    removed = g._suppress_published_skip_placements(
        data,
        [canonical],
        "things_to_do",
        semantic_cache={},
        semantic_report=report,
    )

    assert len(removed) == 1
    assert data["hero"]["headline"] == "Different event"
    assert report["summary"]["late_published_skip_materiality_evaluations"] == 1
    assert report["summary"]["late_published_skip_materiality_promotions"] == 0

def test_false_prospective_quarantine_is_repaired_and_newer_duplicate_redirected():
    g = _load_generate()
    old = _canonical()
    old.update({
        "exclude_from_live_recovery": True,
        "ranking_eligible": False,
        "legacy_identity_status": "quarantined_live_mismatch",
        "identity_quarantine_persistent": True,
        "identity_quarantine_reason": "prospective_headline_slug_event_drift",
    })
    new = {
        **_canonical(),
        "slug": "2026-07-29-big-taste-of-martin-county-fundraiser-set-for-october-in-stuart",
        "headline": "Big Taste of Martin County fundraiser set for October in Stuart",
        "date": "2026-07-29",
        "lastmod": "2026-07-29",
    }
    identity_index = types.SimpleNamespace(safe_story_ids={"story_000253"})
    cleaned, redirects, report = g._reconcile_archive_publication_identity(
        [old, new], identity_index
    )
    assert [row["slug"] for row in cleaned] == [g.BIG_TASTE_CANONICAL_SLUG]
    assert cleaned[0].get("exclude_from_live_recovery") is None
    assert cleaned[0]["ranking_eligible"] is True
    assert report["prospective_quarantine_repairs"] == 1
    assert redirects[0]["source_slug"] in g.BIG_TASTE_REDIRECT_SOURCE_SLUGS
    assert redirects[0]["target_slug"] == g.BIG_TASTE_CANONICAL_SLUG


def test_permanent_big_taste_redirect_exists_even_after_duplicate_archive_row_is_gone(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    (tmp_path / "data").mkdir()
    canonical = _canonical()
    cleaned, redirects = g.apply_canonical_story_cleanup(
        [canonical], articles, tmp_path
    )
    assert [row["slug"] for row in cleaned] == [g.BIG_TASTE_CANONICAL_SLUG]
    redirect = next(
        row for row in redirects
        if row["source_slug"] in g.BIG_TASTE_REDIRECT_SOURCE_SLUGS
    )
    assert redirect["target_slug"] == g.BIG_TASTE_CANONICAL_SLUG
    redirect_page = articles / f"{redirect['source_slug']}.html"
    assert redirect_page.exists()
    assert g.BIG_TASTE_CANONICAL_SLUG in redirect_page.read_text(encoding="utf-8")



def test_repeated_source_copy_reuses_first_category_audit_identity():
    g = _load_generate()
    g.CURRENT_RUN_EDITORIAL_IDENTITIES.clear()
    source = _incoming()["source_url"]
    g.CURRENT_RUN_EDITORIAL_IDENTITIES[g._normalized_external_source_url(source)] = {
        "story_id": "story_000253",
        "event_key": "unknown-event-ae622bed41",
        "route": "skip",
        "relationship": "same_event",
        "relationship_confidence": 1.0,
    }
    repeated = {"title": _incoming()["title"], "link": source}
    assert g._stamp_known_current_run_identity(repeated) is True
    assert repeated["_editorial_route"] == "skip"
    assert repeated["_editorial_story_id"] == "story_000253"
    assert repeated["_editorial_relationship"] == "same_event"

def test_category_generation_report_counts_published_story_suppressions():
    g = _load_generate()
    report = g._build_category_generation_report([{
        "status": "generated_live",
        "attempt_count": 0,
        "model_elapsed_seconds": 0,
        "archive_recovery_requested": False,
        "published_story_duplicate_suppression_count": 2,
    }])
    assert report["schema_version"] == 7
    assert report["summary"]["published_story_duplicate_suppression_count"] == 2


def test_category_generation_report_counts_material_update_promotion_observability():
    g = _load_generate()
    report = g._build_category_generation_report([{
        "status": "generated_live",
        "attempt_count": 0,
        "model_elapsed_seconds": 0,
        "archive_recovery_requested": False,
        "material_update_promotion_evaluation_count": 3,
        "material_update_promotion_count": 1,
        "material_update_promotion_cache_hit_count": 1,
        "material_update_promotion_model_call_count": 2,
    }])
    summary = report["summary"]
    assert summary["material_update_promotion_evaluation_count"] == 3
    assert summary["material_update_promotion_count"] == 1
    assert summary["material_update_promotion_cache_hit_count"] == 1
    assert summary["material_update_promotion_model_call_count"] == 2


def test_writer_preserves_repairable_quarantined_skip_without_minting_page(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    old = _canonical()
    old.update({
        "exclude_from_live_recovery": True,
        "ranking_eligible": False,
        "legacy_identity_status": "quarantined_live_mismatch",
        "identity_quarantine_persistent": True,
        "identity_quarantine_reason": "prospective_headline_slug_event_drift",
    })
    (tmp_path / "archive.json").write_text(json.dumps([old]), encoding="utf-8")
    (tmp_path / "custom_articles.json").write_text("[]", encoding="utf-8")
    articles = tmp_path / "articles"
    articles.mkdir()
    canonical_page = articles / f"{g.BIG_TASTE_CANONICAL_SLUG}.html"
    canonical_page.write_text("original canonical page", encoding="utf-8")

    hero = _incoming()
    hero.update({
        "body": " ".join(["Complete source-backed article paragraph."] * 120),
        "enriched": True,
        "image_url": "/images/event.png",
        "urgency_score": 3,
    })
    category = {
        "category_key": "things_to_do",
        "category_label": "Things To Do",
        "hero": hero,
        "cards": [],
    }
    identity_index = types.SimpleNamespace(
        safe_story_ids={"story_000253"},
        all_story_ids={"story_000253"},
    )

    monkeypatch.setattr(g, "load_custom_articles", lambda: [])
    monkeypatch.setattr(g, "_sanitize_authoritative_custom_archive", lambda rows, *_: list(rows))
    monkeypatch.setattr(g, "_purge_nonstory_archive_entries", lambda rows, *_: (list(rows), {}))
    monkeypatch.setattr(g, "apply_canonical_story_cleanup", lambda rows, *_: (list(rows), []))
    monkeypatch.setattr(g, "_repair_archive_article_lead_framing", lambda rows, *_: (list(rows), {}))
    monkeypatch.setattr(g, "_repair_archive_claim_drifted_permalinks", lambda rows, *_: (list(rows), [], {}))
    monkeypatch.setattr(g, "_load_publication_identity_index", lambda: identity_index)
    monkeypatch.setattr(g, "_backfill_archive_editorial_story_ids", lambda rows, *_args, **_kwargs: (list(rows), {}))
    monkeypatch.setattr(g, "_reconcile_archive_publication_identity", lambda rows, *_: (list(rows), [], {}))
    monkeypatch.setattr(g, "enforce_canonical_redirects", lambda rows, *_args, **_kwargs: (list(rows), {}))
    monkeypatch.setattr(g, "_backfill_archive_category_memberships", lambda rows, *_: (list(rows), {}))
    monkeypatch.setattr(g, "_publishable_article", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(g, "render_article_page", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("skip must not render")))
    monkeypatch.setattr(g, "write_story_regression_report", lambda *_args, **_kwargs: {"production_gate_passed": True})
    monkeypatch.setattr(g, "write_story_health_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(g, "render_archive_page", lambda *_args, **_kwargs: "archive")
    monkeypatch.setattr(g, "update_sitemap", lambda *_args, **_kwargs: "sitemap")
    monkeypatch.setattr(g, "update_news_sitemap", lambda *_args, **_kwargs: "news-sitemap")

    g.write_archives([category], category)

    saved = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    assert [row["slug"] for row in saved] == [g.BIG_TASTE_CANONICAL_SLUG]
    assert canonical_page.read_text(encoding="utf-8") == "original canonical page"
    assert not (articles / "2026-07-29-big-taste-of-martin-county-fundraiser-set-for-october-in-stuart.html").exists()
    forward = json.loads((tmp_path / "data" / "forward-publication-identity.json").read_text(encoding="utf-8"))
    assert forward["published_skip_preservations"][0]["canonical_slug"] == g.BIG_TASTE_CANONICAL_SLUG


def _material_update_decision(canonical_slug, novel_fact="material new development"):
    return {
        "status": "validated",
        "action": "update_existing_canonical",
        "recommended_action": "update_existing_canonical",
        "selected_candidate_slug": canonical_slug,
        "same_real_world_event": True,
        "material_new_update": True,
        "confidence": 0.94,
        "shared_anchors": ["same continuing local case"],
        "novel_facts": [novel_fact],
        "reason": "The newer source materially advances the already-published case.",
        "validation_errors": [],
    }


def test_waggle_bodycam_material_update_is_adjudicated_before_skip_suppression(monkeypatch):
    g = _load_generate()
    g.CURRENT_RUN_EDITORIAL_IDENTITIES.clear()
    g.CURRENT_RUN_PREGEN_MATERIAL_UPDATE_DECISIONS.clear()
    g.CURRENT_RUN_PREGEN_MATERIAL_UPDATE_MODEL_CALLS = 0
    canonical = {
        "slug": "2026-08-20-indian-river-county-sheriffs-office-uses-flock-license-plate-cameras-in-search-f",
        "headline": "Indian River County Sheriff's Office uses Flock cameras in search for Vero Beach murder suspect",
        "teaser": "Deputies were searching for Matthew Waggle after Dawn Kriskewic was killed on First Street in Vero Beach.",
        "body": " ".join(["Investigators searched for Matthew Waggle after Dawn Kriskewic was killed in Vero Beach."] * 40),
        "category_key": "crime",
        "date": "2026-08-20",
        "lastmod": "2026-08-20",
        "first_published": "Thu, 20 Aug 2026 12:00:00 -0400",
        "source_url": "https://www.wpbf.com/article/florida-vero-beach-homicide-search-matthew-waggle/old",
        "editorial_story_id": "story_004367",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }
    incoming = {
        "title": "Body cam video shows US Marshals arrest Indian River County murder suspect - WPBF",
        "summary": "U.S. Marshals arrested Matthew Waggle in West Virginia and Florida authorities are working on extradition.",
        "article_text": " ".join(["U.S. Marshals arrested Matthew Waggle in West Virginia and released body camera footage while Florida authorities prepared extradition in the Dawn Kriskewic murder case."] * 18),
        "link": "https://www.wpbf.com/article/florida-indian-river-county-murder-suspect-arrest-video-body-cam/73499988",
        "source_url": "https://www.wpbf.com/article/florida-indian-river-county-murder-suspect-arrest-video-body-cam/73499988",
        "published": "Sat, 22 Aug 2026 03:13:00 GMT",
        "source_quality": "full",
        "editorial_story_id": "story_004367",
        "_editorial_story_id": "story_004367",
        "_editorial_route": "skip",
        "_editorial_relationship": "same_event",
        "_editorial_relationship_confidence": 1.0,
    }
    normalized = g._normalized_external_source_url(incoming["source_url"])
    g.CURRENT_RUN_EDITORIAL_IDENTITIES[normalized] = {
        "story_id": "story_004367",
        "event_key": "named-person-death:dawn-kriskewic",
        "route": "skip",
        "relationship": "same_event",
        "relationship_confidence": 1.0,
        "new_facts": [],
    }
    calls = []

    def adjudicate(*args, **kwargs):
        calls.append(kwargs)
        return _material_update_decision(
            canonical["slug"], "Body camera footage documents Waggle's arrest and extradition is pending"
        )

    monkeypatch.setattr(g, "adjudicate_semantic_publication_candidates", adjudicate)
    cache = {"schema_version": 1, "entries": {}}
    result = g._promote_published_skip_material_updates(
        [incoming], [canonical], "crime", cache=cache
    )

    assert len(calls) == 1
    assert result["evaluated_count"] == 1
    assert result["promoted_count"] == 1
    assert incoming["_editorial_route"] == "update_existing"
    assert incoming["_semantic_material_update"] is True
    assert incoming["_canonical_context_slug"] == canonical["slug"]
    kept, suppressed = g._filter_published_skip_candidates([incoming], [canonical], "crime")
    assert kept == [incoming]
    assert suppressed == []


def test_palm_city_custom_canonical_can_receive_only_validated_material_update(monkeypatch):
    g = _load_generate()
    g.CURRENT_RUN_EDITORIAL_IDENTITIES.clear()
    g.CURRENT_RUN_PREGEN_MATERIAL_UPDATE_DECISIONS.clear()
    g.CURRENT_RUN_PREGEN_MATERIAL_UPDATE_MODEL_CALLS = 0
    canonical = {
        "slug": "2026-07-20-more-than-70-animals-found-in-stuart-home-during-large-scale-hoarding-response",
        "headline": "More Than 70 Animals Found in Stuart Home During Large-Scale Hoarding Response",
        "teaser": "Authorities rescued animals from a Palm City hoarding case and the owner faces criminal charges.",
        "body": " ".join(["Martin County deputies and animal-welfare teams rescued animals from the Palm City hoarding case."] * 45),
        "category_key": "martin",
        "date": "2026-07-20",
        "lastmod": "2026-07-20",
        "first_published": "Mon, 20 Jul 2026 18:07:06 -0400",
        "source_url": "https://www.wptv.com/news/treasure-coast/region-martin-county/palm-city-home-condemned-after-woman-arrested-in-worst-animal-hoarding-case-humane-society-has-seen",
        "editorial_story_id": "custom:887b7f68e86a4dd4d39e4aa93d4f0b89",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
        "is_custom": True,
        "authoritative_custom": True,
    }
    incoming = {
        "title": "Paige O'Donnell relinquishes 36 Border Collies rescued from Palm City hoarding case",
        "summary": "O'Donnell legally surrendered the dogs, clearing the path for adoption applications beginning Sept. 1.",
        "article_text": " ".join(["Paige O'Donnell legally surrendered 36 Border Collies from the Palm City hoarding case, clearing the legal path for adoption applications beginning Sept. 1 after medical evaluations."] * 18),
        "link": "https://www.wptv.com/news/treasure-coast/paige-odonnell-relinquishes-border-collies-rescued-from-palm-city-hoarding-case",
        "source_url": "https://www.wptv.com/news/treasure-coast/paige-odonnell-relinquishes-border-collies-rescued-from-palm-city-hoarding-case",
        "published": "Fri, 21 Aug 2026 15:50:55 GMT",
        "source_quality": "full",
        "editorial_story_id": canonical["editorial_story_id"],
        "_editorial_story_id": canonical["editorial_story_id"],
        "_editorial_route": "skip",
        "_editorial_relationship": "same_event",
        "_editorial_relationship_confidence": 1.0,
    }
    normalized = g._normalized_external_source_url(incoming["source_url"])
    g.CURRENT_RUN_EDITORIAL_IDENTITIES[normalized] = {
        "story_id": canonical["editorial_story_id"],
        "event_key": "animal-rescue-palm-city-cats",
        "route": "skip",
        "relationship": "same_event",
        "relationship_confidence": 1.0,
        "new_facts": [],
    }
    monkeypatch.setattr(
        g,
        "adjudicate_semantic_publication_candidates",
        lambda *args, **kwargs: _material_update_decision(
            canonical["slug"],
            "O'Donnell legally surrendered 36 Border Collies and adoption applications open Sept. 1",
        ),
    )
    result = g._promote_published_skip_material_updates(
        [incoming], [canonical], "martin", cache={"schema_version": 1, "entries": {}}
    )
    assert result["promoted_count"] == 1
    assert incoming["canonical_slug"] == canonical["slug"]
    assert g._authorized_custom_material_update(incoming, canonical) is True

    target, basis = g._find_forward_publication_target(
        incoming, [canonical], canonical["editorial_story_id"]
    )
    assert target is canonical
    valid, reason = g._forward_publication_target_valid(
        incoming,
        target,
        canonical["editorial_story_id"],
        basis,
        now=datetime(2026, 8, 22, tzinfo=timezone.utc),
    )
    assert valid is True
    assert reason == "pre_generation_material_update_authorized"


def test_newer_same_story_semantic_duplicate_remains_suppressed(monkeypatch):
    g = _load_generate()
    g.CURRENT_RUN_PREGEN_MATERIAL_UPDATE_MODEL_CALLS = 0
    canonical = _canonical()
    canonical["lastmod"] = "2026-07-23"
    incoming = _incoming()
    incoming.update({
        "published": "Wed, 29 Jul 2026 12:00:00 GMT",
        "source_quality": "full",
        "summary": " ".join(["The same fundraiser details remain unchanged."] * 40),
        "article_text": " ".join(["The same fundraiser details remain unchanged at Atlantic Aviation in Stuart on Oct. 6."] * 25),
    })
    monkeypatch.setattr(
        g,
        "adjudicate_semantic_publication_candidates",
        lambda *args, **kwargs: {
            "status": "validated",
            "action": "duplicate_use_existing_canonical",
            "recommended_action": "duplicate_use_existing_canonical",
            "selected_candidate_slug": canonical["slug"],
            "same_real_world_event": True,
            "material_new_update": False,
            "confidence": 0.96,
            "shared_anchors": ["same Oct. 6 fundraiser"],
            "novel_facts": [],
            "reason": "No material development.",
            "validation_errors": [],
        },
    )
    result = g._promote_published_skip_material_updates(
        [incoming], [canonical], "things_to_do", cache={"schema_version": 1, "entries": {}}
    )
    assert result["evaluated_count"] == 1
    assert result["promoted_count"] == 0
    assert incoming["_editorial_route"] == "skip"
    kept, suppressed = g._filter_published_skip_candidates(
        [incoming], [canonical], "things_to_do"
    )
    assert kept == []
    assert len(suppressed) == 1


def test_not_newer_published_skip_never_spends_materiality_model_call(monkeypatch):
    g = _load_generate()
    g.CURRENT_RUN_PREGEN_MATERIAL_UPDATE_MODEL_CALLS = 0
    canonical = _canonical()
    canonical["lastmod"] = "2026-07-29"
    incoming = _incoming()
    incoming.update({
        "published": "Tue, 28 Jul 2026 12:00:00 GMT",
        "source_quality": "full",
        "summary": " ".join(["Fundraiser details."] * 80),
        "article_text": " ".join(["Fundraiser details remain the same."] * 80),
    })
    monkeypatch.setattr(
        g,
        "adjudicate_semantic_publication_candidates",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("model must not be called")),
    )
    result = g._promote_published_skip_material_updates(
        [incoming], [canonical], "things_to_do", cache={"schema_version": 1, "entries": {}}
    )
    assert result["evaluated_count"] == 0
    assert result["model_call_count"] == 0
    assert result["promoted_count"] == 0


def test_authorized_custom_material_update_rewrites_one_canonical_without_duplicate(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(g, "SEMANTIC_GATE_CACHE_PATH", tmp_path / "data" / "semantic-publication-gate-cache.json")
    monkeypatch.setattr(g, "SEMANTIC_GATE_REPORT_PATH", tmp_path / "data" / "semantic-publication-gate.json")
    monkeypatch.setattr(g, "EDITORIAL_REGISTRY_PATH", tmp_path / "data" / "editorial_story_registry.json")
    g.CURRENT_RUN_EDITORIAL_IDENTITIES.clear()
    g.CURRENT_RUN_PREGEN_MATERIAL_UPDATE_DECISIONS.clear()
    g.CURRENT_RUN_PREGEN_MATERIAL_UPDATE_MODEL_CALLS = 0

    canonical = {
        "slug": "2026-07-20-more-than-70-animals-found-in-stuart-home-during-large-scale-hoarding-response",
        "headline": "More Than 70 Animals Found in Stuart Home During Large-Scale Hoarding Response",
        "teaser": "Authorities rescued animals from a Palm City hoarding case.",
        "body": " ".join(["Martin County deputies rescued animals from the Palm City hoarding case."] * 45),
        "category_key": "martin",
        "category_label": "Martin County",
        "category_keys": ["martin", "crime"],
        "county_keys": ["martin"],
        "date": "2026-07-20",
        "lastmod": "2026-07-20",
        "first_published": "Mon, 20 Jul 2026 18:07:06 -0400",
        "source_url": "https://www.wptv.com/news/treasure-coast/region-martin-county/palm-city-home-condemned-after-woman-arrested-in-worst-animal-hoarding-case-humane-society-has-seen",
        "editorial_story_id": "custom:887b7f68e86a4dd4d39e4aa93d4f0b89",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
        "is_custom": True,
        "authoritative_custom": True,
        "publication_id": "publication:custom-hoarding",
        "canonical_publication_id": "publication:custom-hoarding",
        "canonical_slug": "2026-07-20-more-than-70-animals-found-in-stuart-home-during-large-scale-hoarding-response",
        "article_word_count": 300,
        "article_paragraph_count": 4,
    }
    (tmp_path / "archive.json").write_text(json.dumps([canonical]), encoding="utf-8")
    (tmp_path / "custom_articles.json").write_text("[]", encoding="utf-8")
    articles = tmp_path / "articles"
    articles.mkdir()
    canonical_page = articles / f"{canonical['slug']}.html"
    canonical_page.write_text("ORIGINAL CUSTOM PAGE", encoding="utf-8")

    source = {
        "title": "Paige O'Donnell relinquishes 36 Border Collies rescued from Palm City hoarding case",
        "summary": "O'Donnell surrendered the dogs, clearing the path for adoption applications beginning Sept. 1.",
        "article_text": " ".join(["Paige O'Donnell legally surrendered 36 Border Collies from the Palm City hoarding case, clearing the path for adoption applications beginning Sept. 1 after medical evaluations."] * 18),
        "link": "https://www.wptv.com/news/treasure-coast/paige-odonnell-relinquishes-border-collies-rescued-from-palm-city-hoarding-case",
        "source_url": "https://www.wptv.com/news/treasure-coast/paige-odonnell-relinquishes-border-collies-rescued-from-palm-city-hoarding-case",
        "published": "Fri, 21 Aug 2026 15:50:55 GMT",
        "source_quality": "full",
        "editorial_story_id": canonical["editorial_story_id"],
        "_editorial_story_id": canonical["editorial_story_id"],
        "_editorial_route": "skip",
        "_editorial_relationship": "same_event",
        "_editorial_relationship_confidence": 1.0,
    }
    normalized = g._normalized_external_source_url(source["source_url"])
    g.CURRENT_RUN_EDITORIAL_IDENTITIES[normalized] = {
        "story_id": canonical["editorial_story_id"],
        "event_key": "animal-rescue-palm-city-cats",
        "route": "skip",
        "relationship": "same_event",
        "relationship_confidence": 1.0,
        "new_facts": [],
    }
    monkeypatch.setattr(
        g,
        "adjudicate_semantic_publication_candidates",
        lambda *args, **kwargs: _material_update_decision(
            canonical["slug"], "Legal surrender clears adoption path beginning Sept. 1"
        ),
    )
    promoted = g._promote_published_skip_material_updates(
        [source], [canonical], "martin", cache={"schema_version": 1, "entries": {}}
    )
    assert promoted["promoted_count"] == 1

    generated = {
        "headline": "Palm City hoarding case updated: 36 Border Collies surrendered, adoptions open Sept. 1",
        "teaser": "The owner has legally surrendered the 36 Border Collies rescued from the Palm City hoarding case, clearing the way for adoption applications Sept. 1.",
        "body": (
            "The owner in the Palm City animal-hoarding case has legally surrendered the 36 Border Collies rescued from the home, a new development that clears the way for adoption applications beginning Sept. 1. The dogs were rescued earlier in the same Martin County case and remain under medical evaluation.\n\n"
            + " ".join(["Shelter staff will complete medical care, vaccinations, microchipping and adoption vetting before placement."] * 45)
        ),
        "source_index": 1,
        "source_url": source["source_url"],
        "published": source["published"],
        "urgency_score": 7,
        "image_url": "/images/martin.png",
        "enriched": True,
    }
    data = {"category_key": "martin", "category_label": "Martin County", "hero": generated, "cards": []}
    assert g._stamp_current_run_story_ids(data, [source]) == 1
    hero = data["hero"]
    assert g._authorized_custom_material_update(hero, canonical) is True

    # Production order regression: the global custom-incident lock runs before
    # write_archives().  A validated canonical-update transaction must survive it.
    removed_by_custom_lock = g.suppress_authoritative_custom_incidents_from_live(
        [data], archived_customs=[canonical], current_customs=[]
    )
    assert removed_by_custom_lock == []
    assert data["hero"] is hero

    identity_index = types.SimpleNamespace(
        safe_story_ids={canonical["editorial_story_id"]},
        all_story_ids={canonical["editorial_story_id"]},
    )
    monkeypatch.setattr(g, "load_custom_articles", lambda: [])
    monkeypatch.setattr(g, "_sanitize_authoritative_custom_archive", lambda rows, *_: list(rows))
    monkeypatch.setattr(g, "_purge_nonstory_archive_entries", lambda rows, *_: (list(rows), {}))
    monkeypatch.setattr(g, "apply_canonical_story_cleanup", lambda rows, *_: (list(rows), []))
    monkeypatch.setattr(g, "_repair_archive_article_lead_framing", lambda rows, *_: (list(rows), {}))
    monkeypatch.setattr(g, "_repair_archive_claim_drifted_permalinks", lambda rows, *_: (list(rows), [], {}))
    monkeypatch.setattr(g, "_load_publication_identity_index", lambda: identity_index)
    monkeypatch.setattr(g, "_backfill_archive_editorial_story_ids", lambda rows, *_args, **_kwargs: (list(rows), {}))
    monkeypatch.setattr(g, "_reconcile_archive_publication_identity", lambda rows, *_: (list(rows), [], {}))
    monkeypatch.setattr(g, "enforce_canonical_redirects", lambda rows, *_args, **_kwargs: (list(rows), {}))
    monkeypatch.setattr(g, "_backfill_archive_category_memberships", lambda rows, *_: (list(rows), {}))
    monkeypatch.setattr(g, "_publishable_article", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(g, "render_article_page", lambda item, *_args, **_kwargs: f"UPDATED::{item['headline']}::{item['body'][:80]}")
    monkeypatch.setattr(g, "write_story_regression_report", lambda *_args, **_kwargs: {"production_gate_passed": True})
    monkeypatch.setattr(g, "write_story_health_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(g, "render_archive_page", lambda *_args, **_kwargs: "archive")
    monkeypatch.setattr(g, "update_sitemap", lambda *_args, **_kwargs: "sitemap")
    monkeypatch.setattr(g, "update_news_sitemap", lambda *_args, **_kwargs: "news-sitemap")

    g.write_archives([data], data)

    assert data["hero"]["_archived_slug"] == canonical["slug"]
    assert data["hero"]["canonical_slug"] == canonical["slug"]
    assert data["hero"]["link"] == f"{g.SITE_URL}/articles/{canonical['slug']}.html"
    assert data["hero"].get("_publication_skip_reason") in (None, "")

    saved = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    assert len(saved) == 1
    updated = saved[0]
    assert updated["slug"] == canonical["slug"]
    assert updated["is_custom"] is True
    assert updated["authoritative_custom"] is True
    assert updated["headline"] == generated["headline"]
    assert updated["meaningful_update_validated"] is True
    assert updated["meaningful_update_basis"] == "semantic_material_update_gate"
    assert any(
        row.get("role") == "material_update" and row.get("source_url") == normalized
        for row in updated.get("source_history", [])
    )
    assert canonical_page.read_text(encoding="utf-8").startswith("UPDATED::")
    assert len(list(articles.glob("*.html"))) == 1
    semantic_report = json.loads(g.SEMANTIC_GATE_REPORT_PATH.read_text(encoding="utf-8"))
    assert semantic_report["schema_version"] == 5
    assert semantic_report["summary"]["pre_generation_materiality_evaluations"] == 1
    assert semantic_report["summary"]["pre_generation_materiality_promotions"] == 1
    assert semantic_report["summary"]["pre_generation_materiality_model_calls"] == 1
    assert semantic_report["summary"]["pre_generation_materiality_duplicates"] == 0


def test_late_published_skip_material_update_refreshes_exact_canonical(monkeypatch):
    g = _load_generate()
    canonical = {
        "slug": "2026-08-24-tornado-touches-down-in-port-st-lucie-national-weather-service-surveys-damage-mo",
        "headline": "Tornado touches down in Port St. Lucie, National Weather Service surveys damage Monday",
        "teaser": "The National Weather Service said it would survey damage Monday after Sunday's tornado.",
        "body": "The National Weather Service announced late Sunday night that it will conduct a storm survey Monday morning after a tornado touched down near Jessica Clinton Park in Port St. Lucie.",
        "category_key": "st_lucie",
        "date": "2026-08-24",
        "lastmod": "2026-08-24",
        "first_published": "Mon, 24 Aug 2026 06:48:23 -0400",
        "source_url": "https://example.com/pre-survey",
        "editorial_story_id": "story_tornado_psl",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }
    incoming = {
        "title": "NWS confirms EF0 tornado touched down Sunday in Port St. Lucie",
        "headline": "NWS confirms EF0 tornado touched down Sunday in Port St. Lucie",
        "summary": "NWS confirmed an EF0 tornado with peak winds of 75 mph after completing Monday's damage survey.",
        "teaser": "NWS confirmed an EF0 tornado with peak winds of 75 mph after completing Monday's damage survey.",
        "article_text": " ".join([
            "The National Weather Service confirmed an EF0 tornado with peak winds of 75 mph touched down Sunday in Port St. Lucie after a Monday damage survey found a 2.1-mile path and damage to homes."
        ] * 25),
        "body": "The National Weather Service confirmed an EF0 tornado with peak winds of 75 mph touched down Sunday in Port St. Lucie after completing its Monday survey.",
        "link": "https://example.com/nws-confirmed-ef0",
        "source_url": "https://example.com/nws-confirmed-ef0",
        "published": "Mon, 24 Aug 2026 21:31:00 GMT",
        "source_quality": "full",
        "editorial_story_id": "story_tornado_psl",
        "_editorial_story_id": "story_tornado_psl",
        "_editorial_route": "skip",
        "_editorial_relationship": "same_event",
        "_editorial_relationship_confidence": 1.0,
    }

    monkeypatch.setattr(
        g,
        "adjudicate_semantic_publication_candidates",
        lambda *args, **kwargs: _material_update_decision(
            canonical["slug"],
            "NWS completed the survey and confirmed EF0 intensity, 75 mph winds and a 2.1-mile path",
        ),
    )

    def _compose(canonical_arg, incoming_arg, decision_arg, report_arg, *, phase):
        assert canonical_arg["slug"] == canonical["slug"]
        assert phase == "late_published_skip_write_barrier"
        merged = dict(incoming_arg)
        merged.update({
            "headline": "NWS confirms EF0 tornado with 75 mph winds in Port St. Lucie",
            "teaser": "The completed NWS survey confirmed EF0 intensity, 75 mph winds and a 2.1-mile path.",
            "body": (
                "The National Weather Service completed its Monday damage survey and confirmed "
                "the Sunday Port St. Lucie tornado was an EF0 with peak winds of 75 mph and a "
                "2.1-mile path. This updates the earlier report that a survey was still pending."
            ),
            "story_form": "update",
            "_editorial_route": "update_existing",
            "editorial_route": "update_existing",
            "canonical_slug": canonical["slug"],
        })
        return merged, {"status": "validated", "validation_errors": []}

    monkeypatch.setattr(g, "_semantic_material_update_composition", _compose)

    merged, row = g._late_published_skip_material_update_promotion(
        incoming,
        canonical,
        "registry_same_event_and_persistent_story_skip",
        {"schema_version": 1, "entries": {}},
        {"summary": {}},
    )

    assert merged is not None
    assert row["evaluated"] is True
    assert row["promoted"] is True
    assert row["action"] == "update_existing_canonical"
    assert merged["canonical_slug"] == canonical["slug"]
    assert merged["editorial_story_id"] == canonical["editorial_story_id"]
    assert merged["_editorial_route"] == "update_existing"
    assert "confirmed" in merged["body"].lower()
    assert "75 mph" in merged["body"].lower()
    assert g._canonical_write_authorized(merged, canonical) is True


def test_late_published_skip_duplicate_preserves_existing_canonical(monkeypatch):
    g = _load_generate()
    canonical = {
        "slug": "canonical-tornado",
        "headline": "NWS confirms EF0 tornado in Port St. Lucie",
        "teaser": "NWS confirmed an EF0 tornado.",
        "body": "NWS confirmed the EF0 tornado after a damage survey.",
        "category_key": "st_lucie",
        "date": "2026-08-24",
        "lastmod": "2026-08-24",
        "first_published": "Mon, 24 Aug 2026 18:00:00 GMT",
        "source_url": "https://example.com/canonical",
        "editorial_story_id": "story_tornado",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }
    incoming = {
        "title": "NWS confirms EF0 tornado in Port St. Lucie - duplicate wire copy",
        "summary": " ".join(["NWS confirmed the same EF0 tornado after a damage survey."] * 20),
        "article_text": " ".join(["NWS confirmed the same EF0 tornado after a damage survey."] * 25),
        "link": "https://example.com/duplicate",
        "source_url": "https://example.com/duplicate",
        "published": "Mon, 24 Aug 2026 19:00:00 GMT",
        "source_quality": "full",
        "editorial_story_id": "story_tornado",
        "_editorial_story_id": "story_tornado",
        "_editorial_route": "skip",
        "_editorial_relationship": "same_event",
        "_editorial_relationship_confidence": 1.0,
    }
    monkeypatch.setattr(
        g,
        "adjudicate_semantic_publication_candidates",
        lambda *args, **kwargs: {
            "status": "validated",
            "action": "keep_existing_canonical",
            "recommended_action": "keep_existing_canonical",
            "selected_candidate_slug": canonical["slug"],
            "same_real_world_event": True,
            "material_new_update": False,
            "confidence": 0.97,
            "shared_anchors": ["same NWS confirmation"],
            "novel_facts": [],
            "reason": "No material new facts beyond the canonical article.",
            "validation_errors": [],
        },
    )
    monkeypatch.setattr(
        g,
        "_semantic_material_update_composition",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("composer must not run")),
    )

    merged, row = g._late_published_skip_material_update_promotion(
        incoming,
        canonical,
        "registry_same_event_and_persistent_story_skip",
        {"schema_version": 1, "entries": {}},
        {"summary": {}},
    )

    assert merged is None
    assert row["evaluated"] is True
    assert row["promoted"] is False
    assert row["action"] == "preserve_existing_canonical"


def test_late_material_update_composition_failure_leaves_original_skip_row_untouched(monkeypatch):
    g = _load_generate()
    canonical = {
        "slug": "canonical-tornado-hold",
        "headline": "Tornado touches down in Port St. Lucie, NWS plans survey",
        "teaser": "A survey was planned.",
        "body": "NWS said it planned to survey the tornado damage.",
        "category_key": "st_lucie",
        "date": "2026-08-24",
        "lastmod": "2026-08-24",
        "first_published": "Mon, 24 Aug 2026 06:00:00 GMT",
        "source_url": "https://example.com/old-tornado",
        "editorial_story_id": "story_tornado_hold",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }
    incoming = {
        "title": "NWS confirms EF0 tornado with 75 mph winds",
        "summary": " ".join(["NWS confirmed EF0 intensity and 75 mph winds after the survey."] * 20),
        "article_text": " ".join(["NWS confirmed EF0 intensity and 75 mph winds after the survey."] * 25),
        "link": "https://example.com/new-tornado",
        "source_url": "https://example.com/new-tornado",
        "published": "Mon, 24 Aug 2026 20:00:00 GMT",
        "source_quality": "full",
        "editorial_story_id": "story_tornado_hold",
        "_editorial_story_id": "story_tornado_hold",
        "_editorial_route": "skip",
        "_editorial_relationship": "same_event",
        "_editorial_relationship_confidence": 1.0,
    }
    original = dict(incoming)
    monkeypatch.setattr(
        g,
        "adjudicate_semantic_publication_candidates",
        lambda *args, **kwargs: _material_update_decision(
            canonical["slug"], "NWS confirmed EF0 intensity and 75 mph winds"
        ),
    )
    monkeypatch.setattr(
        g,
        "_semantic_material_update_composition",
        lambda *args, **kwargs: (
            None,
            {"status": "context_contract_failed", "validation_errors": ["original_event_context_missing"]},
        ),
    )

    merged, row = g._late_published_skip_material_update_promotion(
        incoming,
        canonical,
        "registry_same_event_and_persistent_story_skip",
        {"schema_version": 1, "entries": {}},
        {"summary": {}},
    )

    assert merged is None
    assert row["action"] == "hold_material_update_composition_failed"
    assert incoming == original
    assert incoming["_editorial_route"] == "skip"
    assert "_canonical_write_authorization" not in incoming


def test_late_validated_material_update_can_refresh_custom_canonical(monkeypatch):
    """A custom permalink is protected from replacement, not frozen from verified updates."""
    g = _load_generate()
    canonical = {
        "slug": "custom-missing-person",
        "headline": "Sheriff searches for missing visitor",
        "teaser": "Deputies are searching for a missing visitor.",
        "body": "Deputies said the visitor was last seen near the beach and asked the public for information.",
        "category_key": "martin",
        "date": "2026-08-29",
        "lastmod": "2026-08-29",
        "first_published": "Sat, 29 Aug 2026 20:00:00 GMT",
        "source_url": "https://example.com/custom-source",
        "editorial_story_id": "custom:missing-person",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
        "is_custom": True,
        "authoritative_custom": True,
    }
    incoming = {
        "title": "Sheriff releases new details in search for missing visitor",
        "summary": "Officials released additional identifying details and search information.",
        "article_text": " ".join(["Officials released additional identifying details and search information."] * 30),
        "link": "https://example.com/followup",
        "source_url": "https://example.com/followup",
        "published": "Sun, 30 Aug 2026 18:00:00 GMT",
        "source_quality": "full",
        "editorial_story_id": canonical["editorial_story_id"],
        "_editorial_story_id": canonical["editorial_story_id"],
        "_editorial_route": "skip",
        "_editorial_relationship": "same_event",
        "_editorial_relationship_confidence": 1.0,
    }
    monkeypatch.setattr(
        g,
        "adjudicate_semantic_publication_candidates",
        lambda *args, **kwargs: _material_update_decision(
            canonical["slug"], "Officials released additional identifying details"
        ),
    )

    def _compose(canonical_arg, incoming_arg, decision_arg, report_arg, *, phase):
        assert canonical_arg is canonical
        assert phase == "late_published_skip_write_barrier"
        merged = dict(incoming_arg)
        merged.update({
            "headline": "Sheriff releases new details in search for missing visitor",
            "teaser": "Officials released additional identifying details in the continuing search.",
            "body": (
                "Officials released additional identifying details in the continuing search for the visitor, "
                "who was first reported missing after being seen near the beach. This materially updates the earlier report."
            ),
            "story_form": "update",
            "canonical_slug": canonical["slug"],
        })
        return merged, {"status": "validated", "validation_errors": []}

    monkeypatch.setattr(g, "_semantic_material_update_composition", _compose)

    merged, row = g._late_published_skip_material_update_promotion(
        incoming,
        canonical,
        "durable_custom_incident_identity:missing-person|visitor",
        {"schema_version": 1, "entries": {}},
        {"summary": {}},
    )

    assert merged is not None
    assert row["promoted"] is True
    assert merged["_late_published_skip_material_update_promotion"] is True
    assert merged["_late_published_skip_material_update_canonical_slug"] == canonical["slug"]
    assert g._canonical_write_authorized(merged, canonical) is True
    assert g._authorized_custom_material_update(merged, canonical) is True


def test_custom_canonical_still_rejects_unverified_external_overwrite():
    g = _load_generate()
    canonical = {
        "slug": "custom-canonical",
        "headline": "Manual TCT story",
        "is_custom": True,
        "authoritative_custom": True,
    }
    incoming = {
        "headline": "Publisher rewrite of manual TCT story",
        "_semantic_material_update": True,
        "canonical_slug": canonical["slug"],
    }

    assert g._authorized_custom_material_update(incoming, canonical) is False


def test_main_uses_main_scoped_semantic_report_for_prearchive_placement_suppression():
    g = _load_generate()
    import inspect

    source = inspect.getsource(g.main)
    assert "semantic_report=_semantic_gate_report" not in source
    assert source.count(
        "semantic_report=_pre_generation_placement_semantic_report"
    ) == 2
    assert "_current_regression_report = write_archives(all_categories, top_cat)" in source



def test_pre_generation_material_update_authority_is_reused_without_timestamp(monkeypatch):
    g = _load_generate()
    canonical = _canonical()
    generated = _incoming()
    generated.update({
        "headline": "Body found in Hutchinson Island mangroves believed to be missing man",
        "body": "Authorities recovered a body during the search and are awaiting positive identification.",
        "_editorial_route": "update_existing",
        "editorial_route": "update_existing",
        "_semantic_material_update": True,
        "_pre_generation_material_update_promotion": True,
        "_pre_generation_material_update_canonical_slug": canonical["slug"],
        "_semantic_material_update_decision": {
            "status": "validated",
            "action": g.SEMANTIC_ACTION_UPDATE,
            "selected_candidate_slug": canonical["slug"],
            "same_real_world_event": True,
            "material_new_update": True,
            "confidence": 0.99,
            "shared_anchors": ["missing person search"],
            "novel_facts": ["body recovered"],
            "reason": "Major development.",
            "validation_errors": [],
        },
    })
    for key in ("source_published", "published_raw", "published", "first_published", "date"):
        generated.pop(key, None)
    g._stamp_canonical_write_authorization(
        generated,
        canonical,
        {
            "outcome": g.IDENTITY_OUTCOME_VERIFIED,
            "identity_outcome": g.IDENTITY_OUTCOME_VERIFIED,
            "evidence_tier": "known_canonical_plus_semantic_materiality",
            "write_authorized": True,
            "proof_type": "published_skip_canonical_plus_semantic_materiality",
            "reason": "Major development.",
            "reason_codes": ["semantic_material_update_validated"],
        },
        basis="pre_generation_material_update_promotion",
    )
    monkeypatch.setattr(
        g,
        "_run_known_canonical_materiality_gate",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not re-adjudicate")),
    )

    updated, row = g._late_published_skip_material_update_promotion(
        generated, canonical, "authorized_canonical_identity_skip", {}, {"summary": {}}
    )

    assert updated is not None
    assert updated["headline"].startswith("Body found")
    assert row["promoted"] is True
    assert row["eligibility_reason"] == "pre_generation_material_update_authority_reused"
    assert row["model_call"] is False


def test_stamp_current_run_story_ids_propagates_source_materiality_receipt():
    g = _load_generate()
    canonical = _canonical()
    source = _incoming()
    source.update({
        "published": "Tue, 01 Sep 2026 19:00:00 GMT",
        "source_quality": "full",
        "article_text": " ".join(["Authorities recovered a body during the missing-person search."] * 60),
    })
    normalized = g._normalized_external_source_url(source["link"])
    g.CURRENT_RUN_EDITORIAL_IDENTITIES = {
        normalized: {
            "story_id": canonical["editorial_story_id"],
            "event_key": "missing-person-example",
            "route": "skip",
            "relationship": "same_event",
            "relationship_confidence": 1.0,
            "new_facts": [],
        }
    }
    data = {
        "hero": {
            "headline": "Body found during missing-person search",
            "source_index": 1,
            "body": "Authorities recovered a body.",
        },
        "cards": [],
    }

    stamped = g._stamp_current_run_story_ids(data, [source])
    assert stamped == 1
    assert data["hero"]["source_published"] == source["published"]
    assert data["hero"]["_source_candidate_publishable_verified"] is True
    should_check, reason = g._published_skip_material_update_candidate(data["hero"], canonical)
    assert should_check is True
    assert reason == "newer_source_requires_materiality_decision"


def test_generated_skip_placement_with_verified_source_receipt_gets_late_materiality(monkeypatch):
    g = _load_generate()
    canonical = _canonical()
    canonical["lastmod"] = "2026-08-29"
    generated = _incoming()
    generated.update({
        "headline": "Body found in Hutchinson Island mangroves believed to be missing man",
        "body": "Authorities recovered a body during the search and are awaiting positive identification.",
        "source_published": "2026-09-01T19:00:00+00:00",
        "_source_candidate_publishable_verified": True,
        "_editorial_route": "skip",
        "editorial_route": "skip",
        "_editorial_relationship": "same_event",
        "_editorial_relationship_confidence": 1.0,
    })
    data = {"hero": generated, "cards": []}
    report = {"summary": {}}

    monkeypatch.setattr(
        g,
        "_run_known_canonical_materiality_gate",
        lambda *args, **kwargs: ({
            "status": "validated",
            "action": g.SEMANTIC_ACTION_UPDATE,
            "selected_candidate_slug": canonical["slug"],
            "same_real_world_event": True,
            "material_new_update": True,
            "confidence": 0.99,
            "shared_anchors": ["missing person search"],
            "novel_facts": ["body recovered"],
            "reason": "Major development.",
            "validation_errors": [],
        }, [], True, False),
    )
    monkeypatch.setattr(
        g,
        "_semantic_material_update_composition",
        lambda canonical_arg, working_arg, decision_arg, report_arg, phase="": (
            dict(working_arg),
            {"status": "validated", "validation_errors": []},
        ),
    )

    removed = g._suppress_published_skip_placements(
        data,
        [canonical],
        "martin",
        semantic_cache={},
        semantic_report=report,
    )

    assert removed == []
    assert data["hero"]["_semantic_material_update"] is True
    assert data["hero"]["_late_published_skip_material_update_promotion"] is True
    assert report["summary"]["late_published_skip_materiality_promotions"] == 1


def test_generated_promoted_custom_canonical_placement_is_not_deleted(monkeypatch):
    g = _load_generate()
    canonical = _canonical()
    canonical.update({
        "is_custom": True,
        "authoritative_custom": True,
    })
    generated = _incoming()
    generated.update({
        "headline": "Body found in Hutchinson Island mangroves believed to be missing man",
        "body": "Authorities recovered a body during the search and are awaiting positive identification.",
        "_editorial_route": "update_existing",
        "editorial_route": "update_existing",
        "_semantic_material_update": True,
        "_pre_generation_material_update_promotion": True,
        "_pre_generation_material_update_canonical_slug": canonical["slug"],
        "_semantic_material_update_decision": {
            "status": "validated",
            "action": g.SEMANTIC_ACTION_UPDATE,
            "selected_candidate_slug": canonical["slug"],
            "same_real_world_event": True,
            "material_new_update": True,
            "confidence": 0.99,
            "novel_facts": ["body recovered"],
        },
    })
    g._stamp_canonical_write_authorization(
        generated,
        canonical,
        {
            "outcome": g.IDENTITY_OUTCOME_VERIFIED,
            "identity_outcome": g.IDENTITY_OUTCOME_VERIFIED,
            "evidence_tier": "known_canonical_plus_semantic_materiality",
            "write_authorized": True,
            "proof_type": "published_skip_canonical_plus_semantic_materiality",
            "reason": "Major development.",
            "reason_codes": ["semantic_material_update_validated"],
        },
        basis="pre_generation_material_update_promotion",
    )
    monkeypatch.setattr(
        g,
        "_published_skip_canonical",
        lambda item, archive: (canonical, "durable_custom_incident_identity:missing-person|michael-debevec"),
    )
    monkeypatch.setattr(
        g,
        "_run_known_canonical_materiality_gate",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must reuse pre-generation authority")),
    )
    data = {"hero": generated, "cards": []}
    report = {"summary": {}}

    removed = g._suppress_published_skip_placements(
        data,
        [canonical],
        "martin",
        semantic_cache={},
        semantic_report=report,
    )

    assert removed == []
    assert data["hero"]["headline"].startswith("Body found")
    assert data["hero"]["_pre_generation_material_update_promotion"] is True
    decisions = report.get("late_published_skip_materiality_decisions") or []
    assert decisions and decisions[0]["promoted"] is True
    assert decisions[0]["eligibility_reason"] == "pre_generation_material_update_authority_reused"


def _debevec_canonical():
    return {
        "slug": "2026-08-29-martin-county-sheriffs-office-searches-for-missing-oklahoma-visitor-last-seen-at-chastain-beach",
        "headline": "Martin County Sheriff's Office searches for missing Oklahoma visitor last seen at Chastain Beach",
        "teaser": "Deputies are searching for Michael Anthony Debevec II after he was last seen near Chastain Beach.",
        "body": (
            "The Martin County Sheriff's Office is searching for Michael Anthony Debevec II, "
            "an Oklahoma visitor who was last seen after going to Chastain Beach. His vehicle "
            "was later found near the beach as deputies continued the missing-person search."
        ),
        "category_key": "martin",
        "date": "2026-08-29",
        "lastmod": "2026-08-29",
        "source_url": "https://example.com/original-debevec-search",
        "editorial_story_id": "story_007411",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
        "is_custom": True,
        "authoritative_custom": True,
    }


def _authorized_debevec_body_source(g):
    canonical = _debevec_canonical()
    decision = {
        "status": "validated",
        "action": g.SEMANTIC_ACTION_UPDATE,
        "recommended_action": g.SEMANTIC_ACTION_UPDATE,
        "selected_candidate_slug": canonical["slug"],
        "same_real_world_event": True,
        "material_new_update": True,
        "confidence": 0.99,
        "shared_anchors": ["Michael Anthony Debevec II", "Chastain Beach"],
        "novel_facts": [
            "A body believed to be Debevec was recovered in mangroves near the House of Refuge",
            "The body was wearing clothing matching what Debevec was believed to be wearing",
            "Positive identification remained pending",
        ],
        "reason": "Body recovery is a major development in the existing missing-person case.",
        "validation_errors": [],
    }
    source = {
        "title": "Martin County Sheriff's Office investigates body found in Hutchinson Island mangroves",
        "headline": "Martin County Sheriff's Office investigates body found in Hutchinson Island mangroves",
        "link": "https://www.wptv.com/news/treasure-coast/region-martin-county/martin-county-sheriffs-office-investigates-body-found-in-hutchinson-island-mangroves",
        "source_url": "https://www.wptv.com/news/treasure-coast/region-martin-county/martin-county-sheriffs-office-investigates-body-found-in-hutchinson-island-mangroves",
        "published": "Mon, 01 Sep 2026 16:05:00 -0400",
        "source_quality": "full",
        "source_type": "full_source",
        "article_text": (
            "The Martin County Sheriff's Office recovered a body from mangroves near the House of Refuge "
            "during the search for Michael Anthony Debevec II. Sheriff John Budensiek said investigators "
            "believe the body may be Debevec because the clothing matched what he was believed to be wearing, "
            "but positive identification was still pending. Investigators had found Debevec's vehicle at "
            "Chastain Beach and later recovered his backpack before locating the body. The medical examiner "
            "will work to determine identity and cause of death. Debevec's family was notified of the discovery."
        ),
        "summary": "A body believed to be missing man Michael Debevec was found in Martin County mangroves.",
        "editorial_story_id": canonical["editorial_story_id"],
        "_editorial_story_id": canonical["editorial_story_id"],
        "_editorial_route": "update_existing",
        "editorial_route": "update_existing",
        "_editorial_relationship": g.IDENTITY_OUTCOME_VERIFIED,
        "_editorial_relationship_confidence": 0.99,
        "_editorial_new_facts": list(decision["novel_facts"]),
        "_semantic_material_update": True,
        "_semantic_material_update_decision": decision,
        "_pre_generation_material_update_promotion": True,
        "_pre_generation_material_update_canonical_slug": canonical["slug"],
        "canonical_slug": canonical["slug"],
    }
    g._attach_canonical_update_context(source, canonical, "test_debevec")
    g._stamp_canonical_write_authorization(
        source,
        canonical,
        {
            "outcome": g.IDENTITY_OUTCOME_VERIFIED,
            "identity_outcome": g.IDENTITY_OUTCOME_VERIFIED,
            "evidence_tier": "known_canonical_plus_semantic_materiality",
            "write_authorized": True,
            "proof_type": "published_skip_canonical_plus_semantic_materiality",
            "reason": "Major body-recovery development.",
            "reason_codes": ["semantic_material_update_validated"],
        },
        basis="pre_generation_material_update_promotion",
    )
    return canonical, source


def test_debevec_validated_material_update_survives_repairable_card_quality_guard():
    g = _load_generate()
    canonical, source = _authorized_debevec_body_source(g)
    generated_card = {
        "headline": "Body found in Hutchinson Island mangroves believed to be missing Port St. Lucie man",
        "body": (
            "A body was recovered from deep within mangroves near the House of Refuge on Tuesday. "
            "Investigators said the deceased person was wearing clothing matching the missing man."
        ),
        "source_index": 1,
    }

    assert g._carry_pre_generation_material_update_authority(generated_card, source) is True
    update_diag = g._update_lead_diagnostics(generated_card, generated_card)
    assert update_diag["passed"] is False
    assert any(code.startswith("original_event_") for code in update_diag["missing"])
    assert g._defer_protected_material_update_quality_failure(
        generated_card, update_diag, guard="contextual_update_lead"
    ) is True
    assert generated_card["_force_semantic_material_update_recomposition"] is True
    assert generated_card["_pre_generation_material_update_canonical_slug"] == canonical["slug"]


def test_debevec_quality_held_generated_card_is_recomposed_not_suppressed(monkeypatch):
    g = _load_generate()
    canonical, source = _authorized_debevec_body_source(g)
    generated = {
        "headline": "Body found in Hutchinson Island mangroves believed to be missing Port St. Lucie man",
        "body": "A body was recovered from deep within the mangroves Tuesday.",
        "source_index": 1,
        "source_headline": source["title"],
        "source_title": source["title"],
        "article_text": source["article_text"],
        "source_summary": source["summary"],
        "source_url": source["source_url"],
        "link": source["source_url"],
    }
    assert g._carry_pre_generation_material_update_authority(generated, source) is True
    generated["_force_semantic_material_update_recomposition"] = True

    repaired = dict(generated)
    repaired.update({
        "headline": "Body found during search for missing Michael Debevec in Martin County",
        "teaser": "A body believed to be Michael Debevec was found during the Martin County search; formal identification remains pending.",
        "body": (
            "Martin County deputies searching for missing Oklahoma visitor Michael Anthony Debevec II recovered "
            "a body Tuesday in mangroves near the House of Refuge, a major development in the search that began "
            "after he was last seen near Chastain Beach. Investigators said the clothing matched what Debevec was "
            "believed to be wearing, although formal identification remained pending.\n\n"
            "Investigators had found Debevec's vehicle at Chastain Beach and later recovered his backpack before "
            "locating the body deeper in the mangroves.\n\n"
            "The medical examiner will work to confirm the identity and determine the cause of death."
        ),
    })

    monkeypatch.setattr(
        g,
        "_published_skip_canonical",
        lambda item, archive: (canonical, "durable_custom_incident_identity:missing-person|michael-anthony-debevec"),
    )
    monkeypatch.setattr(
        g,
        "_semantic_material_update_composition",
        lambda canonical_arg, incoming_arg, decision_arg, report_arg, phase="": (
            dict(repaired),
            {"status": "validated", "validation_errors": []},
        ),
    )
    monkeypatch.setattr(
        g,
        "_article_framing_diagnostics",
        lambda item, source=None: {"required": True, "passed": True, "missing": []},
    )

    data = {"hero": generated, "cards": []}
    report = {"summary": {}}
    removed = g._suppress_published_skip_placements(
        data,
        [canonical],
        "martin",
        semantic_cache={},
        semantic_report=report,
    )

    assert removed == []
    assert data["hero"]["headline"].startswith("Body found during search")
    assert data["hero"].get("_force_semantic_material_update_recomposition") is None
    decisions = report.get("late_published_skip_materiality_decisions") or []
    assert decisions[-1]["eligibility_reason"] == "pre_generation_material_update_quality_recomposed"
    assert decisions[-1]["promoted"] is True


def test_material_update_publication_invariant_fails_when_promoted_update_vanishes(tmp_path):
    g = _load_generate()
    canonical, source = _authorized_debevec_body_source(g)
    g.CURRENT_RUN_SELECTED_MATERIAL_UPDATE_TARGETS = {
        canonical["slug"]: {
            "canonical_slug": canonical["slug"],
            "canonical_headline": canonical["headline"],
            "selected_headlines": ["Body found in Hutchinson Island mangroves believed to be missing Michael Debevec"],
            "source_headlines": [source["title"]],
            "source_urls": [source["source_url"]],
            "max_confidence": 0.99,
        }
    }
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "semantic-publication-gate.json").write_text(
        json.dumps({"material_updates": []}), encoding="utf-8"
    )

    import pytest
    with pytest.raises(RuntimeError, match="MATERIAL UPDATE PUBLICATION INVARIANT FAILED"):
        g._validate_promoted_material_updates_committed(tmp_path)

    report = json.loads((data_dir / "material-update-publication-invariant.json").read_text())
    assert report["passed"] is False
    assert report["missing_target_slugs"] == [canonical["slug"]]


def test_material_update_publication_invariant_passes_after_canonical_commit(tmp_path):
    g = _load_generate()
    canonical, source = _authorized_debevec_body_source(g)
    g.CURRENT_RUN_SELECTED_MATERIAL_UPDATE_TARGETS = {
        canonical["slug"]: {
            "canonical_slug": canonical["slug"],
            "canonical_headline": canonical["headline"],
            "selected_headlines": ["Body found in Hutchinson Island mangroves believed to be missing Michael Debevec"],
            "source_headlines": [source["title"]],
            "source_urls": [source["source_url"]],
            "max_confidence": 0.99,
        }
    }
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "semantic-publication-gate.json").write_text(
        json.dumps({"material_updates": [{
            "target_slug": canonical["slug"],
            "updated_headline": "Body found in Hutchinson Island mangroves believed to be missing Michael Debevec",
        }]}),
        encoding="utf-8",
    )

    report = g._validate_promoted_material_updates_committed(tmp_path)
    assert report["passed"] is True
    assert report["missing_target_slugs"] == []
    assert report["stale_headline_count"] == 0


def test_material_update_publication_invariant_fails_when_headline_stays_stale(tmp_path):
    g = _load_generate()
    canonical, source = _authorized_debevec_body_source(g)
    g.CURRENT_RUN_SELECTED_MATERIAL_UPDATE_TARGETS = {
        canonical["slug"]: {
            "canonical_slug": canonical["slug"],
            "canonical_headline": canonical["headline"],
            "selected_headlines": [
                "Body found in Hutchinson Island mangroves believed to be missing Michael Debevec"
            ],
            "source_headlines": [source["title"]],
            "source_urls": [source["source_url"]],
            "max_confidence": 0.99,
        }
    }
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "semantic-publication-gate.json").write_text(
        json.dumps({"material_updates": [{
            "target_slug": canonical["slug"],
            "updated_headline": canonical["headline"],
        }]}),
        encoding="utf-8",
    )

    import pytest
    with pytest.raises(RuntimeError, match="MATERIAL UPDATE HEADLINE INVARIANT FAILED"):
        g._validate_promoted_material_updates_committed(tmp_path)

    report = json.loads((data_dir / "material-update-publication-invariant.json").read_text())
    assert report["passed"] is False
    assert report["missing_target_slugs"] == []
    assert report["stale_headline_count"] == 1
    assert report["stale_headlines"][0]["canonical_slug"] == canonical["slug"]


def test_debevec_contextless_generated_hero_is_not_deleted_before_recomposition(monkeypatch):
    """Production regression: 2026-09-01 body-recovery copy must survive prose guards."""
    g = _load_generate()
    canonical, source = _authorized_debevec_body_source(g)
    source.update({
        "hero_eligible": "yes",
        "category_match_score": 99,
        "feed_url": "https://example.com/rss",
        "image_url": "",
    })
    payload = json.dumps({
        "hero": {
            "headline": "Body found in Hutchinson Island mangroves believed to be missing Port St. Lucie man",
            "body": (
                "A body was recovered from deep within mangroves near the House of Refuge on Tuesday. "
                "Investigators said the deceased person was wearing clothing matching the missing man."
            ),
            "urgency_score": 9,
            "published": "Mon, 01 Sep 2026 16:05:00 -0400",
            "source_index": 1,
        },
        "cards": [],
    })

    class _Messages:
        def create(self, **kwargs):
            return types.SimpleNamespace(content=[types.SimpleNamespace(text=payload)])

    monkeypatch.setattr(g, "client", types.SimpleNamespace(messages=_Messages()))
    monkeypatch.setattr(g, "load_archive", lambda *args, **kwargs: [])

    data = g.generate_category_content("martin", "Martin County", [source])

    assert data["hero"]["headline"].startswith("Body found")
    assert data["hero"]["_protected_material_update"] is True
    assert data["hero"]["_force_semantic_material_update_recomposition"] is True
    assert data["hero"]["_pre_generation_material_update_canonical_slug"] == canonical["slug"]
    assert data["_contextual_update_lead_rejections"]
    assert data["_article_framing_rejections"]


def test_debevec_protected_material_update_bypasses_only_thinness_until_recomposition(monkeypatch):
    """A selected validated update cannot be discarded as thin before its repair barrier."""
    g = _load_generate()
    canonical, source = _authorized_debevec_body_source(g)
    generated = {
        "headline": "Body found in Hutchinson Island mangroves believed to be missing Port St. Lucie man",
        "body": "A body was found in Hutchinson Island mangroves in Martin County.",
        "source_title": source["title"],
        "article_text": source["article_text"],
        "source_summary": source["summary"],
        "source_url": source["source_url"],
        "link": source["source_url"],
        "category_key": "martin",
    }
    assert g._carry_pre_generation_material_update_authority(generated, source) is True
    generated["_force_semantic_material_update_recomposition"] = True

    # Prove this fixture is actually too thin under the ordinary standalone-article rule.
    assert g._publishable_article(generated, hero=False) is False
    monkeypatch.setattr(g, "_hero_eligible", lambda category_key, item: category_key == "martin")

    assert g._generated_item_passes_final_publication_quality(
        generated, "martin", hero=False
    ) is True

    ordinary = dict(generated)
    ordinary.pop("_force_semantic_material_update_recomposition", None)
    assert g._generated_item_passes_final_publication_quality(
        ordinary, "martin", hero=False
    ) is False


def test_protected_material_update_does_not_bypass_dangerous_jurisdiction_failure():
    g = _load_generate()
    _canonical, source = _authorized_debevec_body_source(g)
    generated = {
        "headline": "Unrelated generated framing",
        "body": "Generated copy drifted outside the verified source jurisdiction.",
    }
    assert g._carry_pre_generation_material_update_authority(generated, source) is True
    diagnostics = {
        "required": True,
        "passed": False,
        "missing": ["generated_jurisdiction_not_supported_by_source"],
    }
    assert g._defer_protected_material_update_quality_failure(
        generated, diagnostics, guard="article_framing"
    ) is False
    assert generated.get("_force_semantic_material_update_recomposition") is not True
