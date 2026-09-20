from pathlib import Path

from tct_engine.membership_paywall import inject_membership_assets

ROOT = Path(__file__).resolve().parents[1]
PARTNER_PAGE = ROOT / "partners" / "treasure-coast-community-news.html"


def test_tccn_partner_page_is_true_marketing_landing_page():
    page = PARTNER_PAGE.read_text()
    assert 'data-partner-offer="treasure-coast-community-news"' in page
    assert "We've got your first month covered." in page
    assert 'A special introductory offer, just for you.' not in page
    assert 'class="partner-offer-title"' in page
    assert 'font-size: clamp(2rem, 9.2vw, 2.45rem);' in page
    assert 'Treasure Coast Community News member offer' in page
    assert 'https://www.facebook.com/groups/188814797289161/' in page
    assert '<span class="membership-price-dollar">FREE</span>' in page
    assert 'Start my free month' in page
    assert 'Then $4.99/month' in page
    assert '<span class="membership-price-dollar">$49</span>' in page
    assert 'Annual: $49/year' in page
    assert 'The annual plan remains $49 per year and is not included in the free-month offer.' in page
    assert 'content="noindex,follow"' in page
    assert '/membership.js?v=1.13.9.38' in page


def test_normal_subscribe_page_remains_on_standard_one_dollar_offer():
    page = (ROOT / "subscribe.html").read_text()
    assert 'Full access starts at $1.' in page
    assert '<span class="membership-price-dollar">$1</span>' in page
    assert 'Get your first month for $1' in page
    assert 'Monthly offer charges $1 today.' in page
    assert 'data-partner-offer="treasure-coast-community-news"' not in page


def test_partner_checkout_uses_free_coupon_only_for_monthly():
    checkout = (ROOT / "supabase/functions/create-checkout/index.ts").read_text()
    assert "const TCCN_FREE_MONTH_COUPON = Deno.env.get('STRIPE_TCCN_FREE_MONTH_COUPON') ?? 'RIoemf0n'" in checkout
    assert "const TCCN_PARTNER_ID = 'treasure-coast-community-news'" in checkout
    assert "const partnerCoupon = partnerOffer && plan === 'monthly' ? partnerOffer.coupon : ''" in checkout
    assert "const discounts = partnerCoupon" in checkout
    assert ": plan === 'monthly'" in checkout
    assert "? [{ coupon: MONTHLY_INTRO_COUPON }]" in checkout
    assert "? 'partner_free_first_month'" in checkout
    assert "const checkoutPath = partnerOffer?.landingPath ?? '/subscribe.html'" in checkout
    assert "partner_name: partnerOffer.name" in checkout


def test_partner_id_is_sent_by_browser_and_success_copy_is_truthful():
    browser = (ROOT / "membership.js").read_text()
    complete = (ROOT / "supabase/functions/checkout-complete/index.ts").read_text()
    assert "document.body?.dataset?.partnerOffer" in browser
    assert "if (partner) checkoutBody.partner = partner" in browser
    assert "data.introductory_offer === 'partner_free_first_month'" in browser
    assert "Your free first month is active." in browser
    assert "introductory_offer: String(session.metadata?.introductory_offer || '')" in complete
    assert "partner: String(session.metadata?.partner || '')" in complete
    assert "partner_name: String(session.metadata?.partner_name || '')" in complete


def test_partner_success_and_cancel_return_to_partner_landing_page():
    checkout = (ROOT / "supabase/functions/create-checkout/index.ts").read_text()
    assert "const TCCN_LANDING_PATH = '/partners/treasure-coast-community-news.html'" in checkout
    assert "success_url: `${siteUrl}${checkoutPath}?checkout=success" in checkout
    assert "cancel_url: `${siteUrl}${checkoutPath}?checkout=cancelled" in checkout


def test_tccn_partner_page_survives_membership_asset_normalization():
    page = PARTNER_PAGE.read_text()
    normalized = inject_membership_assets(page, "")
    assert '/membership.css?v=1.13.9.36' in normalized
    assert '/membership.js?v=1.13.9.38' in normalized
    assert '/membership.js?v=1.13.9.36' not in normalized
