import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SLUG='2026-08-06-martin-county-sheriffs-office-seeks-public-help-finding-missing-14-year-old-auti'

def test_ethan_boyd_resolution_override_is_durable():
    payload=json.loads((ROOT/'data/article-content-overrides.json').read_text())
    row=payload['overrides'][SLUG]
    assert row['headline']=='Missing 14-year-old autistic boy Ethan Boyd safely located, Martin County sheriff says'
    assert row['image_url']=='https://treasurecoast.today/images/ethan-boyd.png'
    assert row['update_status']=='resolved'
    assert 'safely located' in row['update_text']

def test_canonical_page_keeps_permalink_image_and_resolution_update():
    text=(ROOT/'articles'/f'{SLUG}.html').read_text()
    assert 'Missing 14-year-old autistic boy Ethan Boyd safely located' in text
    assert 'UPDATE — Aug. 5, 2026, 11:44 p.m.:' in text
    assert 'https://treasurecoast.today/images/ethan-boyd.png' in text
    assert f'<link rel="canonical" href="https://treasurecoast.today/articles/{SLUG}.html">' in text
