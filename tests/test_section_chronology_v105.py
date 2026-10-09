import importlib.util
import json
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path


def _load_generate():
    if 'feedparser' not in sys.modules:
        feedparser = types.ModuleType('feedparser')
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules['feedparser'] = feedparser
    if 'anthropic' not in sys.modules:
        anthropic = types.ModuleType('anthropic')
        anthropic.Anthropic = lambda *args, **kwargs: types.SimpleNamespace(
            messages=types.SimpleNamespace(create=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('offline')))
        )
        sys.modules['anthropic'] = anthropic
    os.environ.setdefault('ANTHROPIC_API_KEY', 'offline-test-key')
    path = Path('scripts/generate.py')
    spec = importlib.util.spec_from_file_location('scripts.generate_section_chronology_v105', path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_section_publication_chronology_ignores_lastmod_refresh():
    g = _load_generate()
    old_revised = {
        'slug': '2026-08-01-old-business-story',
        'date': '2026-08-01',
        'first_published': '2026-08-01T14:00:00Z',
        'lastmod': '2026-10-09',
        'meaningful_update_validated': True,
        'last_meaningful_update_at': '2026-10-09T10:00:00Z',
    }
    newer = {
        'slug': '2026-10-08-new-business-story',
        'date': '2026-10-08',
        'first_published': '2026-10-08T13:00:00Z',
        'lastmod': '2026-10-08',
    }

    assert g._section_publication_datetime(old_revised) < g._section_publication_datetime(newer)
    rows = sorted([old_revised, newer], key=g._section_publication_sort_key, reverse=True)
    assert rows[0]['slug'] == newer['slug']
    assert g._section_publication_value(old_revised) == '2026-08-01T14:00:00Z'


def test_permanent_archive_recovery_uses_publication_chronology(tmp_path, monkeypatch):
    g = _load_generate()
    g.OUTPUT_DIR = tmp_path
    (tmp_path / 'articles').mkdir(parents=True, exist_ok=True)

    old_revised = {
        'slug': '2026-08-01-old-business-story',
        'headline': 'Old business story revised today',
        'teaser': 'A Treasure Coast company announced a local development with jobs and investment.',
        'body': 'A Treasure Coast company announced a local development with jobs and investment.',
        'category_key': 'business',
        'category_label': 'Business & Development',
        'category_keys': ['business'],
        'date': '2026-08-01',
        'first_published': '2026-08-01T14:00:00Z',
        'lastmod': '2026-10-09',
        'ranking_eligible': True,
    }
    newer = {
        'slug': '2026-10-08-new-business-story',
        'headline': 'New Treasure Coast business expansion announced',
        'teaser': 'A Treasure Coast employer announced a new expansion, investment and local jobs.',
        'body': 'A Treasure Coast employer announced a new expansion, investment and local jobs.',
        'category_key': 'business',
        'category_label': 'Business & Development',
        'category_keys': ['business'],
        'date': '2026-10-08',
        'first_published': '2026-10-08T13:00:00Z',
        'lastmod': '2026-10-08',
        'ranking_eligible': True,
    }
    (tmp_path / 'archive.json').write_text(json.dumps([old_revised, newer]), encoding='utf-8')

    monkeypatch.setattr(g, '_sanitize_authoritative_custom_archive', lambda rows, articles_dir: rows)
    monkeypatch.setattr(g, '_filter_source_retirement_archive_view', lambda rows, output_root: rows)
    monkeypatch.setattr(g, '_backfill_archive_editorial_story_ids', lambda rows, idx, output_root=None: (rows, {}))
    monkeypatch.setattr(g, '_load_publication_identity_index', lambda: {})
    monkeypatch.setattr(g, 'enforce_live_county_membership_authority', lambda categories: {'rejections': []})
    monkeypatch.setattr(g, '_archive_entry_publishable', lambda row: True)
    monkeypatch.setattr(g, '_archive_entry_has_contextless_update_lead', lambda row: False)
    monkeypatch.setattr(g, '_archive_entry_has_article_framing_failure', lambda row: False)
    monkeypatch.setattr(g, '_category_eligibility_contract_assessment', lambda key, row: {'mode': 'off', 'eligible': True})
    monkeypatch.setattr(g, '_category_contract_config', lambda key: {'mode': 'off'})
    monkeypatch.setattr(g, '_archive_article_body', lambda row: row.get('body', ''))
    monkeypatch.setattr(g, '_archive_article_metrics', lambda row: (200, 4))
    monkeypatch.setattr(g, 'get_fallback_image', lambda *args, **kwargs: ('', ''))

    categories = []
    g.ensure_all_category_sections(categories, min_cards=1)
    business = next(row for row in categories if row['category_key'] == 'business')

    assert business['hero']['_archived_slug'] == newer['slug']
    assert business['hero']['published_raw'] == newer['first_published']


def test_render_and_client_contract_make_category_tabs_newest_first():
    source = Path('scripts/generate.py').read_text(encoding='utf-8')
    render = source[source.index('def render_index('):source.index('\ndef slugify', source.index('def render_index('))]
    assert '_bf_archive.sort(key=_section_publication_sort_key, reverse=True)' in render
    assert 'older_archive.sort(key=_section_publication_sort_key, reverse=True)' in render
    assert 'data-section-ts="{card_section_timestamp(card)}"' in render

    js = Path('main.js').read_text(encoding='utf-8')
    assert 'if (cat !== "all" && visible.length)' in js
    assert 'Number(b.dataset.sectionTs || 0)' in js
    assert 'card.style.order = String(index < 4 ? index : index + 1)' in js
    assert 'allStoryCards.forEach(card => { card.style.order = ""; });' in js


def test_archive_recovery_paths_do_not_sort_by_lastmod_anymore():
    source = Path('scripts/generate.py').read_text(encoding='utf-8')
    ensure = source[source.index('def ensure_all_category_sections('):source.index('\ndef _normalized_external_source_url', source.index('def ensure_all_category_sections('))]
    assert 'archive.sort(key=_section_publication_sort_key, reverse=True)' in ensure
    assert '"published": _section_publication_value(e)' in ensure

    # The final category-quality archive hero fallback must use the same chronology.
    guard_slice = source[source.index('Before dropping a page, try to build its hero from the recent archive') - 1000:source.index('Before dropping a page, try to build its hero from the recent archive') + 5000]
    assert '_arch.sort(key=_section_publication_sort_key, reverse=True)' in guard_slice
    assert '_dt = _section_publication_datetime(e)' in guard_slice
