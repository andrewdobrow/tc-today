"""Regression cases from the October 10, 2026 public events calendar."""
import json
from pathlib import Path
from scripts import update_events as events

SNAPSHOT = Path('/mnt/data/events (4).json')


def _event(title, time, venue, source='venue', description='', priority=7):
    return {
        'title': title, 'starts_at': f'2026-10-10T{time}:00-04:00',
        'ends_at': None, 'venue': venue, 'city': 'Stuart', 'county': 'Martin',
        'source_name': source, 'source_priority': priority, 'description': description,
        'time_known': True, 'all_day': False, 'source_url': 'https://example.org',
    }


def test_museum_time_error_reconciled_to_explicit_eight_am_clock():
    bad = _event('CARS AND COFFEE', '04:00', 'Elliott Museum', description='Every second Saturday from 8 AM to 10 AM')
    good = _event('CARS AND COFFEE', '08:00', 'Elliott Museum')
    result = events._dedupe_cross_source([bad, good])
    assert len(result) == 1
    assert result[0]['starts_at'].startswith('2026-10-10T08:00')


def test_museum_stroll_year_prefix_and_curly_apostrophe_merge():
    official = _event('2026 Trick or Treat Stroll', '16:00', "Children's Museum of the Treasure Coast")
    tourism = _event('Trick or Treat Stroll', '16:00', 'Children’s Museum of the Treasure Coast', source='Discover Martin', priority=35, description='Admission $3 per person')
    result = events._dedupe_cross_source([official, tourism])
    assert len(result) == 1
    assert result[0]['description'] == 'Admission $3 per person'


def test_stuart_festival_html_venue_and_fall_variant_merge():
    city = _event('27th Annual Downtown Stuart Art & Craft Festival', '10:00', '<p>Downtown Stuart</p> - Stuart FL 34994', source='City of Stuart', priority=20)
    tourism = _event('27th Annual Downtown Stuart Fall Craft Festival', '10:00', 'Downtown Stuart', source='Discover Martin', priority=35)
    result = events._dedupe_cross_source([city, tourism])
    assert len(result) == 1
    assert result[0]['venue'] == 'Downtown Stuart'
    assert '<p>' not in events._render_card({**result[0], 'id': 'x', 'category': 'Arts & Culture', 'price': '', 'event_url': 'https://example.org'})


def test_same_show_different_performance_and_similar_events_remain_distinct():
    matinee = _event('Proof', '14:00', 'Pineapple Playhouse')
    evening = _event('Proof', '19:00', 'Pineapple Playhouse')
    other = _event('Proven', '14:00', 'Pineapple Playhouse')
    assert len(events._dedupe_cross_source([matinee, evening, other])) == 3


def test_clock_is_not_corrected_without_unambiguous_four_hour_disagreement():
    x = _event('CARS AND COFFEE', '08:00', 'Elliott Museum', description='Every Saturday 8 AM to 10 AM')
    y = events._dedupe_cross_source([x])
    assert y[0]['starts_at'].startswith('2026-10-10T08:00')
