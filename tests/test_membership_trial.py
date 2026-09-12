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
    assert 'class="tct-paywall-headline-accent">$1</span>' in markup
    assert "Get full access to every story" in markup
    assert 'class="tct-paywall-current-price">$1</strong>' in markup
    assert 'class="tct-paywall-old-price">$4.99</span>' in markup
    assert "for your first month" in markup
    assert "Start for $1" in markup
    assert "$4.99/month after your first month. Cancel anytime." in markup
    assert "Prefer annual billing?" in markup
    assert "$49/year" in markup
    assert "$4.08/month" in markup
    assert "Choose annual" in markup
    assert "Unlimited access to every TCT story" in markup
    assert "Read on any device" in markup
    assert "Support local, independent journalism" in markup
    assert "Morning Brief" not in markup
    assert "tct-paywall-card" not in markup
    assert "Best value" not in markup
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


def test_article_paywall_uses_editorial_single_offer_presentation():
    from tct_engine.membership_paywall import paywall_html
    markup = paywall_html("example-story")
    css = (ROOT / "membership.css").read_text()
    assert "tct-paywall-subscriber-strip" in markup
    assert "Already a subscriber?" in markup
    assert "tct-paywall-offer-panel" in markup
    assert "tct-paywall-primary-offer" in markup
    assert "tct-paywall-benefits" in markup
    assert markup.count('data-plan="monthly"') == 1
    assert markup.count('data-plan="annual"') == 1
    assert "tct-paywall-card" not in markup
    assert 'class="tct-paywall-exit" href="/"' in markup
    release_css = css.split("TCT v1.13.7.25 — editorial single-offer article paywall",1)[1]
    assert "linear-gradient(145deg, #fffaf8 0%, #fdeee9 54%, #f9ddd4 100%)" in release_css
    assert 'font-family: "Fraunces", Georgia, "Times New Roman", serif' in release_css
    assert "linear-gradient(135deg, #ff765c 0%, #f26445 55%, #df5135 100%)" in release_css
    assert "font-size: clamp(2.25rem, 10.6vw, 2.85rem)" in release_css
    assert "white-space: nowrap" in release_css
    assert "tct-paywall-subscriber-strip" in release_css

