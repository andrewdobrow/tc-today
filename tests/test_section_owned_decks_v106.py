from pathlib import Path


def _render_source():
    source = Path("scripts/generate.py").read_text(encoding="utf-8")
    start = source.index("def render_index(")
    end = source.index("\ndef slugify", start)
    return source[start:end]


def test_category_views_render_dedicated_section_owned_cards():
    render = _render_source()
    assert "Section views use their own server-built card decks" in render
    assert 'data-section-owner="{_section_key}"' in render
    assert '_section_cards = [' in render
    assert '_section.get("cards")' in render
    assert '_section_view.get("cards")' in render
    assert '_rank_section_editorial_candidates(' in render
    assert 'card_section_timestamp(card)' in render


def test_section_decks_exclude_their_hero_and_dedupe_within_section():
    render = _render_source()
    assert '_section_hero_permalink = _raw_surface_permalink' in render
    assert '_section_seen_permalinks.add(_section_hero_key)' in render
    assert '_permalink_key in _section_seen_permalinks' in render


def test_client_never_reconstructs_county_from_cross_category_memberships():
    js = Path("main.js").read_text(encoding="utf-8")
    assert 'show = sectionOwner === cat;' in js
    assert 'show = !sectionOwner && card.dataset.topnews === "true";' in js
    assert 'memberships.includes(cat)' not in js
    assert 'card.dataset.cats || card.dataset.cat' not in js


def test_dolly_style_cross_section_leak_is_structurally_impossible():
    # A Things To Do card can still carry Martin in data-cats for metadata, but
    # section visibility is controlled only by its dedicated section owner.
    js = Path("main.js").read_text(encoding="utf-8")
    assert 'const sectionOwner = card.dataset.sectionOwner || "";' in js
    assert 'show = sectionOwner === cat;' in js
    render = _render_source()
    assert 'data-cat="{_section_key}"' in render
    assert 'data-section-owner="{_section_key}"' in render


def test_more_stories_excludes_dedicated_section_cards():
    render = _render_source()
    assert 'current_headlines.update(_section_rendered_headlines)' in render


def test_asset_version_bumped_for_new_filter_behavior():
    audience = Path("scripts/build_audience_features.py").read_text(encoding="utf-8")
    assert 'ASSET_VERSION = "1.13.9.108"' in audience
