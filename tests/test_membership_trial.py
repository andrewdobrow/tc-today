from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_checkout_applies_one_dollar_intro_coupon_only_to_monthly():
    checkout = (ROOT / "supabase/functions/create-checkout/index.ts").read_text()
    assert "const MONTHLY_INTRO_COUPON = Deno.env.get('STRIPE_MONTHLY_INTRO_COUPON') ?? 'z039dZCN'" in checkout
    assert "discounts: plan === 'monthly' ? [{ coupon: MONTHLY_INTRO_COUPON }] : undefined" in checkout
    assert "introductory_offer: plan === 'monthly' ? 'first_month_1_usd' : 'none'" in checkout
    assert "payment_method_collection: 'always'" in checkout
    assert "trial_period_days" not in checkout
    assert "TRIAL_DAYS" not in checkout


def test_existing_trial_status_still_grants_entitlement():
    shared = (ROOT / "supabase/functions/_shared/membership.ts").read_text()
    status = (ROOT / "supabase/functions/membership-status/index.ts").read_text()
    assert "new Set(['active', 'trialing'])" in shared
    assert "ACTIVE_STATUSES.has" in status


def test_checkout_completion_keeps_backward_compatibility_for_old_trial_sessions():
    complete = (ROOT / "supabase/functions/checkout-complete/index.ts").read_text()
    assert "'no_payment_required'" in complete
    assert "syncSubscription(subscription" in complete
    assert "plan: String(session.metadata?.plan || '')" in complete


def test_paywall_discloses_one_dollar_intro_and_renewal_price():
    from tct_engine.membership_paywall import paywall_html
    markup = paywall_html("example-story")
    assert "Keep reading for" in markup
    assert "$1 for your first month" in markup
    assert "Limited-time offer" in markup
    assert "tct-trial-urgency" in markup
    assert "Then $4.99/month" in markup
    assert "Get your first month for $1" in markup
    assert "Annual membership" in markup
    assert "$49/year" in markup
    assert "Monthly offer charges $1 today." in markup
    assert "Monthly: $1 today, then $4.99/month starting one month later." in markup
    assert "FREE for 1 week" not in markup
    assert "free trial" not in markup.lower()


def test_subscribe_page_and_checkout_copy_match_intro_offer():
    page = (ROOT / "subscribe.html").read_text()
    browser = (ROOT / "membership.js").read_text()
    css = (ROOT / "membership.css").read_text()
    assert "Limited time &middot; $1 first month &middot; then $4.99/mo" in page
    assert "membership-trial-urgency" in page
    assert "Get your first month for $1" in page
    assert "Then $4.99/month" in page
    assert "Subscribe annually" in page
    assert "Monthly offer charges $1 today." in page
    assert "Your $1 first month is active." in browser
    assert "Your annual membership is active." in browser
    assert "membership-intro-price" in css
    assert "7-day free trial" not in page


def test_generated_site_chrome_advertises_intro_offer_consistently():
    generator = (ROOT / "scripts/generate.py").read_text()
    assert "Limited time &middot; $1 first month &middot; then $4.99/mo" in generator
    assert "Get your first month for $1" in generator
    assert "Unlimited local news for $1 your first month." in generator
    assert "footer_pattern" in generator
