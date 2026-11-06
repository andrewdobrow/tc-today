"""The TCT header promotes the live iPhone app without removing Kit signups."""
from pathlib import Path

from scripts.replace_header_app_store import (
    APP_URL,
    BADGE_URL,
    APP_BADGE,
    MOBILE_LINK,
    CSS_ASSET_VERSION,
    reconcile,
    replace_header_promo,
)

ROOT = Path(__file__).resolve().parents[1]
OLD = ('<a class="masthead-newsletter" '
       'href="https://treasure-coast-today.kit.com/cb848255f8" '
       'aria-label="Get the Treasure Coast Today Morning Brief">'
       '<span class="masthead-newsletter-kicker">Morning Brief</span>'
       '<span class="masthead-newsletter-copy">'
       'Start your day with local headlines</span></a>')


def test_replaces_only_masthead_and_preserves_newsletter_signup():
    sample = (
        '<header class="site-masthead"><div class="masthead-top-row">'
        + OLD +
        '</div><nav id="tct-mobile-nav"><section class="mobile-nav-group '
        'mobile-nav-group--more"><div class="mobile-nav-links">'
        '<a href="/events.html" class="mobile-nav-link active" '
        'aria-current="page">Events</a>'
        '</div></section></nav></header>'
        '<link rel="stylesheet" href="/style.css?v=1.13.9.114">'
        '<aside class="newsletter-inline-slot"><script data-uid="30e15672d3">'
        '</script></aside>'
    )
    output = replace_header_promo(sample)
    assert APP_BADGE in output
    assert MOBILE_LINK in output
    assert output.count(BADGE_URL) == 1
    assert '/style.css?v=' + CSS_ASSET_VERSION in output
    assert 'class="masthead-newsletter"' not in output
    assert 'data-uid="30e15672d3"' in output
    assert replace_header_promo(output) == output


def test_unrelated_morning_brief_references_and_sans_header_remain():
    html = '<p>Morning Brief</p><a href="https://treasure-coast-today.kit.com/cb848255f8">Subscribe to newsletter</a>'
    assert replace_header_promo(html) == html


def test_can_reconcile_old_html_and_skip_hidden_metadata(tmp_path):
    (tmp_path / "articles").mkdir()
    (tmp_path / ".github").mkdir()
    before = '<header class="site-masthead">' + OLD + '</header>'
    (tmp_path / "articles" / "story.html").write_text(before)
    (tmp_path / ".github" / "private.html").write_text(before)
    assert reconcile(tmp_path) == {"scanned": 1, "updated": 1}
    assert reconcile(tmp_path) == {"scanned": 1, "updated": 0}
    assert APP_URL in (tmp_path / "articles" / "story.html").read_text()
    assert (tmp_path / ".github" / "private.html").read_text() == before


def test_home_and_events_headers_use_official_badge_and_mobile_link():
    for path in ("index.html", "events.html"):
        html = (ROOT / path).read_text(encoding="utf-8")
        header = html.split('<header class="site-masthead">', 1)[1].split('</header>', 1)[0]
        assert header.count("masthead-app-store") == 1, path
        assert APP_URL in header, path
        assert BADGE_URL in header, path
        assert 'width="135" height="40"' in header, path
        assert 'class="masthead-newsletter"' not in header, path
        assert header.count('data-tct-app-store-link') == 1, path
        assert 'href="' + APP_URL + '" class="mobile-nav-link" data-tct-app-store-link' in header
        assert 'href="/style.css?v=' + CSS_ASSET_VERSION in html


def test_badge_is_not_diminished_and_mobile_masthead_remains_compact():
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    assert ".site-masthead .masthead-app-store img" in css
    assert "width: 135px;" in css
    assert "height: 40px;" in css
    assert ".site-masthead .masthead-app-store { display: none !important; }" in css


def test_normal_and_deploy_only_workflows_apply_to_every_html_page():
    workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
    step = "run: python scripts/replace_header_app_store.py"
    assert workflow.count(step) == 2
    assert workflow.index("python scripts/direct_donation_links.py") < workflow.index(step)
    assert workflow.index(step) < workflow.index("- name: Validate final SEO and audience contracts")
    assert workflow.rindex(step) < workflow.index("- name: Upload artifact")


def test_events_validation_checks_new_masthead_contract():
    source = (ROOT / "scripts/update_events.py").read_text(encoding="utf-8")
    assert 'a.masthead-app-store[href="' + APP_URL + '"]' in source
    assert 'img[src="' + BADGE_URL + '"]' in source
    assert "shared Morning Brief masthead callout" not in source
