from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]


def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")
        anthropic.Anthropic = lambda *args, **kwargs: types.SimpleNamespace(
            messages=types.SimpleNamespace(create=lambda **kwargs: None)
        )
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    import importlib
    return importlib.import_module("scripts.generate")


def test_launch_header_uses_coral_pricing_context_and_quiet_signin(monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "MEMBERSHIP_UI_ENABLED", True)
    header = g._header_primary_cta_html()
    css = (ROOT / "style.css").read_text()
    assert "membership-subscribe-btn" in header
    assert "Limited time &middot; $1 first month" in header
    assert "then $4.99" not in header
    assert "membership-header-signin" in header
    assert "signin=1" in header
    assert 'data-membership-welcome' in header
    assert "Welcome, subscriber" in header
    assert "#f26445" in css
    assert ".membership-subscribe-price { display: none; }" in css
    assert ".membership-header-signin { display: none !important; }" in css


def test_sitewide_chrome_normalizer_preserves_dark_mode_and_launches_retained_pages(tmp_path, monkeypatch):
    g = _load_generate()
    sample = tmp_path / "retained.html"
    sample.write_text('<header><div class="header-actions"><a href="/advertise.html" class="support-btn">Advertise</a></div></header>')

    monkeypatch.setattr(g, "MEMBERSHIP_UI_ENABLED", False)
    g._apply_membership_site_chrome(tmp_path)
    assert "Advertise" in sample.read_text()
    assert "membership-subscribe-btn" not in sample.read_text()

    monkeypatch.setattr(g, "MEMBERSHIP_UI_ENABLED", True)
    g._apply_membership_site_chrome(tmp_path)
    launched = sample.read_text()
    assert "membership-subscribe-btn" in launched
    assert "Limited time &middot; $1 first month" in launched
    assert "Sign in" in launched
    assert 'data-membership-welcome' in launched


def test_subscribe_page_is_real_landing_page_not_account_gate():
    page = (ROOT / "subscribe.html").read_text()
    assert "Know what’s happening across the Treasure Coast." in page
    assert 'id="membership-plans"' in page
    assert "Don’t miss stories like these." in page
    assert "data-membership-top-stories" in page
    assert "archive.json" in page
    assert "front.hero" in page
    assert "front.cards" in page
    assert "membership-story-card" in page
    assert "membership-landing-value-grid" in page
    assert "membership-faq-grid" in page
    assert "membership-hero-plans" in page
    assert "membership-hero-plan-monthly" in page
    assert "membership-hero-plan-annual" in page
    assert page.index("membership-hero-plans") < page.index("membership-landing-value")
    assert page.count('data-plan="annual"') >= 2
    assert page.count('data-plan="monthly"') >= 2
    assert "Create account" not in page
    assert 'type="password"' not in page
    assert "Limited time &middot; $1 first month" in page
    assert "Monthly: $1 today, then $4.99/month starting one month later. Annual: $49/year. Subscriptions renew automatically until canceled." in page


def test_browser_config_requires_explicit_live_payment_mode_before_public_launch(monkeypatch, tmp_path):
    path = ROOT / "scripts/write_membership_browser_config.py"
    spec = importlib.util.spec_from_file_location("membership_config_launch", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "OUT", tmp_path / "membership-config.js")
    monkeypatch.setattr(module, "SUBSCRIBE", tmp_path / "subscribe.html")
    (tmp_path / "subscribe.html").write_text('<meta id="membership-robots" name="robots" content="noindex,nofollow,noarchive">')
    monkeypatch.setenv("TCT_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("TCT_SUPABASE_PUBLISHABLE_KEY", "sb_publishable_example")
    monkeypatch.setenv("TCT_MEMBERSHIP_UI_ENABLED", "true")
    monkeypatch.setenv("TCT_STRIPE_MODE", "test")
    try:
        module.main()
    except RuntimeError as exc:
        assert "TCT_STRIPE_MODE=live" in str(exc)
    else:
        raise AssertionError("public membership launch accepted test-mode Stripe")

    monkeypatch.setenv("TCT_STRIPE_MODE", "live")
    module.main()
    payload_text = (tmp_path / "membership-config.js").read_text()
    assert '"paymentMode":"live"' in payload_text
    assert '"sandbox":false' in payload_text
    assert 'content="index,follow"' in (tmp_path / "subscribe.html").read_text()


def test_stripe_entitlements_are_mode_isolated():
    migration = (ROOT / "supabase/migrations/202608090003_membership_live_mode.sql").read_text()
    shared = (ROOT / "supabase/functions/_shared/membership.ts").read_text()
    status = (ROOT / "supabase/functions/membership-status/index.ts").read_text()
    protected = (ROOT / "supabase/functions/protected-article/index.ts").read_text()
    checkout = (ROOT / "supabase/functions/create-checkout/index.ts").read_text()
    webhook = (ROOT / "supabase/functions/stripe-webhook/index.ts").read_text()
    assert "stripe_livemode boolean not null default false" in migration
    assert "stripe_livemode: Boolean(subscription.livemode)" in shared
    assert ".eq('stripe_livemode', STRIPE_LIVEMODE)" in status
    assert ".eq('stripe_livemode', STRIPE_LIVEMODE)" in protected
    assert "stripeSecretMatchesMode" in checkout
    assert "stripeObjectMatchesMode(event)" in webhook


def test_sandbox_engineering_page_cannot_start_live_checkout():
    script = (ROOT / "membership-test.js").read_text()
    assert "sandboxMode" in script
    assert "Live Stripe checkout is intentionally disabled" in script
    assert "Stripe is in LIVE mode" in script


def test_paid_content_schema_targets_protected_content_placeholder():
    from tct_engine.membership_paywall import add_paywall_schema, paywall_html
    page = '<script type="application/ld+json">{"@type":"NewsArticle","isAccessibleForFree":true}</script>'
    transformed = add_paywall_schema(page)
    assert '"cssSelector":".tct-paywalled-content"' in transformed
    markup = paywall_html("example-story")
    assert "tct-paywalled-content" in markup
    assert "Then $4.99/month. Cancel anytime." in markup
    assert "Annual membership" in markup
    assert '<strong>$49</strong><span>per year</span>' in markup
    assert "Continue annually" in markup
    assert "Subscriptions renew automatically until canceled." in markup


def test_workflow_passes_payment_mode_to_browser_launch_guard():
    workflow = (ROOT / ".github/workflows/update.yml").read_text()
    assert "TCT_STRIPE_MODE: ${{ vars.TCT_STRIPE_MODE || 'test' }}" in workflow


def test_membership_launch_removes_article_support_banner_from_renderer(monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "MEMBERSHIP_UI_ENABLED", True)
    assert g._article_banner_html_for_context("ordinary local news") == ""


def test_membership_launch_removes_retained_support_banner(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "MEMBERSHIP_UI_ENABLED", True)
    articles = tmp_path / "articles"
    articles.mkdir()
    page = articles / "example.html"
    page.write_text('''<!doctype html><html><body><main class="article-wrap">
      <a href="https://buy.stripe.com/legacy" class="article-banner-slot article-ad-banner" aria-label="Support Treasure Coast Today">
        <img src="https://treasurecoast.today/images/support-banner.png" alt="Support Treasure Coast Today">
      </a>
      <div class="article-meta">Meta</div><div class="article-editorial-grid"></div><aside class="article-side-rail"></aside>
    </main></body></html>''')
    result = g._remove_membership_launch_article_support_banners(tmp_path)
    rendered = page.read_text()
    assert result["removed"] == 1
    assert "support-banner.png" not in rendered
    assert "article-banner-slot" not in rendered
    assert "article-meta" in rendered


def test_dark_launch_keeps_reader_support_banner(monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "MEMBERSHIP_UI_ENABLED", False)
    monkeypatch.setattr(g, "ARTICLE_BANNER_MODE", "reader_support")
    banner = g._article_banner_html_for_context("ordinary local news")
    assert "support-banner.png" in banner
    assert "Support Treasure Coast Today" in banner


def test_workflow_passes_membership_launch_state_to_support_banner_preflight():
    workflow = (ROOT / ".github/workflows/update.yml").read_text()
    marker = "- name: Normalize recent reader-support banners"
    section = workflow.split(marker, 1)[1].split("- name:", 1)[0]
    assert "TCT_MEMBERSHIP_UI_ENABLED: ${{ vars.TCT_MEMBERSHIP_UI_ENABLED || 'false' }}" in section


def test_membership_sitemap_is_python311_safe_and_launch_aware(monkeypatch):
    source = (ROOT / "scripts/generate.py").read_text()
    # Python 3.11 cannot parse same-quote nested f-strings (PEP 701 landed in 3.12).
    assert 'else f"""' not in source

    g = _load_generate()
    monkeypatch.setattr(g, "MEMBERSHIP_UI_ENABLED", False)
    assert "/subscribe.html" not in g.update_sitemap([])

    monkeypatch.setattr(g, "MEMBERSHIP_UI_ENABLED", True)
    sitemap = g.update_sitemap([])
    assert f"{g.SITE_URL}/subscribe.html" in sitemap
    assert "<changefreq>monthly</changefreq>" in sitemap


def test_sitewide_subscriber_chrome_loads_membership_state_and_prepaints(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "MEMBERSHIP_UI_ENABLED", True)
    page = tmp_path / "index.html"
    page.write_text('<!doctype html><html><head></head><body><header><div class="header-actions"><a href="/advertise.html" class="support-btn">Advertise</a></div></header></body></html>')
    g._apply_membership_site_chrome(tmp_path)
    rendered = page.read_text()
    assert "data-tct-member-prepaint" in rendered
    assert "tct_member_entitled_hint" in rendered
    assert 'src="/membership-config.js"' in rendered
    assert 'src="/membership.js?v=1.13.7.9"' in rendered
    assert rendered.count('/membership.js?v=1.13.7.9') == 1


def test_entitled_subscriber_chrome_replaces_sales_header_and_hides_membership_card():
    script = (ROOT / "membership.js").read_text()
    css = (ROOT / "style.css").read_text()
    assert "function applySubscriberChrome(status)" in script
    assert "`Welcome, ${firstName}`" in script
    assert "status?.first_name" in script
    assert "body.tct-member-entitled .membership-subscribe-btn" in css
    assert "body.tct-member-entitled .membership-header-signin" in css
    assert "body.tct-member-entitled .membership-header-welcome" in css
    assert "body.tct-member-entitled .tct-membership-card" in css
    assert "html.tct-member-preverified .tct-membership-card" in css


def test_membership_status_persists_and_returns_first_name_without_weakening_entitlement():
    migration = (ROOT / "supabase/migrations/202608160001_membership_subscriber_chrome.sql").read_text()
    status = (ROOT / "supabase/functions/membership-status/index.ts").read_text()
    checkout = (ROOT / "supabase/functions/create-checkout/index.ts").read_text()
    complete = (ROOT / "supabase/functions/checkout-complete/index.ts").read_text()
    webhook = (ROOT / "supabase/functions/stripe-webhook/index.ts").read_text()
    assert "add column if not exists first_name text" in migration
    assert "name_collection: { individual: { enabled: true, optional: false } }" in checkout
    assert "first_name: firstName" in status
    assert "Name personalization must never block an otherwise valid entitlement" in status
    assert ".update({ first_name: firstName" in complete
    assert "profileUpdate.first_name = firstName" in webhook


def test_sitewide_chrome_normalizer_migrates_retained_free_trial_footer(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "MEMBERSHIP_UI_ENABLED", True)
    page = tmp_path / "retained-article.html"
    page.write_text(
        '<!doctype html><html><head></head><body>'
        '<header><div class="header-actions"><a href="/advertise.html" class="support-btn">Advertise</a></div></header>'
        '<footer><a class="footer-subscribe-cta" href="/subscribe.html"><span>Start free trial</span>'
        '<small>Limited time &middot; 7 days free &middot; then $4.99/mo</small></a></footer>'
        '</body></html>'
    )
    g._apply_membership_site_chrome(tmp_path)
    rendered = page.read_text()
    assert "Start free trial" not in rendered
    assert "7 days free" not in rendered
    assert "Get first month for $1" in rendered
    assert "Limited time &middot; $1 first month" in rendered
    assert "then $4.99/mo" not in rendered
