import importlib.util
import os
import sys
import types
from datetime import datetime, timedelta, timezone
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
    spec = importlib.util.spec_from_file_location('scripts.generate_section_editorial_v108', path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _card(headline, published, urgency, **extra):
    return {
        'headline': headline,
        'published_raw': published.isoformat(),
        'published': published.isoformat(),
        'urgency_score': urgency,
        **extra,
    }


def test_section_rank_is_editorial_not_pure_chronology():
    g = _load_generate()
    now = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    newest_routine = _card('Routine item from this morning', now - timedelta(hours=2), 4)
    important_recent = _card('Major county decision from yesterday', now - timedelta(hours=26), 9)

    selected, report = g._rank_section_editorial_candidates(
        [newest_routine, important_recent], category_key='martin', now=now
    )

    assert selected[0]['headline'] == important_recent['headline']
    assert report['policy'] == 'freshness_gate_then_urgency_plus_recency_editorial_rank'


def test_month_old_story_cannot_rank_in_active_section_even_at_max_urgency():
    g = _load_generate()
    now = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    stale = _card('Month-old major story', now - timedelta(days=30), 10)
    fresh = _card('Fresh local development', now - timedelta(hours=5), 5)

    selected, report = g._rank_section_editorial_candidates(
        [stale, fresh], category_key='martin', now=now
    )

    assert [c['headline'] for c in selected] == [fresh['headline']]
    stale_row = next(row for row in report['excluded'] if row['headline'] == stale['headline'])
    assert stale_row['eligibility_reason'] == 'older_than_14_days'


def test_extended_high_urgency_story_can_survive_but_new_story_still_beats_it():
    g = _load_generate()
    now = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    older_urgent = _card('Ten-day-old major unresolved story', now - timedelta(days=10), 9)
    fresh_routine = _card('Fresh routine county story', now - timedelta(hours=2), 4)

    selected, report = g._rank_section_editorial_candidates(
        [older_urgent, fresh_routine], category_key='martin', now=now
    )

    assert selected[0]['headline'] == fresh_routine['headline']
    assert selected[1]['headline'] == older_urgent['headline']
    selected_rows = {row['headline']: row for row in report['selected']}
    assert selected_rows[older_urgent['headline']]['eligibility_reason'] == 'high_urgency_extended_window'


def test_validated_material_update_can_legitimately_refresh_old_canonical():
    g = _load_generate()
    now = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    old_updated = _card(
        'Older canonical with major new development',
        now - timedelta(days=20),
        8,
        slug='2026-09-19-old-canonical',
        meaningful_update_validated=True,
        last_meaningful_update_at=(now - timedelta(hours=1)).isoformat(),
    )
    archive = [{
        'slug': '2026-09-19-old-canonical',
        'first_published': (now - timedelta(days=20)).isoformat(),
        'meaningful_update_validated': True,
        'last_meaningful_update_at': (now - timedelta(hours=1)).isoformat(),
    }]

    selected, report = g._rank_section_editorial_candidates(
        [old_updated], archive, category_key='martin', now=now
    )

    assert selected == [old_updated]
    assert report['selected'][0]['age_hours'] == 1.0
    assert 'last_meaningful_update_at' in report['selected'][0]['timestamp_basis']


def test_section_render_builds_recent_archive_candidate_pool_and_ranks_hero_too():
    source = Path('scripts/generate.py').read_text(encoding='utf-8')
    start = source.index('def render_index(')
    end = source.index('\ndef slugify', start)
    render = source[start:end]

    assert 'Add recent canonical archive stories even when the current model/generation' in render
    assert 'for _entry in archive:' in render
    assert '_ranked_section, _ranking_report = _rank_section_editorial_candidates(' in render
    assert '_section_hero = _ranked_section[0]' in render
    assert '_section_cards = _ranked_section[1:]' in render
    assert 'section-editorial-ranking.json' in render


def test_browser_preserves_server_editorial_rank_instead_of_date_sorting():
    js = Path('main.js').read_text(encoding='utf-8')
    assert 'eligibility first, then urgency/importance + recency' in js
    assert 'visible.sort(' not in js
    assert 'Number(b.dataset.sectionTs || 0)' not in js
