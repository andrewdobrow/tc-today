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
    assert "Limited time &middot; 7 days free &middot; then $4.99/mo" in header
    assert "membership-header-signin" in header
    assert "signin=1" in header
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
    assert "Limited time &middot; 7 days free &middot; then $4.99/mo" in launched
    assert "Sign in" in launched


def test_subscribe_page_is_real_landing_page_not_account_gate():
    page = (ROOT / "subscribe.html").read_text()
    assert "Treasure Coast news without the noise." in page
    assert 'id="membership-plans"' in page
    assert 'data-plan="annual"' in page
    assert 'data-plan="monthly"' in page
    assert "Create account" not in page
    assert 'type="password"' not in page
    assert "Limited time &middot; 7 days free &middot; then $4.99/mo" in page
    assert "After your 7-day free trial, your selected subscription renews automatically until canceled" in page


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
    assert "After your 7-day free trial, your selected subscription renews automatically until canceled" in markup


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
