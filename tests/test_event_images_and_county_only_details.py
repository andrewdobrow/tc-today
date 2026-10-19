"""Regression: event imagery and county-only official event landing pages."""
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

from scripts import update_events
from scripts import build_audience_features as audience


TARGET_TITLE = 'Treasures on the Tide Walk'


def event_sample():
    return {
        'id': '0b837c294d9c017a5d', 'title': TARGET_TITLE,
        'starts_at': '2026-10-19T09:00-04:00', 'ends_at': '2026-10-19T11:00-04:00',
        'all_day': False, 'time_known': True, 'county': 'St. Lucie',
        'category': 'Outdoors & Nature', 'venue': '', 'city': '', 'address': '',
        'description': "Join this guided beach ecology walk at Ocean Bay Preserve to discover the treasures brought in by the tides and explore the beach habitat.",
        'event_url': 'https://visitstlucie.com/event/treasures-on-the-tide-walk/',
        'source_url': 'https://visitstlucie.com/events/list/',
        'source_name': 'Visit St. Lucie',
        'image_url': 'https://visitstlucie.com/wp-content/uploads/2026/01/sun.jpg',
        'price': '', 'ticket_url': '',
    }


def test_official_county_only_event_gets_internal_detail_page():
    assert audience._event_detail_eligible(event_sample())


def test_unverified_county_only_events_remain_excluded():
    a = event_sample()
    a['description'] = 'Walk'
    assert not audience._event_detail_eligible(a)
    a = event_sample()
    a['county'] = ''
    assert not audience._event_detail_eligible(a)
    a = event_sample()
    a['event_url'] = a['source_url']
    assert not audience._event_detail_eligible(a)
    a = event_sample()
    a['starts_at'] = ''
    assert not audience._event_detail_eligible(a)


def test_initial_event_cards_show_real_images_only():
    card = update_events._render_card(event_sample())
    soup = BeautifulSoup(card, 'html.parser')
    image = soup.select_one('.event-card-media img')
    assert image['src'] == event_sample()['image_url']
    assert 'loading' in image.attrs
    a = event_sample()
    a['image_url'] = ''
    assert 'event-card-media' not in update_events._render_card(a)
    a['image_url'] = 'javascript:alert(1)'
    assert 'event-card-media' not in update_events._render_card(a)


def test_dynamic_renderer_displays_image_and_is_idempotent():
    original = update_events.EVENTS_HTML_PATH.read_text(encoding='utf-8')
    page = update_events._ensure_event_image_ui(original)
    assert 'const imageUrl = event.image_url ? safeUrl(event.image_url)' in page
    assert '${imageMarkup}' in page
    assert '.event-card-media img' in page
    assert update_events._ensure_event_image_ui(page) == page


def test_event_page_generated_and_calendar_relinked(tmp_path, monkeypatch):
    example = event_sample()
    (tmp_path / 'data').mkdir()
    (tmp_path / 'data' / 'events.json').write_text(json.dumps({'events':[example], 'event_count':1}), encoding='utf-8')
    (tmp_path / 'data' / 'events-retention.json').write_text('{}', encoding='utf-8')
    source_root = Path(__file__).resolve().parents[1]
    (tmp_path / 'about.html').write_text((source_root / 'about.html').read_text(encoding='utf-8'), encoding='utf-8')
    (tmp_path / 'events.html').write_text((source_root / 'events.html').read_text(encoding='utf-8'), encoding='utf-8')
    monkeypatch.setenv('TCT_EVENTS_NOW', '2026-10-18T12:00:00-04:00')
    monkeypatch.setattr(update_events, 'EVENTS_HTML_PATH', tmp_path / 'events.html')
    update_events._render_page([example], {'generated_at':'2026-10-18T12:00:00-04:00'})
    monkeypatch.setattr(audience, 'ROOT', tmp_path)
    report = audience.render_event_detail_pages()
    assert report['rendered'] == 1
    payload = json.loads((tmp_path / 'data' / 'events.json').read_text())
    detail_url = payload['events'][0]['detail_url']
    assert detail_url.startswith('/events/')
    detail_page = (tmp_path / detail_url.lstrip('/')).read_text()
    assert TARGET_TITLE in detail_page
    assert 'event-detail-photo' in detail_page
    assert example['image_url'] in detail_page
    assert 'Ocean Bay Preserve' in detail_page
    assert 'St. Lucie County' in detail_page
    assert 'https://visitstlucie.com/event/treasures-on-the-tide-walk/' in detail_page
    calendar = (tmp_path / 'events.html').read_text()
    soup = BeautifulSoup(calendar, 'html.parser')
    card = soup.select_one('[data-event-id="0b837c294d9c017a5d"]')
    assert card is not None
    assert card.select_one('.event-title a')['href'] == detail_url
    assert card.select_one('.event-card-media img')['src'] == example['image_url']
    assert card.select_one('.event-actions a')['href'] == detail_url
    assert 'const imageMarkup = imageUrl ===' in calendar
    assert f'https://treasurecoast.today{detail_url}' in calendar
