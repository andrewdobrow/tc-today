from __future__ import annotations

import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import sys

from tct_engine.membership_paywall import (
    add_paywall_schema,
    inject_membership_assets,
    is_public_service_exception,
    paywall_html,
    split_article_body,
)

ROOT = Path(__file__).resolve().parents[1]


def test_character_bounded_cliffhanger_hides_first_paragraph_remainder_completely():
    secret = "MEMBER-ONLY-DETAIL-92341"
    first = (
        "Port St. Lucie officials approved the project after months of debate, and the vote "
        "sets up several immediate changes for residents and businesses across the city that "
        "will begin taking effect over the coming weeks with additional details still pending."
    )
    body = (
        f"<p>{first}</p>"
        f"<p>Second paragraph contains {secret} and should never be public.</p>"
        "<p>Later reporting adds more detail and another substantial paragraph for members.</p>"
    )
    split = split_article_body(body)
    assert split is not None
    assert 'data-tct-preview-paragraph="true"' in split.preview_html
    assert 'tct-preview-fade-text' in split.preview_html
    assert 'tct-preview-ellipsis' in split.preview_html
    assert secret not in split.preview_html
    assert "Second paragraph" not in split.preview_html
    assert secret in split.protected_html
    assert 'data-tct-first-paragraph-continuation="true"' in split.protected_html

    preview_plain = re.sub(r"<[^>]+>", " ", split.preview_html)
    preview_plain = re.sub(r"\s+", " ", preview_plain).strip().rstrip("…")
    assert len(preview_plain) <= 300
    assert len(preview_plain) < len(first) * 0.62
    assert len(preview_plain) > len(first) * 0.35


def test_public_service_exceptions_are_narrow():
    assert is_public_service_exception("Mandatory evacuation order issued for barrier island", "<p>Residents must leave now.</p>")
    assert is_public_service_exception("Boil water notice issued in Stuart", "<p>The advisory remains active.</p>")
    assert is_public_service_exception("Missing child alert issued", "<p>A missing girl was last seen Friday.</p>")
    assert not is_public_service_exception("Candidate campaigns on hurricane preparedness", "<p>The election is Tuesday.</p>")
    assert not is_public_service_exception("Bridge construction project advances", "<p>Lane closures begin next month.</p>")


def test_paywall_markup_uses_locked_copy_and_pay_first_buttons():
    markup = paywall_html("example-story")
    assert "Two ways to continue reading" in markup
    assert "Comprehensive local coverage. No ads. Less than $5 a month." in markup
    assert "Annual — $49/year" in markup
    assert "Monthly — $4.99/month" in markup
    assert "Subscribe annually" in markup
    assert "Subscribe monthly" in markup
    assert "Already a member?" in markup
    assert "Create account" not in markup
    assert "password" not in markup.lower()


def test_paywalled_schema_and_assets_are_injected_without_body_payload():
    page = '''<!doctype html><html><head><script type="application/ld+json">{"@context":"https://schema.org","@type":"NewsArticle","isAccessibleForFree":true}</script></head><body><h1>Story</h1></body></html>'''
    page = add_paywall_schema(page)
    page = inject_membership_assets(page, "story-slug")
    assert '"isAccessibleForFree":false' in page
    assert '"cssSelector":".tct-paywalled-content"' in page
    assert '/membership.css' in page
    assert '/membership.js' in page
    assert 'data-article-slug="story-slug"' in page


def test_subscribe_page_has_no_registration_gate_before_plan_buttons():
    page = (ROOT / "subscribe.html").read_text()
    annual_at = page.index('data-plan="annual"')
    monthly_at = page.index('data-plan="monthly"')
    assert annual_at > 0 and monthly_at > 0
    assert "Create account" not in page
    assert 'type="password"' not in page
    assert "Email me a sign-in link" in page



def test_membership_plan_cards_are_visually_balanced_and_gradient_backed():
    page = (ROOT / "subscribe.html").read_text()
    css = (ROOT / "membership.css").read_text()
    markup = paywall_html("example-story")
    assert "Most flexible" in page
    assert "Most flexible" in markup
    assert '<div class="membership-price">$4.99</div>' in page
    assert '<div class="membership-plan-note">Cancel anytime</div>' in page
    assert 'linear-gradient(135deg,#f26445 0%,#f87858 48%,#e9583e 100%)' in css
    assert 'color:#fff}.membership-kicker' in css
    assert 'background:var(--tct-member-paper);color:var(--tct-member-charcoal)' in css
    assert 'color:rgba(255,255,255,.88)' in css
    assert 'text-align:center' in css
    assert 'margin-top:auto' in css


def test_checkout_completion_creates_or_links_identity_then_sends_passwordless_access():
    completion = (ROOT / "supabase/functions/checkout-complete/index.ts").read_text()
    shared = (ROOT / "supabase/functions/_shared/membership.ts").read_text()
    webhook = (ROOT / "supabase/functions/stripe-webhook/index.ts").read_text()
    assert "checkout.sessions.retrieve" in completion
    assert "resolveMembershipUser" in completion
    assert "signInWithOtp" in completion
    assert "shouldCreateUser: false" in completion
    assert "auth.admin.createUser" in shared
    assert "customer_details?.email" in webhook
    assert "resolveMembershipUser" in webhook


def test_protected_content_is_entitlement_checked_server_side():
    protected = (ROOT / "supabase/functions/protected-article/index.ts").read_text()
    assert "withSupabase({ auth: 'user' }" in protected
    assert "is_admin" in protected
    assert "ACTIVE_STATUSES" in protected
    assert "MEMBERSHIP_REQUIRED" in protected
    assert ".from('protected_articles')" in protected


def test_protected_sync_uses_dedicated_secret_and_never_browser_config():
    sync_fn = (ROOT / "supabase/functions/sync-protected-articles/index.ts").read_text()
    workflow = (ROOT / ".github/workflows/update.yml").read_text()
    writer = (ROOT / "scripts/write_membership_browser_config.py").read_text()
    assert "TCT_CONTENT_SYNC_SECRET" in sync_fn
    assert "X-TCT-Content-Sync" in sync_fn
    assert "secrets.TCT_CONTENT_SYNC_SECRET" in workflow
    assert "TCT_CONTENT_SYNC_SECRET" not in writer


def test_launch_pipeline_exports_protected_text_outside_repo_and_requires_sync():
    workflow = (ROOT / ".github/workflows/update.yml").read_text()
    prep = (ROOT / "scripts/prepare_membership_paywall.py").read_text()
    assert "/tmp/tct-protected-articles.json" in workflow
    assert "--required" in workflow
    assert "outside the public repository" in prep
    assert "data-tct-paywall" in prep


def test_config_writer_fails_closed_if_ui_enabled_without_public_config(monkeypatch, tmp_path):
    path = ROOT / "scripts/write_membership_browser_config.py"
    spec = importlib.util.spec_from_file_location("membership_config_v2", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "OUT", tmp_path / "membership-config.js")
    monkeypatch.setattr(module, "SUBSCRIBE", tmp_path / "subscribe.html")
    monkeypatch.setenv("TCT_MEMBERSHIP_UI_ENABLED", "true")
    monkeypatch.delenv("TCT_SUPABASE_URL", raising=False)
    monkeypatch.delenv("TCT_SUPABASE_PUBLISHABLE_KEY", raising=False)
    try:
        module.main()
    except RuntimeError as exc:
        assert "cannot be enabled" in str(exc)
    else:
        raise AssertionError("launch accepted missing browser configuration")


def test_paywall_prepare_script_keeps_secret_remainder_out_of_public_html(tmp_path, monkeypatch):
    # Exercise the transformation mechanism against a tiny isolated repo shape.
    script_path = ROOT / "scripts/prepare_membership_paywall.py"
    spec = importlib.util.spec_from_file_location("prepare_membership", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)

    root = tmp_path / "repo"
    articles = root / "articles"
    articles.mkdir(parents=True)
    secret = "PROTECTED-SENTINEL-7843"
    page = f'''<html><head><script type="application/ld+json">{{"@type":"NewsArticle","isAccessibleForFree":true}}</script></head><body><h1 class="article-headline">Council approves project</h1><div class="article-body"><p>Lead paragraph explains the decision.</p><p>Second paragraph first sentence. Second paragraph second sentence. {secret} is hidden here.</p><p>This later paragraph contains enough member-only reporting to exceed the minimum protected length by a comfortable margin for the test.</p></div><div class="article-share">share</div></body></html>'''
    article = articles / "council-project.html"
    article.write_text(page)
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module, "ARTICLES", articles)
    monkeypatch.setenv("TCT_MEMBERSHIP_UI_ENABLED", "true")
    export = tmp_path / "protected.json"
    monkeypatch.setenv("TCT_PROTECTED_EXPORT_PATH", str(export))
    module.main()

    public = article.read_text()
    payload = json.loads(export.read_text())
    assert secret not in public
    assert secret in payload["articles"][0]["protected_body"]
    assert "data-tct-paywall" in public
    assert '"isAccessibleForFree":false' in public


def test_membership_cli_scripts_bootstrap_repo_package_when_executed_by_path():
    env = os.environ.copy()
    env["TCT_MEMBERSHIP_UI_ENABLED"] = "false"
    prep = subprocess.run(
        [sys.executable, str(ROOT / "scripts/prepare_membership_paywall.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert prep.returncode == 0, prep.stderr
    assert "Membership paywall preparation skipped: UI disabled" in prep.stdout

    sync = subprocess.run(
        [sys.executable, str(ROOT / "scripts/sync_protected_articles.py"), "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert sync.returncode == 0, sync.stderr
    assert "--scan-public" in sync.stdout
