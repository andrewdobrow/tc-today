"""Searchable archive must use the same validated editorial activity as Latest News."""

from datetime import datetime
from email.utils import parsedate_to_datetime

from scripts import build_audience_features as features


def _archive_env(tmp_path, monkeypatch):
    # Use the existing real archive chrome contract without requiring a site build.
    (tmp_path / 'about.html').write_text(
        '<header class="site-masthead"><a href="/">TCT</a></header>'
        '<footer><a href="/archive.html">Archive</a></footer>',
        encoding='utf-8',
    )
    monkeypatch.setattr(features, 'ROOT', tmp_path)


def _story(slug, headline, published, *, updated='', validated=False, lastmod=''):
    date_value = published[:10] if published[:4].isdigit() else parsedate_to_datetime(published).date().isoformat()
    return {
        'slug': slug,
        'headline': headline,
        'teaser': 'Verified local news article.',
        'category_key': 'martin',
        'category_label': 'Martin County',
        'county_keys': ['martin'],
        'date': date_value,
        'first_published': published,
        'lastmod': lastmod or date_value,
        'meaningful_update_validated': validated,
        'last_meaningful_update_at': updated,
    }


def _render(rows, tmp_path, monkeypatch):
    _archive_env(tmp_path, monkeypatch)
    features.render_searchable_archive(rows)
    return (tmp_path / 'archive.html').read_text(encoding='utf-8')


def test_substantive_update_returns_old_story_to_top_with_updated_headline(tmp_path, monkeypatch):
    old = _story(
        '2026-09-29-canonical-story',
        'Updated factual headline for September reporting',
        'Tue, 29 Sep 2026 10:00:00 -0400',
        updated='2026-10-16T19:45:00Z',
        validated=True,
    )
    new = _story('2026-10-16-newer-published-story', 'Newly published story', '2026-10-16T18:00:00Z')
    html = _render([old, new], tmp_path, monkeypatch)
    assert html.index('Updated factual headline') < html.index('Newly published story')
    assert 'data-date="2026-10-16" data-published="2026-09-29"' in html
    assert 'Updated 2026-10-16' in html
    assert 'title="Originally published 2026-09-29"' in html
    assert 'href="/articles/2026-09-29-canonical-story.html"' in html
    assert 'September 2026</h2>' not in html


def test_only_validated_updates_move_stories_not_lastmod_or_unverified_timestamps(tmp_path, monkeypatch):
    recent = _story('recent', 'October new article', '2026-10-15T16:00:00Z')
    older_maintenance = _story(
        'older-maintenance', 'Routine maintenance article', '2026-09-05T16:00:00Z',
        lastmod='2026-10-17', updated='2026-10-17T11:00:00Z', validated=False,
    )
    older_stamp = _story('older-stamp', 'Article with pre-publication update', '2026-09-06T16:00:00Z',
                         updated='2026-09-05T10:00:00Z', validated=True)
    html = _render([older_maintenance, recent, older_stamp], tmp_path, monkeypatch)
    assert html.index('October new article') < html.index('Article with pre-publication update')
    assert html.index('Article with pre-publication update') < html.index('Routine maintenance article')
    assert 'Updated 2026-10-17' not in html
    assert 'data-date="2026-09-05" data-published="2026-09-05"' in html


def test_update_near_utc_midnight_uses_florida_calendar_date(tmp_path, monkeypatch):
    old = _story('past-story', 'Late Florida evening update', '2026-08-20',
                 updated='2026-10-17T03:15:00Z', validated=True)
    html = _render([old], tmp_path, monkeypatch)
    assert 'data-date="2026-10-16"' in html
    assert 'Updated 2026-10-16' in html


def test_rfc822_update_receipt_supported_and_does_not_change_original_date(tmp_path, monkeypatch):
    old = _story('past-story', 'RFC822 updated headline', 'Thu, 15 Oct 2026 08:00:00 -0400',
                 updated='Fri, 16 Oct 2026 13:20:00 -0400', validated=True)
    html = _render([old], tmp_path, monkeypatch)
    assert 'data-date="2026-10-16" data-published="2026-10-15"' in html
    assert 'Updated 2026-10-16' in html
