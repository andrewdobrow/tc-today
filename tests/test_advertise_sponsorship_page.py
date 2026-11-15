"""Advertising-page publication contract for all current partnership types."""
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'advertise.html'
PACKARD_PATH = '/articles/2026-10-04-three-generations-later-packard-roofing-remains-rooted-on-the-treasure-coast.html'


def _assert_contract(page):
    doc = BeautifulSoup(page, 'html.parser')
    assert 'Sponsored business features' in page
    assert 'Morning Brief sponsorships' in page
    # Audience metrics change frequently: the public sponsor page must stay evergreen.
    assert not doc.select('.adv-stats, .adv-stat, .adv-audience-note')
    for stale_claim in ('~30,000', '~550', 'Monthly local users', 'Morning Brief subscribers',
                        'Approximate audience figures', 'as of October 2026'):
        assert stale_claim not in page
    assert 'Martin, St. Lucie and Indian River counties' in page
    assert 'No paywall. Every reader sees your ad' not in page
    assert '706K+' not in page
    assert 'Top 5</span><span class="adv-stat-label">' not in page
    assert PACKARD_PATH in page
    assert 'Sponsored content is labeled' not in page
    assert 'clearly labeled' not in page
    assert 'clearly identified' not in page
    assert 'Sponsorship does not influence editorial coverage' not in page
    assert "We'll work with you to choose the right opportunities" in page
    for heading in ('Website advertising', 'Podcast sponsorships'):
        assert heading in page
    for option in ('Website advertising', 'Podcast sponsorship', 'Multiple placements'):
        assert any(x.get_text(strip=True) == option for x in doc.select('select#interest option'))
    assert doc.select_one('a[href="/podcast/"]') is not None
    assert 'advertise-banner.png' not in page
    assert doc.select_one('form#advForm')['action'] == 'https://formspree.io/f/mqejrpdv'
    assert doc.select_one('form#advForm')['method'].upper() == 'POST'
    for f in ('name', 'business', 'email', 'industry', 'interest'):
        assert doc.select_one('form#advForm [name="'+f+'"]') is not None
    assert doc.select_one('#interest')['required'] is not None
    assert doc.select_one('form#advForm [name="budget"]') is None
    assert doc.select_one('#submitBtn') is not None
    assert doc.select_one('#successMsg') is not None
    assert 'new FormData(form)' in page
    assert "if(res.ok)" in page
    assert 'grid-template-columns: 1fr;' in page


def test_static_advertise_page_and_retained_template_agree_on_sponsorship_contract():
    page = PAGE.read_text(encoding='utf-8')
    template = (ROOT / 'content' / 'advertise-page.html').read_text(encoding='utf-8')
    # The newsroom's navigation normalizer may adjust the active menu state.
    # Preserve the advertising copy and inquiry form, not byte-for-byte chrome.
    for html in (page, template):
        _assert_contract(html)
    current = BeautifulSoup(page, 'html.parser')
    retained = BeautifulSoup(template, 'html.parser')
    for selector in ('.adv-offers', '.adv-offers-note', '.adv-disclosure', '#advForm'):
        current_section = current.select_one(selector)
        retained_section = retained.select_one(selector)
        assert current_section is not None and retained_section is not None
        assert str(current_section) == str(retained_section), selector


def test_full_update_restores_advertise_page_after_generator():
    workflow = (ROOT / '.github' / 'workflows' / 'update.yml').read_text(encoding='utf-8')
    assert 'cp content/advertise-page.html advertise.html' in workflow
    assert workflow.index('python -u scripts/run_generator_fail_fast.py') < workflow.index('cp content/advertise-page.html advertise.html') < workflow.index('python -u scripts/build_audience_features.py')


def test_retained_advertise_page_includes_current_offerings():
    actual = PAGE.read_text(encoding='utf-8')
    for literal in ('Your business has a story.', 'Ways to work together', 'Morning Brief sponsorships', 'Website advertising', 'Podcast sponsorships', 'What are you interested in?', 'formspree.io/f/mqejrpdv'):
        assert literal in actual


def test_sponsored_example_target_is_real_local_page():
    assert (ROOT / PACKARD_PATH.lstrip('/')).is_file()
