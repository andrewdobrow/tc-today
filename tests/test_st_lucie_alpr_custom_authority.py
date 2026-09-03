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

        class _Messages:
            def create(self, *args, **kwargs):
                raise RuntimeError("AI calls disabled in ALPR identity regression test")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = _Messages()

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def _custom(g):
    return {
        "slug": g.ST_LUCIE_ALPR_POLICY_CANONICAL_SLUG,
        "headline": (
            "St. Lucie County sheriff restricts license plate reader use to "
            "forcible felonies, missing-person cases"
        ),
        "teaser": (
            "The St. Lucie County Sheriff's Office is imposing new restrictions "
            "on automated license plate reader technology."
        ),
        "body": (
            "Sheriff Richard Del Toro limited automated license plate reader use "
            "to forcible felonies and missing or endangered people after state "
            "directives governing cameras in FDOT rights-of-way."
        ),
        "category_key": "st_lucie",
        "category_keys": ["st_lucie"],
        "county_keys": ["st_lucie"],
        "date": "2026-09-01",
        "first_published": "Tue, 01 Sep 2026 18:12:45 -0400",
        "is_custom": True,
        "authoritative_custom": True,
        "editorial_story_id": "custom:alpr-policy",
        "event_identity": {"event_families": ["missing-person"]},
    }


def _pslpd_policy(g, *, slug=None):
    return {
        "slug": slug or next(iter(g.ST_LUCIE_ALPR_POLICY_REDIRECT_SOURCE_SLUGS)),
        "headline": (
            "Port St. Lucie police pause license plate readers, limit use to "
            "life-threatening situations"
        ),
        "source_headline": (
            "Port St. Lucie police limiting use of license plate readers after state directive"
        ),
        "teaser": (
            "PSLPD paused automated license plate reader use after an FDOT directive."
        ),
        "body": (
            "The department will remove cameras in state rights-of-way and restrict "
            "remaining ALPR access during the pause to exigent threats to human life."
        ),
        "category_key": "st_lucie",
        "category_keys": ["st_lucie"],
        "county_keys": ["st_lucie"],
        "date": "2026-09-02",
        "source_published": "Wed, 02 Sep 2026 10:15:00 -0400",
        "source_url": "https://publisher.example/pslpd-alpr-policy",
        "is_custom": False,
        "authoritative_custom": False,
        # Deliberately contaminated legacy story identity. The durable custom
        # contract must not depend on this field being correct.
        "editorial_story_id": "story_002646",
    }


def test_same_window_st_lucie_alpr_policy_matches_authoritative_custom():
    g = _load_generate()
    matched, key = g._durable_custom_identity_match(_pslpd_policy(g), _custom(g))
    assert matched is True
    assert key == "local-alpr-policy|st-lucie|2026-09-01"


def test_alpr_policy_match_does_not_absorb_incident_story_that_only_mentions_flock():
    g = _load_generate()
    incident = {
        "headline": "Vero Beach homicide suspect arrested after Flock camera alert",
        "source_headline": "Flock camera helps deputies find homicide suspect in Vero Beach",
        "body": "Investigators said license plate reader evidence helped locate a vehicle.",
        "date": "2026-09-02",
        "category_key": "indian_river",
    }
    assert g._durable_custom_identity_match(incident, _custom(g))[0] is False


def test_cleanup_collapses_generated_lpr_policy_copy_to_custom_and_repairs_metadata(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    canonical = _custom(g)
    duplicate = _pslpd_policy(
        g,
        slug="2026-09-02-port-st-lucie-police-pause-license-plate-readers-limit-use-to-life-threatening-s",
    )
    cleaned, redirects = g.apply_canonical_story_cleanup(
        [canonical, duplicate], articles, tmp_path
    )

    by_slug = {row["slug"]: row for row in cleaned}
    assert set(by_slug) == {g.ST_LUCIE_ALPR_POLICY_CANONICAL_SLUG}
    assert by_slug[g.ST_LUCIE_ALPR_POLICY_CANONICAL_SLUG]["event_identity"]["event_families"] == []
    redirect_by_source = {row["source_slug"]: row for row in redirects}
    assert g.ST_LUCIE_ALPR_POLICY_REDIRECT_SOURCE_SLUGS <= set(redirect_by_source)
    for source_slug in g.ST_LUCIE_ALPR_POLICY_REDIRECT_SOURCE_SLUGS:
        assert redirect_by_source[source_slug]["target_slug"] == g.ST_LUCIE_ALPR_POLICY_CANONICAL_SLUG
        assert redirect_by_source[source_slug]["canonical_is_custom"] is True


def test_final_redirect_enforcement_overrides_stale_dui_target_and_creates_both_pages(tmp_path):
    g = _load_generate()
    articles = tmp_path / "articles"
    articles.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    sep1_generated = "2026-09-01-port-st-lucie-police-pause-flock-camera-use-after-state-revokes-permits"
    (data / "canonical-redirects.json").write_text(
        json.dumps({
            "redirects": [{
                "source_slug": sep1_generated,
                "target_slug": "2026-07-29-man-crashes-suv-into-port-st-lucie-liquor-store-charged-with-dui",
                "canonical_is_custom": False,
                "reason": "stale contaminated registry target",
            }]
        }),
        encoding="utf-8",
    )
    canonical = _custom(g)
    cleaned, current_redirects = g.apply_canonical_story_cleanup(
        [canonical], articles, tmp_path
    )
    cleaned, verification = g.enforce_canonical_redirects(
        cleaned, articles, tmp_path, current_redirects
    )

    manifest = json.loads((data / "canonical-redirects.json").read_text(encoding="utf-8"))
    by_source = {row["source_slug"]: row for row in manifest["redirects"]}
    assert by_source[sep1_generated]["target_slug"] == g.ST_LUCIE_ALPR_POLICY_CANONICAL_SLUG
    assert by_source[sep1_generated]["canonical_is_custom"] is True
    assert g.ST_LUCIE_ALPR_POLICY_REDIRECT_SOURCE_SLUGS <= set(by_source)
    assert all(
        by_source[slug]["target_slug"] == g.ST_LUCIE_ALPR_POLICY_CANONICAL_SLUG
        for slug in g.ST_LUCIE_ALPR_POLICY_REDIRECT_SOURCE_SLUGS
    )
    verified = {row["source_slug"]: row for row in verification}
    assert all(verified[slug]["passed"] for slug in g.ST_LUCIE_ALPR_POLICY_REDIRECT_SOURCE_SLUGS)
    assert all(
        g._redirect_target_path(g.ST_LUCIE_ALPR_POLICY_CANONICAL_SLUG)
        in (articles / f"{slug}.html").read_text(encoding="utf-8")
        for slug in g.ST_LUCIE_ALPR_POLICY_REDIRECT_SOURCE_SLUGS
    )


def test_story_regression_gate_requires_both_lpr_urls_to_target_custom(tmp_path):
    g = _load_generate()
    data = tmp_path / "data"
    data.mkdir()
    # Hoarding remains the always-on baseline contract in this report.
    hoarding_story = {
        "story_id": "story-hoarding",
        "canonical_is_custom": True,
        "canonical_slug": g.HOARDING_CANONICAL_SLUG,
        "articles": [{
            "headline": "Martin County deputies rescue 80 cats from Stuart hoarding home",
            "teaser": "The same animal-hoarding response.",
        }],
    }
    (data / "stories.json").write_text(json.dumps({"stories": [hoarding_story]}), encoding="utf-8")
    redirects = [{
        "source_slug": source,
        "target_slug": g.HOARDING_CANONICAL_SLUG,
        "canonical_is_custom": True,
        "reason": "Permanent hoarding migration",
    } for source in g.HOARDING_REDIRECT_SOURCE_SLUGS]
    redirects += [{
        "source_slug": source,
        "target_slug": g.ST_LUCIE_ALPR_POLICY_CANONICAL_SLUG,
        "canonical_is_custom": True,
        "reason": "Permanent ALPR policy migration",
    } for source in g.ST_LUCIE_ALPR_POLICY_REDIRECT_SOURCE_SLUGS]
    (data / "canonical-redirects.json").write_text(json.dumps({"redirects": redirects}), encoding="utf-8")
    verification = [{
        "source_slug": row["source_slug"],
        "target_slug": row["target_slug"],
        "passed": True,
    } for row in redirects]
    archive = [{
        "slug": g.HOARDING_CANONICAL_SLUG,
        "headline": "More than 70 animals found in Stuart home during large-scale hoarding response",
        "teaser": "Authorities removed cats and dogs during the hoarding response.",
        "is_custom": True,
        "authoritative_custom": True,
    }, _custom(g)]

    report = g.write_story_regression_report(tmp_path, archive, verification)
    assert report["production_gate_passed"] is True
    assert report["checks"]["st_lucie_alpr_custom_article_remains_canonical"] is True
    assert report["checks"]["st_lucie_alpr_duplicate_redirects_exist"] is True
    assert report["checks"]["st_lucie_alpr_duplicates_target_custom"] is True
    assert report["checks"]["st_lucie_alpr_duplicates_removed_from_archive"] is True
    assert report["checks"]["st_lucie_alpr_redirect_html_verified"] is True
