from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_membership_backend_is_manual_and_reader_ui_stays_dark():
    workflow = (ROOT / ".github/workflows/deploy-membership-backend.yml").read_text()
    update = (ROOT / ".github/workflows/update.yml").read_text()
    generator = (ROOT / "scripts/generate.py").read_text()

    assert "workflow_dispatch" in workflow
    assert "push:" not in workflow
    assert "TCT_MEMBERSHIP_UI_ENABLED" in update
    assert "|| 'false'" in update
    assert 'os.getenv("TCT_MEMBERSHIP_UI_ENABLED", "0")' in generator


def test_public_membership_functions_have_explicit_server_side_verification():
    config = (ROOT / "supabase/config.toml").read_text()
    assert "[functions.stripe-webhook]\nverify_jwt = false" in config
    assert "[functions.create-checkout]\nverify_jwt = false" in config
    assert "[functions.checkout-complete]\nverify_jwt = false" in config
    assert "[functions.sync-protected-articles]\nverify_jwt = false" in config
    assert "[functions.membership-status]\nverify_jwt = true" in config
    assert "[functions.create-portal]\nverify_jwt = true" in config
    assert "[functions.protected-article]\nverify_jwt = true" in config


def test_admin_bypass_is_server_side_and_not_a_static_passcode():
    migration = (ROOT / "supabase/migrations/202608090001_membership_backend.sql").read_text()
    status_fn = (ROOT / "supabase/functions/membership-status/index.ts").read_text()
    page = (ROOT / "membership-test.html").read_text()

    assert "is_admin boolean not null default false" in migration
    assert "ctx.supabaseAdmin" in status_fn
    assert "entitlement_source: isAdmin ? 'admin'" in status_fn
    assert "ADMIN ACCESS" not in page  # result comes from the authenticated function
    assert "noindex,nofollow,noarchive" in page


def test_checkout_is_checkout_first_and_uses_only_server_side_stripe_secrets():
    checkout = (ROOT / "supabase/functions/create-checkout/index.ts").read_text()
    browser = (ROOT / "membership.js").read_text()

    assert "withSupabase({ auth: 'none' }" in checkout
    assert "Deno.env.get('STRIPE_SECRET_KEY')" in checkout
    assert "Deno.env.get('STRIPE_PRICE_MONTHLY')" in checkout
    assert "Deno.env.get('STRIPE_PRICE_ANNUAL')" in checkout
    assert "customer_email" not in checkout
    assert "client_reference_id" not in checkout
    assert "{CHECKOUT_SESSION_ID}" in checkout
    assert "sk_test_" not in browser
    assert "STRIPE_SECRET_KEY" not in browser


def test_webhook_verifies_signature_before_writing_entitlement():
    webhook = (ROOT / "supabase/functions/stripe-webhook/index.ts").read_text()
    verify_at = webhook.index("constructEventAsync")
    sync_at = webhook.index("syncSubscription(event.data.object")
    assert verify_at < sync_at
    assert "STRIPE_WEBHOOK_SECRET" in webhook
    assert "stripe_webhook_events" in webhook
    assert "Do not record the event as processed" in webhook


def test_browser_config_writer_refuses_privileged_keys(monkeypatch, tmp_path):
    import importlib.util

    path = ROOT / "scripts/write_membership_browser_config.py"
    spec = importlib.util.spec_from_file_location("membership_config", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)

    monkeypatch.setattr(module, "OUT", tmp_path / "membership-config.js")
    monkeypatch.setenv("TCT_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("TCT_SUPABASE_PUBLISHABLE_KEY", "sb_secret_do_not_publish")

    try:
        module.main()
    except RuntimeError as exc:
        assert "browser-safe" in str(exc) or "privileged" in str(exc)
    else:
        raise AssertionError("privileged key was accepted for browser output")


def test_membership_backend_deploy_verifies_snapshot_capability():
    workflow = (ROOT / ".github/workflows/deploy-membership-backend.yml").read_text()
    assert "supabase functions deploy sync-protected-articles --use-api" in workflow
    assert "Verify protected-content snapshot capability" in workflow
    assert '"action":"snapshot"' in workflow
    assert "TCT_CONTENT_SYNC_SECRET" in workflow
    assert "Protected-content snapshot capability verified." in workflow
