"""Sponsored feature / Morning Brief advertising-page publication contract."""
from pathlib import Path
from bs4 import BeautifulSoup
import ast

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'advertise.html'
GENERATOR = ROOT / 'scripts' / 'generate.py'
PACKARD_PATH = '/articles/2026-10-04-three-generations-later-packard-roofing-remains-rooted-on-the-treasure-coast.html'


def _generated_preview():
    """Execute only page renderer from generator to avoid starting the newsroom pipeline."""
    source = GENERATOR.read_text(encoding='utf-8')
    tree = ast.parse(source)
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'render_advertise_page')
    module = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    env = {
        '_page_head': lambda *args: '<title>Advertising preview</title>',
        '_page_header': lambda **kwargs: '<header></header>',
        '_page_footer': lambda: '<footer></footer>',
    }
    exec(compile(module, str(GENERATOR), 'exec'), env)
    return env['render_advertise_page']()


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
    assert 'Sponsored content is labeled' in page
    assert 'Sponsorship does not influence editorial coverage' in page
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


def test_static_advertise_page_and_generator_agree_on_sponsorship_contract():
    for page in (PAGE.read_text(encoding='utf-8'), _generated_preview()):
        _assert_contract(page)


def test_regenerating_advertising_does_not_revert_to_display_ads():
    generated = _generated_preview()
    actual = PAGE.read_text(encoding='utf-8')
    for literal in ('Your business has a story.', 'Ways to work together', 'Morning Brief sponsorships', 'What are you interested in?', 'formspree.io/f/mqejrpdv'):
        assert literal in generated and literal in actual


def test_sponsored_example_target_is_real_local_page():
    assert (ROOT / PACKARD_PATH.lstrip('/')).is_file()
