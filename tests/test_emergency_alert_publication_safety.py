"""End-to-end regression coverage for repeated unverified emergency alert headlines.

Uses actual editorial source code rather than testing only a fixed list of slugs.
"""
import json
import os
import sys
import types
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def gen():
    if 'feedparser' not in sys.modules:
        m=types.ModuleType('feedparser'); m.parse=lambda *a,**k: types.SimpleNamespace(entries=[])
        sys.modules['feedparser']=m
    if 'anthropic' not in sys.modules:
        m=types.ModuleType('anthropic')
        class Stub:
            def __init__(self,*a,**k):
                self.messages=types.SimpleNamespace(create=lambda **kw: None)
        m.Anthropic=Stub; sys.modules['anthropic']=m
    os.environ.setdefault('ANTHROPIC_API_KEY','offline-test-key')
    from scripts import generate
    return generate

@pytest.fixture
def site(tmp_path):
    p=tmp_path/'data/source-retirement-editor-overrides.json'
    p.parent.mkdir(parents=True)
    p.write_bytes((ROOT/'data/source-retirement-editor-overrides.json').read_bytes())
    return tmp_path

THIRD='2026-10-12-flash-flood-warning-hits-coastal-martin-county-until-7-pm'

def test_third_known_permanently_retired_and_earlier_two_preserved(gen,site):
    policies=gen._source_retirement_policy_by_slug(site)
    for slug in [THIRD,'2026-10-11-flash-flood-warning-hits-stuart-hobe-sound-palm-city-and-coastal-martin-county', '2026-10-12-flash-flood-warning-hits-stuart-hobe-sound-palm-city-and-coastal-martin-county']:
        assert gen._source_retirement_policy_for_slug(slug, policies)['action']=='retire'
    entry={'slug':THIRD,'headline':'Flash Flood Warning Hits Coastal Martin County Until 7 PM','date':'2026-10-12','source_url':'https://example.com/weather'}
    kept, redirects, report=gen.apply_source_retirement_cleanup_to_archive([entry],site/'articles',output_root=site)
    assert kept==[] and redirects==[] and report['retired_count']==1
    page=(site/'articles'/f'{THIRD}.html').read_text()
    assert 'noindex,nofollow' in page and 'This article has been retired' in page

@pytest.mark.parametrize('headline',[
    'Flash Flood Warning Hits Coastal Martin County Until 7 PM',
    'Flash Flood Warning Hits Stuart, Hobe Sound, Palm City and Coastal Martin County',
    'Flash Flood Warning Extended for Martin County',
    'Martin County Under Flash Flood Warning Until 7 PM',
    'NWS Issues Flash Flood Warning for Hobe Sound',
    'Breaking: Tornado Warning Issued for St. Lucie County',
    'Severe Thunderstorm Warning for Indian River County',
])
def test_new_reworded_warning_with_fresh_slug_still_held(gen, headline):
    row={'slug':'2026-10-17-new-different-title-'+gen.slugify(headline),'date':'2026-10-17','headline':headline}
    assert gen._unverified_automated_live_alert_policy(row)['action']=='retire'

@pytest.mark.parametrize('headline',[
    'Why St. Lucie Residents Received Tornado Warnings Late',
    'Flash Flood Warning Expired Sunday, Cleanup Continues Monday',
    'After Heavy Flooding, Martin County Crews Assess Damage',
    'Residents Question Tornado Warning Delays',
    'NWS Confirms Tornado Struck Port St. Lucie',
])
def test_post_event_reporting_is_not_suppressed(gen, headline):
    assert gen._unverified_automated_live_alert_policy({'date':'2026-10-17','headline':headline}) is None

def test_manually_written_alert_not_automatically_suppressed(gen):
    assert gen._unverified_automated_live_alert_policy({
        'headline':'Flash Flood Warning Hits Martin County',
        'date':'2026-10-17','is_custom':True}) is None

def test_historical_archive_entries_preserved(gen):
    assert gen._unverified_automated_live_alert_policy({
        'headline':'Flash Flood Warning Hits Coastal Martin County',
        'date':'2026-07-17'}) is None


def test_new_alert_filtered_in_all_surfaces(gen,site):
    unseen_slug='2026-10-17-new-flash-flood-warning-extended-for-martin-county'
    row={'slug':unseen_slug,'date':'2026-10-17','headline':'Flash Flood Warning Extended for Martin County'}
    good={'slug':'2026-10-17-flood-cleanup-continues','headline':'Flood cleanup continues'}
    assert gen._filter_source_retirement_archive_view([row,good],site)==[good]
    kept,_,report=gen.apply_source_retirement_cleanup_to_archive([row,good],site/'articles',site)
    assert kept==[good] and report['retired_count']==1
    cats=[{'category_key':'martin','hero':dict(row),'cards':[dict(row),good]}]
    top={'hero':dict(row),'cards':[dict(row),good]}
    assert gen.apply_source_retirements_to_live(cats,top,site)==4
    assert cats[0]['hero']==good and cats[0]['cards']==[]
    assert top['hero']==good and top['cards']==[]


def test_undated_new_live_generated_headline_held(gen):
    assert gen._unverified_automated_live_alert_policy({
        'headline':'Flash Flood Warning Hits Stuart Until 7 PM'})


def test_source_has_prewrite_hold_and_final_post_rebind_sweep():
    text=(ROOT/'scripts/generate.py').read_text()
    assert 'EMERGENCY ALERT SAFETY HOLD' in text
    assert 'held_before_article_page_write' in text
    assert 'apply_source_retirements_to_live(all_categories, top_cat, output_root=OUTPUT_DIR)' in text
    assert text.index('held_before_article_page_write') < text.index('(_generated_custom_publication_slug(') if '(_generated_custom_publication_slug(' in text else True

def test_final_safety_invariant_refuses_any_leaked_live_or_archive_warning(gen):
    warning={'headline':'Flash Flood Warning Hits Coastal Martin County Until 7 PM','date':'2026-10-12'}
    good={'headline':'After the Storm, Streets Reopen','date':'2026-10-12'}
    assert gen.validate_no_unverified_active_alerts(archive=[good],all_categories=[{'hero':good,'cards':[]}])
    with pytest.raises(RuntimeError,match='EMERGENCY ALERT PUBLICATION BLOCKED'):
        gen.validate_no_unverified_active_alerts(archive=[warning])
    with pytest.raises(RuntimeError,match='EMERGENCY ALERT PUBLICATION BLOCKED'):
        gen.validate_no_unverified_active_alerts(all_categories=[{'category_key':'martin','hero':warning,'cards':[]}])
    with pytest.raises(RuntimeError,match='EMERGENCY ALERT PUBLICATION BLOCKED'):
        gen.validate_no_unverified_active_alerts(top_cat={'category_key':'top_news','hero':good,'cards':[warning]})


def test_retirement_safeguard_still_works_without_any_exact_tombstones(gen,tmp_path):
    warning={'headline':'Flash Flood Warning Hits Stuart Until 7 PM','date':'2026-10-14','slug':'2026-10-14-new-headline'}
    assert gen._filter_source_retirement_archive_view([warning],tmp_path)==[]
    cat=[{'category_key':'martin','hero':warning,'cards':[]}]
    assert gen.apply_source_retirements_to_live(cat,output_root=tmp_path)==1
    assert cat[0]['hero'] is None
