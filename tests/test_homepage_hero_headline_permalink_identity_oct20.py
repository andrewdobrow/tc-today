"""Prevent an October 19 Port St. Lucie hoarding lead linking to Hobe Sound kittens."""
from __future__ import annotations

import importlib
import json
import os
import sys
import types
from pathlib import Path

import pytest


def _g():
    if "feedparser" not in sys.modules:
        p = types.ModuleType("feedparser")
        p.parse = lambda *a, **k: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = p
    if "anthropic" not in sys.modules:
        a = types.ModuleType("anthropic")
        a.Anthropic = lambda *args, **kw: types.SimpleNamespace(messages=types.SimpleNamespace(create=lambda **kw: None))
        sys.modules["anthropic"] = a
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


HOBE = "2026-10-08-hobe-sound-woman-accused-of-burying-cats-alive-says-she-thought-they-were-demons"
PSL = "2026-10-19-more-than-100-cats-rescued-from-port-st-lucie-hoarding-house"
OLD_TITLE = "Rescued Hobe Sound Kittens Buried Alive Recovering in Foster Care"
NEW_TITLE = "Port St. Lucie Hoarding Case: 124 Cats Removed, Two Residents Cited"


def _fixture(root, include_new=True):
    (root / 'articles').mkdir()
    entries = [
        {
            "slug": HOBE, "headline": OLD_TITLE, "editorial_story_id": "story_hobe_kittens",
            "canonical_first_published_at": "2026-10-08T21:51:00-04:00",
            "permalink_origin_headline": "Hobe Sound Woman Accused of Burying Cats Alive Says She Thought They Were Demons",
            "category_keys": ["martin", "crime"],
        },
    ]
    if include_new:
        entries.append({
            "slug": PSL, "headline": NEW_TITLE, "editorial_story_id": "story_psl_hoarding",
            "canonical_first_published_at": "2026-10-19T18:52:00-04:00",
            "permalink_origin_headline": "More Than 100 Cats Rescued From Port St. Lucie Hoarding House",
            "meaningful_update_validated": True,
            "last_meaningful_update_at": "2026-10-20T18:52:00-04:00",
            "meaningful_update_basis": "semantic_material_update_gate",
            "category_keys": ["st_lucie", "crime"],
        })
    for row in entries:
        (root / 'articles' / (row['slug'] + '.html')).write_text("<html><h1>" + row['headline'] + "</h1></html>")
    (root / 'archive.json').write_text(json.dumps(entries))
    return entries


def _hero(slug=HOBE, title=NEW_TITLE):
    return {"hero": {
        "headline": title,
        "body": "More than 100 cats were recovered from a Port St. Lucie hoarding house.",
        "_archived_slug": slug,
        "link": "https://treasurecoast.today/articles/" + slug + ".html",
        "editorial_story_id": "story_hobe_kittens",
        "incident_anchor_key": "mass-animal-hoarding:martin-county",
    }}


def _html(slug, title):
    return ('<section class="hero hero-v3" data-cat-hero="all">'
            f'<a class="hero-v3-link" href="https://treasurecoast.today/articles/{slug}.html">'
            f'<h1 class="hero-v3-headline">{title}</h1></a></section>')


def test_distinct_county_hoarding_lead_rebinds_to_exact_2026_10_19_canonical(tmp_path):
    g = _g()
    _fixture(tmp_path)
    news = _hero()
    outcome = g.reconcile_homepage_hero_headline_permalink(news, tmp_path)
    assert outcome["action"] == "corrected"
    assert news["hero"]["_archived_slug"] == PSL
    assert news["hero"]["canonical_slug"] == PSL
    assert news["hero"]["link"].endswith(PSL + '.html')
    assert news["hero"]["editorial_story_id"] == "story_psl_hoarding"
    assert "mass-animal-hoarding:martin-county" not in news["hero"].values()
    assert news["hero"]["body"].startswith("More than 100")
    assert g.reconcile_homepage_hero_headline_permalink(news, tmp_path)["action"] == "verified"


def test_original_hobe_sound_lead_still_owns_its_url(tmp_path):
    g = _g()
    _fixture(tmp_path)
    old = _hero(title=OLD_TITLE)
    assert g.reconcile_homepage_hero_headline_permalink(old, tmp_path)["action"] == "verified"
    assert old["hero"]["link"].endswith(HOBE + '.html')


def test_never_guess_canonical_when_matching_article_missing(tmp_path):
    g = _g()
    _fixture(tmp_path, include_new=False)
    with pytest.raises(RuntimeError, match="headline/permalink identity FAILED"):
        g.reconcile_homepage_hero_headline_permalink(_hero(), tmp_path)


def test_rendered_hero_with_wrong_link_cannot_deploy(tmp_path):
    g = _g()
    _fixture(tmp_path)
    with pytest.raises(RuntimeError, match="after final render"):
        g.validate_rendered_homepage_hero_headline_permalink(_html(HOBE, NEW_TITLE), tmp_path)
    assert g.validate_rendered_homepage_hero_headline_permalink(_html(PSL, NEW_TITLE), tmp_path)["action"] == "verified"
    assert g.validate_rendered_homepage_hero_headline_permalink(_html(HOBE, OLD_TITLE), tmp_path)["action"] == "verified"


def test_similar_cat_topic_cannot_be_used_as_identity_proof(tmp_path):
    g = _g()
    entries = _fixture(tmp_path)
    # Same cat/hoarding vocabulary is not an exact publication identity.
    entries[1]['headline'] = 'Two Residents Cited in Port St. Lucie Cat Hoarding Investigation'
    (tmp_path / 'archive.json').write_text(json.dumps(entries))
    with pytest.raises(RuntimeError, match="no unique"):
        g.reconcile_homepage_hero_headline_permalink(_hero(), tmp_path)
