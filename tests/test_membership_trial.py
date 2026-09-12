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
    assert "Two ways to continue reading" in markup
    assert "Pay Annually" in markup
    assert "Pay Monthly" in markup
    assert '<div class="tct-paywall-card-price">$49</div>' in markup
    assert '<div class="tct-paywall-card-price">$1</div>' in markup
    assert "for your first month" in markup
    assert "$4.99/month after" in markup
    assert "Cancel anytime" in markup
    assert markup.count(">Subscribe</button>") == 2
    assert "Best value" in markup
    assert "Unlimited access to local news across Martin, St. Lucie and Indian River counties." not in markup
    assert "Secure checkout powered by Stripe." not in markup
    assert "FREE for 1 week" not in markup
    assert "free trial" not in markup.lower()


def test_subscribe_page_and_checkout_copy_match_intro_offer():
    page = (ROOT / "subscribe.html").read_text()
    browser = (ROOT / "membership.js").read_text()
    css = (ROOT / "membership.css").read_text()
    assert "Limited time &middot; $1 first month" in page
    assert "Choose your plan" in page
    assert "Full access starts at $1." in page
    assert page.index('id="membership-plans"') < page.index("membership-landing-value")
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
    assert "Limited time &middot; $1 first month" in generator
    assert "then $4.99/mo" not in generator
    assert "Get your first month for $1" in generator
    assert "Unlimited local news for $1 your first month." in generator
    assert "footer_pattern" in generator


def test_article_paywall_uses_simple_full_width_green_presentation():
    from tct_engine.membership_paywall import paywall_html
    markup = paywall_html("example-story")
    css = (ROOT / "membership.css").read_text()
    assert markup.count("tct-paywall-card ") == 2
    assert "tct-paywall-card-annual" in markup
    assert "tct-paywall-card-monthly" in markup
    assert "tct-paywall-benefits" not in markup
    assert 'class="tct-paywall-exit" href="/"' in markup
    release_css = css.split("TCT v1.13.7.20 - simple full-width article paywall cards",1)[1]
    assert "width: var(--tct-paywall-viewport-width, 100vw)" in release_css
    assert "background: #174f3d" in release_css
    assert "border-radius: 0" in release_css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in release_css
    assert "white-space: nowrap" in release_css
    assert "font-size: clamp(1.12rem, 5.25vw, 1.5rem)" in release_css
