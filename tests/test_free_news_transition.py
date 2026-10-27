"""Free-news migration must restore full text before changing the public site."""
import json
import re
from pathlib import Path

import pytest

from scripts.free_news_transition import (
    _rewrite_chrome,
    _rewrite_home_support,
    _rewrite_privacy,
    load_snapshot,
    restore_article,
    transition,
)

SLUG = "2026-10-27-example"
FULL = "<p>Entire original full story paragraph one.</p><p>Additional reporting paragraph two.</p>"
LOCKED = (
    '<html><head><script type="application/ld+json">'
    '{"@context":"https://schema.org","@type":"NewsArticle","isAccessibleForFree":false,'
    '"hasPart":{"@type":"WebPageElement","cssSelector":".tct-paywalled-content",'
    '"isAccessibleForFree":false}}</script></head><body>'
    '<div class="article-body tct-member-preview"><div class="tct-preview-copy">'
    '<p>Teaser</p></div></div><div class="tct-member-only">'
    '<section data-tct-paywall="true">Subscribe</section>'
    '<div id="tct-protected-content" class="article-body tct-protected-content"></div></div>'
    '<div class="article-share">Share</div></body></html>'
)


def test_migration_restores_full_story_and_public_schema():
    page = restore_article(LOCKED, SLUG, {SLUG: "<!--tct-full-article-v2-->" + FULL})
    assert FULL in page
    assert 'class="article-body">' in page
    assert "Subscribe</section>" not in page
    assert 'data-tct-paywall=' not in page
    assert '"isAccessibleForFree":true' in page
    assert '"hasPart"' not in page


def test_missing_protected_body_fails_closed():
    with pytest.raises(RuntimeError, match="Protected body missing"):
        restore_article(LOCKED, SLUG, {})


def test_malformed_paywall_fails_closed():
    with pytest.raises(RuntimeError, match="boundary"):
        restore_article('<html><div data-tct-paywall="true">broken</div></html>', SLUG,
                        {SLUG: "<!--tct-full-article-v2-->" + FULL})


def test_snapshot_requires_complete_valid_shape(tmp_path):
    file = tmp_path / "snapshot.json"
    with pytest.raises(RuntimeError):
        load_snapshot(file)
    file.write_text(json.dumps({"articles":[{"slug": SLUG, "protected_body":
                                              "<!--tct-full-article-v2-->" + FULL}]}))
    assert load_snapshot(file)[SLUG].endswith(FULL)


def test_existing_paid_readers_keep_ad_free_tracking_and_account_access():
    source = (
        '<html><head><script data-tct-member-prepaint>'
        'old two article meter prepaint</script>'
        '<link rel="stylesheet" href="/membership.css?v=1">'
        '</head><body>'
        '<header><div class="header-actions">'
        '<a href="/subscribe.html" class="support-btn membership-subscribe-btn">Subscribe</a>'
        '<a href="/subscribe.html?signin=1" class="membership-header-signin">Sign in</a>'
        '<a href="/subscribe.html" class="membership-header-welcome">Welcome, subscriber</a>'
        '</div></header><script src="/membership-config.js"></script>'
        '<script type="module" src="/membership.js?v=1"></script>'
        '</body></html>'
    )
    public = _rewrite_chrome(source, "article.html")
    assert 'href="/donate.html"' in public
    assert public.count('href="/subscribe.html?signin=1"') == 1
    assert 'class="membership-header-welcome"' in public
    assert "mv-no-ads" in public
    assert "tct_member_entitled_hint" in public
    assert "old two article meter prepaint" not in public
    assert '<script src="/membership-config.js"></script>' in public
    assert '<script type="module" src="/membership.js?v=1"></script>' in public
    assert _rewrite_chrome(public, "article.html") == public


def test_main_bar_advertise_after_events_and_out_of_desktop_dropdown():
    source = ('<html><head></head><body><header class="site-masthead">'
              '<div class="header-actions"><a href="/subscribe.html" class="support-btn '
              'membership-subscribe-btn"><span class="membership-subscribe-label">Subscribe</span></a>'
              '<a href="/subscribe.html?signin=1" class="membership-header-signin">Sign in</a></div>'
              '<nav class="category-nav category-nav--primary" aria-label="Primary navigation">'
              '<a href="/events.html" class="cat-btn">Events</a><details class="nav-sections">'
              '<div class="nav-sections-menu"><a href="/advertise.html" class="nav-section-link">'
              'Advertise</a></div></details></nav></header></body></html>')
    page = _rewrite_chrome(source, "index.html")
    nav = re.search(r'<nav class="category-nav.*?</nav>', page, re.S).group()
    assert nav.index('>Events</a>') < nav.index('>Advertise</a>')
    assert nav.count('href="/advertise.html"') == 1
    assert 'href="/donate.html"' in page
    assert ">Subscribe</span>" not in page
    assert _rewrite_chrome(page, "index.html") == page


def test_homepage_support_card_no_longer_sells_subscriptions():
    before = ('<a href="/subscribe.html" class="grid-card tct-membership-card" '
              'data-support-card="true"><div>Membership $1/month</div></a>')
    after = _rewrite_home_support(before)
    assert 'href="/donate.html"' in after
    assert "Local news. Free for everyone." in after
    assert "$1" not in after


def test_privacy_policy_mentions_payments_and_for_profit_status():
    p = _rewrite_privacy('<p>Last updated: October 15, 2026</p><h2>Information we collect</h2>')
    assert "Last updated: October 27, 2026" in p
    assert "Stripe" in p
    assert "for-profit" in p


def test_stripe_donation_payment_link_host_is_supported():
    from scripts.free_news_transition import PAYMENT_PATTERN
    assert PAYMENT_PATTERN.fullmatch("https://donate.stripe.com/4gM5kw9LWfRb7uV6P34ZG01")
    assert PAYMENT_PATTERN.fullmatch("https://buy.stripe.com/test_abc123")
    assert not PAYMENT_PATTERN.fullmatch("https://donate.stripe.com.evil.example/abc")


def test_public_transition_requires_actual_stripe_payment_link(tmp_path):
    with pytest.raises(RuntimeError, match="genuine Stripe-hosted"):
        transition(tmp_path, tmp_path / "snapshot.json", "https://example.com/fake")


def test_project_workflow_does_not_activate_donation_mode_implicitly():
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/update.yml").read_text()
    assert "vars.TCT_READER_REVENUE_MODE || 'subscription'" in workflow
    assert "TCT_DONATION_PAYMENT_LINK" in workflow
    assert "scripts/free_news_transition.py" in workflow
    assert "python scripts/sync_protected_articles.py --snapshot-file /tmp/tct-protected-current.json --required" in workflow
