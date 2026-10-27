"""Free-news migration must restore full text before changing the public site."""
import json
import re
from pathlib import Path

import pytest

from scripts.free_news_transition import (
    _rewrite_chrome,
    _rewrite_home_support,
    _rewrite_privacy,
    _rewrite_subscription_terms,
    _rewrite_about,
    _rewrite_ownership,
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


def test_legacy_ios_free_article_fallback_is_separately_gated():
    endpoint = (
        Path(__file__).resolve().parents[1]
        / "supabase/functions/protected-article/index.ts"
    ).read_text(encoding="utf-8")
    assert "TCT_PUBLIC_READING_ENABLED" in endpoint
    assert "status: 404" in endpoint
    assert endpoint.index("body.action === 'meter-capability'") < endpoint.index("TCT_PUBLIC_READING_ENABLED")
    assert "code: 'PUBLIC_ARTICLE'" in endpoint


def test_project_workflow_does_not_activate_donation_mode_implicitly():
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/update.yml").read_text()
    assert "vars.TCT_READER_REVENUE_MODE || 'subscription'" in workflow
    assert "TCT_DONATION_PAYMENT_LINK" in workflow
    assert "scripts/free_news_transition.py" in workflow
    assert "python scripts/sync_protected_articles.py --snapshot-file /tmp/tct-protected-current.json --required" in workflow


def test_free_news_privacy_preserves_mediavine_exactly_and_removes_old_access_claims():
    root = Path(__file__).resolve().parents[1]
    raw = (root / "privacy.html").read_text(encoding="utf-8")
    before_ad = raw.split('<h3>Mediavine Programmatic Advertising (Ver 1.1)</h3>', 1)[1].split(
        '<h2>Your choices, retention and requests</h2>', 1,
    )[0]
    actual = _rewrite_privacy(raw)
    after_ad = actual.split('<h3>Mediavine Programmatic Advertising (Ver 1.1)</h3>', 1)[1].split(
        '<h2>Your choices, retention and requests</h2>', 1,
    )[0]
    assert before_ad == after_ad, "Never rewrite Mediavine-required programmatic disclosure"
    assert "October 27, 2026" in actual
    assert "for-profit business" in actual
    assert "not tax-deductible" in actual
    assert "one-time" in actual
    assert "Kit" in actual and "Formspree" in actual
    assert "Stripe" in actual and "Supabase" in actual
    assert "ad-free" in actual
    assert "monthly article-meter record" in actual
    assert "If you purchase or use a Treasure Coast Today membership" not in actual
    assert _rewrite_privacy(actual) == actual


def test_historical_subscription_terms_do_not_sell_new_memberships():
    root = Path(__file__).resolve().parents[1]
    source = (root / "subscription-terms.html").read_text(encoding="utf-8")
    terms = _rewrite_subscription_terms(source)
    assert "New paid reading memberships" not in terms or "closing new paid reading memberships" in terms
    assert "All articles are available to everyone without payment" in terms
    assert "ad-free benefit through the end of their paid terms" in terms
    assert "future renewals will be stopped at the billing transition" in terms
    assert 'id="tct-existing-subscription-notice"' in terms
    assert "Historical membership plans and pricing" in terms
    assert "The advertised introductory offer is $1" not in terms
    assert _rewrite_subscription_terms(terms) == terms


def test_ownership_and_about_funding_disclosures_are_consistent():
    root = Path(__file__).resolve().parents[1]
    ownership = _rewrite_ownership((root / "ownership.html").read_text(encoding="utf-8"))
    about = _rewrite_about((root / "about.html").read_text(encoding="utf-8"))
    assert "optional reader contributions" in ownership
    assert "not charitable tax-deductible donations" in ownership
    assert "independent reporting" in ownership
    assert "All Treasure Coast Today news articles are free to read." in about
    assert 'href="/donate.html"' in about
    assert 'href="/advertise.html"' in about
    assert "independent coverage" in about
    assert _rewrite_ownership(ownership) == ownership
    assert _rewrite_about(about) == about


def test_free_news_transition_wires_all_public_policies_into_update():
    root = Path(__file__).resolve().parents[1]
    source = (root / "scripts/free_news_transition.py").read_text(encoding="utf-8")
    for expected in (
        'if path == root / "privacy.html":',
        'if path == root / "subscription-terms.html":',
        'if path == root / "ownership.html":',
        'if path == root / "about.html":',
        "text = _rewrite_ownership(text)",
        "text = _rewrite_about(text)",
    ):
        assert expected in source


def test_donate_buttons_include_heart_before_label_and_not_newsletter():
    from scripts.free_news_transition import create_donation_page
    root = Path(__file__).resolve().parents[1]
    source = (
        '<html><head></head><body><a href="/subscribe.html" '
        'class="support-btn membership-subscribe-btn">Subscribe</a>'
        '<a href="/subscribe.html">Membership</a>'
        '<a href="/subscribe.html" class="footer-subscribe-cta">'
        '<span>Subscribe today</span></a>'
        '<form action="https://treasure-coast-today.kit.com">'
        '<button type="submit">Subscribe to newsletter</button></form></body></html>'
    )
    page = _rewrite_chrome(source, "index.html")
    assert 'class="tct-donate-heart" aria-hidden="true">&#9829;</span> <span class="membership-subscribe-label">Donate' in page
    assert 'class="tct-donate-heart" aria-hidden="true">&#9829;</span> Donate</a>' in page
    assert 'class="tct-donate-heart" aria-hidden="true">&#9829;</span> Donate to local news' in page
    assert 'Subscribe to newsletter' in page
    assert _rewrite_chrome(page, "index.html") == page
    home = _rewrite_home_support(
        '<a data-support-card="true" href="/subscribe.html">Old support tile</a>'
    )
    assert 'class="tct-donate-heart" aria-hidden="true">&#9829;</span> Donate to support the newsroom' in home
    generator = (root / "scripts/free_news_transition.py").read_text(encoding="utf-8")
    assert '<span class="tct-donate-heart" aria-hidden="true">&#9829;</span> Donate securely with Stripe' in generator


def test_open_access_launch_checks_real_supabase_checkout_before_generation():
    source = (Path(__file__).resolve().parents[1] / ".github/workflows/update.yml").read_text(encoding="utf-8")
    assert "Verify legacy membership checkout is blocked before free-news launch" in source
    assert "TCT_DISABLE_NEW_SUBSCRIPTIONS=true" in source
    assert 'if status != 410 or "new paid reading memberships are closed" not in body.lower():' in source
    assert "method=\"GET\"" in source, "Verification must never create a new real checkout session"
    assert source.index("Verify legacy membership checkout is blocked before free-news launch") < source.index("- name: Generate news")




def test_donate_hearts_inherit_label_color_and_align_inline():
    css = (Path(__file__).resolve().parents[1] / "donation-model.css").read_text(encoding="utf-8")
    assert ".tct-donate-heart{color:inherit;" in css
    assert ".tct-donate-button .tct-donate-heart{color:#fff}" not in css
    assert ".tct-donate-header{min-width:98px;flex-direction:row!important;" in css
    assert "background:#f26445;color:white!important" in css
    # Heart is decorative; the text Donate remains the accessible action name.
    source = _rewrite_chrome(
        '<a class="support-btn membership-subscribe-btn" href="/subscribe.html">Subscribe</a>',
        "index.html",
    )
    assert 'aria-hidden="true">&#9829;</span> <span class="membership-subscribe-label">Donate</span>' in source


def test_production_direct_invocation_imports_without_pythonpath():
    """Reproduce the exact mode that failed in run 40580075128.

    Importing through pytest or with python -m succeeds even when running
    python scripts/free_news_transition.py would throw ModuleNotFoundError.
    """
    import os
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "scripts/free_news_transition.py", "--help"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "--snapshot" in result.stdout
    assert "--payment-link" in result.stdout


def test_real_site_migration_dry_run_restores_custom_article_without_publish(tmp_path):
    """Validate both a legacy protected fixture and the now-open live archive.

    The protected fixture is synthetic; no real article is overwritten with
    test body text, and no Stripe, Supabase, or production data is modified.
    """
    import shutil

    root = Path(__file__).resolve().parents[1]
    page_names = (
        "index.html", "about.html", "privacy.html",
        "subscription-terms.html", "ownership.html", "advertise.html",
    )
    for name in page_names:
        shutil.copyfile(root / name, tmp_path / name)
    src = root / "articles" / (
        "2026-10-26-st-lucie-detective-tyler-horstman-felony-dui-arrest.html"
    )
    assert src.is_file(), "Canonical custom article fixture is missing"
    article_dir = tmp_path / "articles"
    article_dir.mkdir()
    dest = article_dir / src.name
    shutil.copyfile(src, dest)
    canonical_before = dest.read_text(encoding="utf-8")
    if "data-tct-paywall" not in canonical_before:
        # Do not fabricate a protected body for an article that has genuinely
        # already become public. The migration must leave its full text intact.
        assert '<div class="article-body">' in canonical_before
        assert '"isAccessibleForFree":true' in canonical_before

    # Independently exercise the fail-closed legacy rehydration path. Real
    # snapshots no longer need to contain public articles after cutover.
    legacy = article_dir / "synthetic-legacy-protected-article.html"
    legacy.write_text(LOCKED, encoding="utf-8")
    snapshot_path = tmp_path / "protected-private-test.json"
    snapshot_path.write_text(json.dumps({"articles": [
        {"slug": legacy.stem,
         "protected_body": "<!--tct-full-article-v2-->" + FULL},
        *([{"slug": src.stem, "protected_body": "<!--tct-full-article-v2-->" + FULL}]
          if "data-tct-paywall" in canonical_before else []),
    ]}), encoding="utf-8")
    report = transition(
        tmp_path,
        snapshot_path,
        "https://donate.stripe.com/4gM5kw9LWfRb7uV6P34ZG01",
    )
    assert report["rehydrated"] == (2 if "data-tct-paywall" in canonical_before else 1)
    published = legacy.read_text(encoding="utf-8")
    assert "Entire original full story paragraph one." in published
    assert "Additional reporting paragraph two." in published
    assert "data-tct-paywall" not in published
    assert "tct-member-preview" not in published
    assert "tct-member-only" not in published
    assert '"isAccessibleForFree":true' in published
    actual_custom = dest.read_text(encoding="utf-8")
    assert "data-tct-paywall" not in actual_custom
    assert 'href="/donate.html"' in actual_custom
    assert 'href="/advertise.html"' in actual_custom
    assert "tct_member_entitled_hint" in actual_custom, "Honor paid-through ad-free users"
    assert (tmp_path / "donate.html").is_file()
    donation = (tmp_path / "donate.html").read_text(encoding="utf-8")
    assert "https://donate.stripe.com/4gM5kw9LWfRb7uV6P34ZG01" in donation
    assert 'class="tct-donate-heart"' in donation
    privacy = (tmp_path / "privacy.html").read_text(encoding="utf-8")
    assert "Mediavine Programmatic Advertising (Ver 1.1)" in privacy
    assert "voluntary reader contributions" in privacy
    terms = (tmp_path / "subscription-terms.html").read_text(encoding="utf-8")
    assert "Historical membership plans and pricing" in terms
