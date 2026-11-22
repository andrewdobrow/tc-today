"""Article byline and schema may not claim an update occurred before publication."""
import ast
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import re
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / 'scripts' / 'generate.py'


def _render_date_block():
    source = SOURCE.read_text(encoding='utf-8')
    tree = ast.parse(source)
    namespace = {'datetime': datetime, 'timezone': timezone, 'ZoneInfo': ZoneInfo,
                 're': re, '_slug_date': lambda slug: None}
    for name in ('_parse_any_datetime', '_latest_news_publication_datetime',
                 '_latest_news_validated_update_datetime',
                 '_format_article_timestamp_eastern'):
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), namespace)
    start = source.index('    def _fmt_full(raw):', source.index('def render_article_page('))
    end = source.index('    description = ', start)
    code = 'def render_dates(hero, pub_date):\n' + source[start:end] + '''    return {
        "published": _pub_display,
        "published_raw": _pub_raw,
        "updated": _updated_display,
        "updated_raw": _updated_raw,
        "updated_html": _updated_html,
        "dateModified": _updated_raw or _pub_raw or pub_date,
    }
'''
    exec(compile(code, str(SOURCE), 'exec'), namespace)
    return namespace['render_dates']


def _hero(published, update=None, validated=True, **overrides):
    return {
        'slug': '2026-10-20-st-lucie-fire-crews-battle-two-structure-fires-in-fort-pierce-port-st-lucie',
        'first_published': published,
        'meaningful_update_validated': validated,
        'last_meaningful_update_at': update or '',
        **overrides,
    }


def test_november_est_uses_utc_minus_five_not_summer_dst():
    result = _render_date_block()(_hero('Sun, 22 Nov 2026 11:47:51 -0500'), '2026-11-22')
    assert result['published'] == 'November 22, 2026 at 11:47 AM ET'
    assert result['published_raw'] == 'Sun, 22 Nov 2026 11:47:51 -0500'


def test_summer_edt_uses_utc_minus_four():
    result = _render_date_block()(_hero('2026-07-22T15:47:51+00:00'), '2026-07-22')
    assert result['published'] == 'July 22, 2026 at 11:47 AM ET'


def test_dst_fall_back_transition_has_correct_wall_clock():
    first = _render_date_block()(_hero('2026-11-01T05:30:00+00:00'), '2026-11-01')
    second = _render_date_block()(_hero('2026-11-01T06:30:00+00:00'), '2026-11-01')
    assert first['published'] == second['published'] == 'November 1, 2026 at 1:30 AM ET'


def test_date_only_fallback_does_not_invent_previous_day_time():
    result = _render_date_block()(_hero('', date='2026-11-22'), '2026-11-22')
    assert result['published'] == 'November 22, 2026'


def test_oct20_article_cannot_be_updated_on_oct19():
    result = _render_date_block()(_hero('2026-10-20T15:45:00-04:00', '2026-10-19T22:01:00Z'), '2026-10-20')
    assert result['published'] == 'October 20, 2026 at 3:45 PM ET'
    assert result['updated'] == ''
    assert result['updated_html'] == ''
    assert result['dateModified'] == result['published_raw']


def test_same_day_update_before_original_publication_is_not_shown():
    result = _render_date_block()(_hero('Tue, 20 Oct 2026 16:30:00 -0400', '2026-10-20T16:00:00-04:00'), '2026-10-20')
    assert result['updated_raw'] == ''
    assert result['dateModified'] == result['published_raw']


def test_valid_later_material_update_is_visible():
    result = _render_date_block()(_hero('2026-10-20T15:45:00-04:00', '2026-10-20T23:21:00Z'), '2026-10-20')
    assert result['updated'] == 'October 20, 2026 at 7:21 PM ET'
    assert 'Updated October 20, 2026 at 7:21 PM ET' in result['updated_html']
    assert result['dateModified'] == '2026-10-20T23:21:00+00:00'


def test_generic_updated_at_cannot_create_false_update():
    result = _render_date_block()(_hero('2026-10-20T15:45:00-04:00',
                                         update=None, validated=True,
                                         updated_at='2026-10-20T23:21:00Z'), '2026-10-20')
    assert result['updated_html'] == ''


def test_unvalidated_update_never_displays_even_when_later():
    result = _render_date_block()(_hero('2026-10-20T15:45:00-04:00', '2026-10-21T09:00:00Z', validated=False), '2026-10-20')
    assert result['updated_html'] == ''


def test_last_material_and_canonical_receipt_choose_latest_valid_time():
    result = _render_date_block()(_hero('2026-10-20T15:45:00-04:00',
                                         '2026-10-19T10:00:00Z',
                                         canonical_last_material_update_at='2026-10-21T15:00:00Z'), '2026-10-20')
    assert result['updated'] == 'October 21, 2026 at 11:00 AM ET'


def test_article_structured_data_uses_same_validated_date_field():
    source = SOURCE.read_text(encoding='utf-8')
    body = source[source.index('def render_article_page('):source.index('def render_archive_page(')]
    assert '"dateModified":  _updated_raw or _pub_raw or pub_date' in body
    assert '"datePublished": _pub_raw or pub_date' in body


def _retained_repair():
    import re
    source = SOURCE.read_text(encoding='utf-8')
    tree = ast.parse(source)
    namespace = {'datetime': datetime, 'timezone': timezone, 'Path': Path,
                 'json': json, 're': re, 'ZoneInfo': ZoneInfo}
    for name in ('_parse_any_datetime', '_recent_direct_article_paths',
                 '_format_article_timestamp_eastern',
                 '_repair_prepublication_article_timestamps'):
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), namespace)
    return namespace['_repair_prepublication_article_timestamps']


def _make_article(root, stem, published_label, updated_label, pub_raw, mod_raw):
    article_dir = root / 'articles'
    article_dir.mkdir(exist_ok=True)
    path = article_dir / (stem + '.html')
    payload = {'@context': 'https://schema.org', '@type':'NewsArticle',
               'headline':'St. Lucie Fire Crews Battle Two Structure Fires',
               'datePublished':pub_raw, 'dateModified':mod_raw}
    html = (f'<html><script type="application/ld+json">{json.dumps(payload)}</script>'
            f'<div class="article-times"><span class="article-published">Published {published_label}</span>'
            f'<span class="article-updated">Updated {updated_label}</span></div>'
            '<h1>St. Lucie Fire Crews Battle Two Structure Fires</h1>'
            '<div class="article-body">Unchanged article content</div></html>')
    path.write_text(html)
    (root / 'archive.json').write_text(json.dumps([{'slug':stem}]))
    return path


def test_retained_november_published_byline_uses_metadata_receipt(tmp_path):
    path = _make_article(
        tmp_path, '2026-11-22-fort-pierce-test',
        'November 22, 2026 at 12:47 PM ET',
        'November 22, 2026 at 12:47 PM ET',
        '2026-11-22T11:47:51-05:00', '2026-11-22T11:47:51-05:00'
    )
    original = path.read_text()
    html = original.replace(
        '<html>',
        '<html><head><meta property="article:published_time" content="Sun, 22 Nov 2026 11:47:51 -0500">'
        '<meta property="article:modified_time" content="Sun, 22 Nov 2026 11:47:51 -0500"></head>'
    )
    path.write_text(html)
    assert _retained_repair()(tmp_path) == {'checked':1, 'repaired':1}
    repaired = path.read_text()
    assert '<span class="article-published">Published November 22, 2026 at 11:47 AM ET</span>' in repaired
    assert 'class="article-updated"' not in repaired
    assert 'Unchanged article content' in repaired
    assert '2026-11-22T11:47:51-05:00' in repaired
    assert _retained_repair()(tmp_path)['repaired'] == 0


def test_retained_winter_valid_update_both_labels_corrected(tmp_path):
    path = _make_article(
        tmp_path, '2026-11-22-st-lucie-test',
        'November 22, 2026 at 12:47 PM ET', 'November 22, 2026 at 1:15 PM ET',
        '2026-11-22T11:47:51-05:00', '2026-11-22T12:15:00-05:00'
    )
    assert _retained_repair()(tmp_path)['repaired'] == 1
    html = path.read_text()
    assert 'Published November 22, 2026 at 11:47 AM ET' in html
    assert 'Updated November 22, 2026 at 12:15 PM ET' in html


def test_source_no_fixed_summer_offset_for_eastern_clock():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'utc - timedelta(hours=4)' not in source
    assert 'hour=9, tzinfo=timezone(timedelta(hours=-4))' not in source
    assert 'et = _tz(timedelta(hours=-4))' not in source
    assert 'ZoneInfo("America/New_York")' in source


def test_retained_articles_fix_byline_and_jsonld_without_touching_content(tmp_path):
    path = _make_article(
        tmp_path, '2026-10-20-st-lucie-fire-crews',
        'October 20, 2026 at 3:45 PM ET', 'October 19, 2026 at 6:01 PM ET',
        '2026-10-20T15:45:00-04:00', '2026-10-19T18:01:00-04:00')
    result = _retained_repair()(tmp_path)
    html = path.read_text()
    assert result == {'checked':1, 'repaired':1}
    assert 'class="article-updated"' not in html
    assert 'Unchanged article content' in html
    match = __import__('re').search(r'<script type="application/ld\+json">(.*?)</script>', html)
    payload = json.loads(match.group(1))
    assert payload['dateModified'] == payload['datePublished']
    assert _retained_repair()(tmp_path)['repaired'] == 0


def test_retained_valid_update_is_not_rewritten(tmp_path):
    path = _make_article(
        tmp_path, '2026-10-20-st-lucie-fire-crews',
        'October 20, 2026 at 3:45 PM ET', 'October 20, 2026 at 5:01 PM ET',
        '2026-10-20T15:45:00-04:00', '2026-10-20T17:01:00-04:00')
    before = path.read_bytes()
    assert _retained_repair()(tmp_path) == {'checked':1, 'repaired':0}
    assert path.read_bytes() == before


def test_retained_update_before_publish_on_same_day_is_removed(tmp_path):
    path = _make_article(
        tmp_path, '2026-10-20-st-lucie-fire-crews',
        'October 20, 2026 at 3:45 PM ET', 'October 20, 2026 at 2:15 PM ET',
        'Tue, 20 Oct 2026 15:45:00 -0400', '2026-10-20T18:15:00Z')
    assert _retained_repair()(tmp_path)['repaired'] == 1
    assert 'class="article-updated"' not in path.read_text()


def test_retained_repair_ignores_redirect_stub(tmp_path):
    path = _make_article(
        tmp_path, '2026-10-20-st-lucie-fire-crews',
        'October 20, 2026 at 3:45 PM ET', 'October 19, 2026 at 2:15 PM ET',
        '2026-10-20T15:45:00-04:00', '2026-10-19T18:15:00Z')
    path.write_text(path.read_text().replace('</html>', '<meta http-equiv="refresh" content="0; url=/">\n</html>'))
    before = path.read_bytes()
    assert _retained_repair()(tmp_path)['checked'] == 0
    assert path.read_bytes() == before


def test_update_pipeline_repairs_retained_pages_before_other_sitewide_transforms():
    source = SOURCE.read_text(encoding='utf-8')
    pipeline = source[source.index('def main('):]
    assert pipeline.index('_repair_article_shells(OUTPUT_DIR)') < pipeline.index('_repair_prepublication_article_timestamps(OUTPUT_DIR)') < pipeline.index('_validate_presentation_contract(OUTPUT_DIR)')
