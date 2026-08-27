from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


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
    spec = importlib.util.spec_from_file_location("generate_final_surface_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _identity_index(*safe_story_ids):
    return types.SimpleNamespace(
        safe_story_ids=set(safe_story_ids),
        all_story_ids=set(safe_story_ids),
    )


def _resolver(card):
    slug = card.get("_archived_slug") or card.get("slug")
    return f"https://treasurecoast.today/articles/{slug}.html" if slug else None


def _write_surface_files(root: Path, archive, redirects):
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "archive.json").write_text(json.dumps(archive), encoding="utf-8")
    (root / "data" / "canonical-redirects.json").write_text(
        json.dumps({"redirects": redirects}), encoding="utf-8"
    )


def _homepage_html(hero_href, card_hrefs):
    cards = "".join(
        f'<a href="{href}" class="grid-card fade-in" data-cat="all"></a>'
        for href in card_hrefs
    )
    return (
        '<section class="hero hero-v3" data-cat-hero="all">'
        f'<a class="hero-v3-link" href="{hero_href}"></a>'
        "</section>"
        + cards
    )


def test_ware_redirect_copy_and_custom_card_collapse_to_custom_canonical(tmp_path):
    g = _load_generate()
    custom_story_id = "custom:ware-award"
    canonical = {
        "slug": g.WARE_AWARD_CANONICAL_SLUG,
        "headline": "St. Lucie Mets pitcher Conner Ware named FSL Pitcher of the Week",
        "teaser": "Ware earned the weekly Florida State League pitching honor.",
        "image_url": "https://treasurecoast.today/images/mets10.png",
        "category_key": "sports",
        "date": "2026-07-28",
        "editorial_story_id": custom_story_id,
        "is_custom": True,
        "authoritative_custom": True,
        "custom_event_key": "sports-award|st-lucie-mets|ware|pitcher-of-the-week|2026-07-27",
    }
    source_slug = next(iter(g.WARE_AWARD_REDIRECT_SOURCE_SLUGS))
    redirects = {source_slug: g.WARE_AWARD_CANONICAL_SLUG}
    context = g._build_final_canonical_surface_context(
        [canonical], tmp_path, identity_index=_identity_index(), redirect_map=redirects
    )
    rss_copy = {
        "headline": "St. Lucie Mets pitcher Conner Ware named Florida State League Pitcher of the Week",
        "_archived_slug": source_slug,
        "cat_key": "st_lucie",
        "cat_label": "St. Lucie County",
        "urgency_score": 8,
    }
    custom_copy = {
        **canonical,
        "_archived_slug": g.WARE_AWARD_CANONICAL_SLUG,
        "cat_key": "sports",
        "cat_label": "Sports",
        "urgency_score": 6,
    }

    kept, report = g._dedupe_homepage_cards_by_permalink(
        [rss_copy, custom_copy],
        _resolver,
        topnews_ids={id(rss_copy), id(custom_copy)},
        surface_context=context,
    )

    assert kept == [custom_copy]
    assert kept[0]["_archived_slug"] == g.WARE_AWARD_CANONICAL_SLUG
    assert kept[0]["headline"] == canonical["headline"]
    # v1.13.2.0: a county container/category label on a duplicate copy is not
    # source authority. The canonical custom Sports article keeps its topic
    # membership, but unsupported St. Lucie membership is not unioned in.
    assert set(kept[0]["category_keys"]) == {"sports"}
    assert report["resolved_unique_identity_count"] == 1
    assert report["removed_count"] == 1
    assert report["removed"][0]["identity_key"] == (
        "custom-event:sports-award|st-lucie-mets|ware|"
        "pitcher-of-the-week|2026-07-27"
    )


def test_big_taste_redirect_source_is_rewritten_even_when_it_is_the_only_card(tmp_path):
    g = _load_generate()
    story_id = "story_000253"
    canonical = {
        "slug": g.BIG_TASTE_CANONICAL_SLUG,
        "headline": "Big Taste of Martin County returns Oct. 6 to support youth mentoring programs",
        "teaser": "The Stuart fundraiser supports Big Brothers Big Sisters mentoring programs.",
        "category_key": "things_to_do",
        "date": "2026-07-23",
        "editorial_story_id": story_id,
    }
    source_slug = next(iter(g.BIG_TASTE_REDIRECT_SOURCE_SLUGS))
    context = g._build_final_canonical_surface_context(
        [canonical],
        tmp_path,
        identity_index=_identity_index(story_id),
        redirect_map={source_slug: g.BIG_TASTE_CANONICAL_SLUG},
    )
    card = {
        "headline": "Big Taste of Martin County fundraiser set for October in Stuart",
        "_archived_slug": source_slug,
        "editorial_story_id": story_id,
        "cat_key": "things_to_do",
        "cat_label": "Things To Do",
    }

    kept, report = g._dedupe_homepage_cards_by_permalink(
        [card], _resolver, surface_context=context
    )

    assert kept == [card]
    assert card["_archived_slug"] == g.BIG_TASTE_CANONICAL_SLUG
    assert card["link"].endswith(f"/{g.BIG_TASTE_CANONICAL_SLUG}.html")
    assert card["headline"] == canonical["headline"]
    assert report["canonical_rewrite_count"] == 1
    assert report["removed_count"] == 0


def test_two_direct_slugs_with_same_safe_story_id_collapse_to_oldest_canonical(tmp_path):
    g = _load_generate()
    story_id = "story_execution_update"
    old = {
        "slug": "2026-07-20-florida-execution-case",
        "headline": "Florida schedules execution in murder case",
        "date": "2026-07-20",
        "editorial_story_id": story_id,
    }
    newer = {
        "slug": "2026-07-29-florida-executes-inmate-in-murder-case",
        "headline": "Florida executes inmate in murder case",
        "date": "2026-07-29",
        "editorial_story_id": story_id,
    }
    context = g._build_final_canonical_surface_context(
        [old, newer], tmp_path, identity_index=_identity_index(story_id), redirect_map={}
    )
    old_card = {**old, "_archived_slug": old["slug"], "cat_key": "florida"}
    new_card = {
        **newer,
        "_archived_slug": newer["slug"],
        "cat_key": "florida",
        "urgency_score": 10,
    }

    kept, report = g._dedupe_homepage_cards_by_permalink(
        [new_card, old_card], _resolver, surface_context=context
    )

    assert len(kept) == 1
    assert kept[0]["_archived_slug"] == old["slug"]
    assert kept[0]["headline"] == old["headline"]
    assert report["removed_count"] == 1
    assert report["removed"][0]["identity_basis"] == "persistent_story_id"


def test_untrusted_shared_story_id_does_not_merge_distinct_direct_articles(tmp_path):
    g = _load_generate()
    story_id = "story_follow_up_family"
    first = {
        "slug": "first-stage",
        "headline": "Investigation begins",
        "date": "2026-07-20",
        "editorial_story_id": story_id,
    }
    second = {
        "slug": "later-arrest",
        "headline": "Suspect arrested after investigation",
        "date": "2026-07-29",
        "editorial_story_id": story_id,
    }
    context = g._build_final_canonical_surface_context(
        [first, second], tmp_path, identity_index=_identity_index(), redirect_map={}
    )
    cards = [
        {**first, "_archived_slug": first["slug"], "cat_key": "crime"},
        {**second, "_archived_slug": second["slug"], "cat_key": "crime"},
    ]

    kept, report = g._dedupe_homepage_cards_by_permalink(
        cards, _resolver, surface_context=context
    )

    assert kept == cards
    assert report["removed_count"] == 0
    assert report["resolved_unique_identity_count"] == 2


def test_card_matching_hero_safe_story_identity_is_removed_even_with_different_slug(tmp_path):
    g = _load_generate()
    story_id = "story_infant_case"
    canonical = {
        "slug": "2026-07-27-infant-case-arrests",
        "headline": "Three arrested in infant death investigation",
        "date": "2026-07-27",
        "editorial_story_id": story_id,
    }
    variant = {
        "slug": "2026-07-28-detective-describes-infant-case-home",
        "headline": "Detective describes conditions in infant death case",
        "date": "2026-07-28",
        "editorial_story_id": story_id,
    }
    context = g._build_final_canonical_surface_context(
        [canonical, variant], tmp_path, identity_index=_identity_index(story_id), redirect_map={}
    )
    card = {**variant, "_archived_slug": variant["slug"], "cat_key": "crime"}

    kept, report = g._dedupe_homepage_cards_by_permalink(
        [card],
        _resolver,
        hero_permalink=f"https://treasurecoast.today/articles/{canonical['slug']}.html",
        surface_context=context,
    )

    assert kept == []
    assert report["removed"][0]["reason"] == "duplicates_front_page_hero_identity"


def test_final_surface_contract_rejects_redirect_source_link(tmp_path):
    g = _load_generate()
    canonical = {
        "slug": g.WARE_AWARD_CANONICAL_SLUG,
        "headline": "Ware named FSL Pitcher of the Week",
        "date": "2026-07-28",
        "editorial_story_id": "custom:ware-award",
        "is_custom": True,
    }
    source_slug = next(iter(g.WARE_AWARD_REDIRECT_SOURCE_SLUGS))
    _write_surface_files(tmp_path, [canonical], [{
        "source_slug": source_slug,
        "target_slug": g.WARE_AWARD_CANONICAL_SLUG,
    }])
    html = _homepage_html(
        "https://treasurecoast.today/articles/unrelated-hero.html",
        [f"https://treasurecoast.today/articles/{source_slug}.html"],
    )

    with pytest.raises(RuntimeError, match="Final canonical surface contract FAILED"):
        g.validate_final_canonical_surface_uniqueness(
            html, tmp_path, identity_index=_identity_index()
        )

    report = json.loads(
        (tmp_path / "data" / "final-canonical-surface-contract.json").read_text()
    )
    assert report["redirect_source_link_count"] == 1
    assert report["passed"] is False


def test_final_surface_contract_rejects_two_direct_urls_for_same_safe_story(tmp_path):
    g = _load_generate()
    story_id = "story_same_event"
    archive = [
        {
            "slug": "older-canonical",
            "headline": "Original headline",
            "date": "2026-07-20",
            "editorial_story_id": story_id,
        },
        {
            "slug": "newer-copy",
            "headline": "Rewritten headline",
            "date": "2026-07-29",
            "editorial_story_id": story_id,
        },
    ]
    _write_surface_files(tmp_path, archive, [])
    html = _homepage_html(
        "https://treasurecoast.today/articles/unique-hero.html",
        [
            "https://treasurecoast.today/articles/older-canonical.html",
            "https://treasurecoast.today/articles/newer-copy.html",
        ],
    )

    with pytest.raises(RuntimeError, match="Final canonical surface contract FAILED"):
        g.validate_final_canonical_surface_uniqueness(
            html, tmp_path, identity_index=_identity_index(story_id)
        )

    report = json.loads(
        (tmp_path / "data" / "final-canonical-surface-contract.json").read_text()
    )
    assert report["canonical_duplicate_count"] == 1
    assert report["redirect_source_link_count"] == 1


def test_final_surface_contract_passes_for_unique_direct_canonical_links(tmp_path):
    g = _load_generate()
    archive = [
        {"slug": "hero", "headline": "Hero", "date": "2026-07-29"},
        {"slug": "one", "headline": "One", "date": "2026-07-29"},
        {"slug": "two", "headline": "Two", "date": "2026-07-29"},
    ]
    _write_surface_files(tmp_path, archive, [])
    html = _homepage_html(
        "https://treasurecoast.today/articles/hero.html",
        [
            "https://treasurecoast.today/articles/one.html",
            "https://treasurecoast.today/articles/two.html",
        ],
    )

    report = g.validate_final_canonical_surface_uniqueness(
        html, tmp_path, identity_index=_identity_index()
    )

    assert report["passed"] is True
    assert report["canonical_duplicate_count"] == 0
    assert report["redirect_source_link_count"] == 0


def test_engine_version_is_compatible_with_final_canonical_surface_dedup():
    import tct_engine.observability as observability

    version = tuple(int(part) for part in observability.ENGINE_VERSION.split("."))
    assert version >= (1, 11, 9, 0)
    assert observability.OBSERVABILITY_SCHEMA_VERSION >= 17


def test_render_pipeline_uses_final_identity_context_and_fails_closed_before_write():
    root = Path(__file__).resolve().parents[1]
    source = (root / "scripts" / "generate.py").read_text(encoding="utf-8")
    render_start = source.index("def render_index(all_categories, top_cat):")
    render_end = source.index("def render_about_page", render_start)
    render_source = source[render_start:render_end]
    assert "_build_final_canonical_surface_context(archive, OUTPUT_DIR)" in render_source
    assert "surface_context=_surface_context" in render_source
    assert '"final-canonical-surface-dedup.json"' in render_source

    final_gate = source.index("validate_final_canonical_surface_uniqueness(index_html, OUTPUT_DIR)")
    literal_gate = source.index("validate_homepage_permalink_uniqueness(index_html, OUTPUT_DIR)")
    index_write = source.index('(OUTPUT_DIR / "index.html").write_text(index_html')
    assert final_gate < literal_gate < index_write


def test_rendered_projection_self_heals_live_item_identity_drift_before_final_gate(tmp_path):
    """Exact production failure class: rich live identity differs from URL projection.

    Two current-run cards can carry distinct live-only incident anchors while their
    persisted archive URLs belong to one safe story. The in-memory deduper may keep
    both; the rendered projection must collapse them using the same URL/archive-only
    identity that the final validator sees.
    """
    g = _load_generate()
    story_id = "story_render_projection_drift"
    archive = [
        {
            "slug": "older-canonical",
            "headline": "Original coverage",
            "date": "2026-08-19",
            "editorial_story_id": story_id,
        },
        {
            "slug": "newer-rewrite",
            "headline": "Later rewrite",
            "date": "2026-08-19",
            "editorial_story_id": story_id,
        },
    ]
    _write_surface_files(tmp_path, archive, [])
    identity_index = _identity_index(story_id)
    context = g._build_final_canonical_surface_context(
        archive, tmp_path, identity_index=identity_index, redirect_map={}
    )
    cards = [
        {
            **archive[0],
            "_archived_slug": archive[0]["slug"],
            "incident_anchor_key": "live-only-anchor-a",
            "cat_key": "crime",
        },
        {
            **archive[1],
            "_archived_slug": archive[1]["slug"],
            "incident_anchor_key": "live-only-anchor-b",
            "cat_key": "martin",
        },
    ]

    # This is the exact mismatch that reached production: rich-object identity can
    # distinguish the cards even though the final public URL projection cannot.
    kept, rich_report = g._dedupe_homepage_cards_by_permalink(
        cards, _resolver, surface_context=context
    )
    assert len(kept) == 2
    assert rich_report["removed_count"] == 0

    html = _homepage_html(
        "https://treasurecoast.today/articles/unique-hero.html",
        [_resolver(card) for card in kept],
    )
    with pytest.raises(RuntimeError, match="Final canonical surface contract FAILED"):
        g.validate_final_canonical_surface_uniqueness(
            html, tmp_path, identity_index=identity_index
        )

    repaired_html, repair = g.repair_final_canonical_surface_projection(
        html, tmp_path, identity_index=identity_index
    )
    assert repair["removed_count"] == 1
    assert repair["removed"][0]["identity_key"] == f"story:{story_id}"
    assert repaired_html.count('class="grid-card fade-in"') == 1

    final_report = g.validate_final_canonical_surface_uniqueness(
        repaired_html, tmp_path, identity_index=identity_index
    )
    assert final_report["passed"] is True
    assert final_report["canonical_duplicate_count"] == 0
    assert final_report["redirect_source_link_count"] == 0



def test_redirect_backed_tornado_card_is_canonicalized_before_it_can_compete_as_independent_homepage_story(tmp_path):
    g = _load_generate()
    canonical_slug = "2026-08-25-port-st-lucie-residents-receive-tornado-emergency-alert-20-minutes-after-storm-p"
    retired_slug = "2026-08-26-national-weather-service-explains-port-st-lucie-tornado-warning"
    canonical = {
        "slug": canonical_slug,
        "headline": "National Weather Service confirms EF-0 tornado touched down in Port St. Lucie Sunday evening",
        "date": "2026-08-25",
        "editorial_story_id": "story_psl_tornado",
    }
    context = g._build_final_canonical_surface_context([canonical], tmp_path, identity_index=_identity_index("story_psl_tornado"), redirect_map={retired_slug: canonical_slug})
    retired_card = {"headline": "NWS explains Port St. Lucie tornado warning", "_archived_slug": retired_slug, "editorial_story_id": "story_psl_tornado", "urgency_score": 10}
    canonical_card = {"headline": canonical["headline"], "_archived_slug": canonical_slug, "editorial_story_id": "story_psl_tornado", "urgency_score": 7}
    kept, report = g._dedupe_homepage_cards_by_permalink([retired_card, canonical_card], _resolver, surface_context=context)
    assert len(kept) == 1
    assert kept[0]["_archived_slug"] == canonical_slug
    assert kept[0]["headline"] == canonical["headline"]
    assert report["removed_count"] == 1
    assert report["canonical_rewrite_count"] >= 1


def test_two_redirect_placements_rebound_to_same_canonical_are_collapsed_before_final_render(tmp_path):
    g = _load_generate()
    canonical = {"slug": "2026-08-25-tornado-canonical", "headline": "Port St. Lucie tornado canonical", "date": "2026-08-25"}
    context = g._build_final_canonical_surface_context([canonical], tmp_path, identity_index=_identity_index(), redirect_map={"old-tornado-alert": canonical["slug"], "nws-tornado-explanation": canonical["slug"]})
    cards = [
        {"headline": "Old tornado alert", "_archived_slug": "old-tornado-alert", "urgency_score": 8},
        {"headline": "NWS tornado explanation", "_archived_slug": "nws-tornado-explanation", "urgency_score": 9},
    ]
    kept, report = g._dedupe_homepage_cards_by_permalink(cards, _resolver, surface_context=context)
    assert len(kept) == 1
    assert kept[0]["_archived_slug"] == canonical["slug"]
    assert kept[0]["headline"] == canonical["headline"]
    assert report["removed_count"] == 1
    assert report["canonical_rewrite_count"] == 2
