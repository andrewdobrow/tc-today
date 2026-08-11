from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_checkout_starts_seven_day_trial_and_collects_payment_method():
    checkout = (ROOT / "supabase/functions/create-checkout/index.ts").read_text()
    assert "const TRIAL_DAYS = 7" in checkout
    assert "payment_method_collection: 'always'" in checkout
    assert "trial_period_days: TRIAL_DAYS" in checkout
    assert "trial_days: String(TRIAL_DAYS)" in checkout


def test_trial_status_already_grants_entitlement():
    shared = (ROOT / "supabase/functions/_shared/membership.ts").read_text()
    status = (ROOT / "supabase/functions/membership-status/index.ts").read_text()
    assert "new Set(['active', 'trialing'])" in shared
    assert "ACTIVE_STATUSES.has" in status


def test_checkout_completion_accepts_zero_due_trial_session():
    complete = (ROOT / "supabase/functions/checkout-complete/index.ts").read_text()
    assert "'no_payment_required'" in complete
    assert "syncSubscription(subscription" in complete


def test_paywall_discloses_trial_and_post_trial_price():
    from tct_engine.membership_paywall import paywall_html
    markup = paywall_html("example-story")
    assert "FREE for 1 week" in markup
    assert "Limited-time offer" in markup
    assert "tct-trial-urgency" in markup
    assert "tct-trial-price-old" in markup
    assert "7 days free · then $4.99/month" in markup
    assert "Card required. You won’t be charged today." in markup
    assert "Cancel before the trial ends to avoid a charge." in markup


def test_subscribe_page_and_checkout_copy_match_trial_offer():
    page = (ROOT / "subscribe.html").read_text()
    browser = (ROOT / "membership.js").read_text()
    css = (ROOT / "membership.css").read_text()
    assert "Limited time &middot; 7 days free &middot; then $4.99/mo" in page
    assert "membership-trial-urgency" in page
    assert "Start 7-day free trial" in page
    assert "Your 7-day free trial has started" in browser
    assert "membership-trial-price-old" in css
    assert "text-decoration-line:line-through" in css


def test_generated_site_chrome_advertises_trial_consistently():
    generator = (ROOT / "scripts/generate.py").read_text()
    assert "Limited time &middot; 7 days free &middot; then $4.99/mo" in generator
    assert "Start your free trial" in generator
    assert "Unlimited local news. Free for your first week." in generator
