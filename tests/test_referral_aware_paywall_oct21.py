"""Referral personalization is optional copy, never a subscription bypass."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_referral_copy_is_whitelisted_and_does_not_affect_entitlement():
    browser = (ROOT / 'membership.js').read_text()
    protected = (ROOT / 'supabase/functions/protected-article/index.ts').read_text()
    assert "nextdoor: {" in browser and "reddit: {" in browser
    assert "facebook: {" in browser and "newsletter: {" in browser
    assert 'utm_source' in browser and 'document.referrer' in browser
    assert 'sessionStorage.setItem(REFERRAL_SESSION_KEY, source)' in browser
    assert 'domain => host === domain || host.endsWith' in browser
    # Referral targeting is limited to optional post-read invitations.
    # It must never replace a hard-paywall headline or its subscription terms.
    assert "REFERRAL_COPY[source]?.soft" in browser
    assert "function applyReferralPaywallCopy(" not in browser
    assert "paywall.dataset.tctReferral" not in browser
    assert "Hey, Nextdoor neighbor!" not in browser
    paywall_state = browser.split("function setMeterPaywallState(", 1)[1].split("function placePostReadMeterAfterStory(", 1)[0]
    assert "Continue reading for" in paywall_state
    assert "applyReferralPaywallCopy" not in paywall_state
    assert "tct-paywall-headline-accent" in paywall_state
    assert "const FREE_ARTICLE_LIMIT = 3" in browser
    assert "meter_token: existingMeterToken" in browser
    assert "const FREE_ARTICLE_LIMIT = 3" in protected


def test_first_two_free_stories_receive_nonblocking_post_read_invitation():
    browser = (ROOT / 'membership.js').read_text()
    css = (ROOT / 'membership.css').read_text()
    monthly = browser.split("data?.access === 'monthly_free'", 1)[1].split("return { access:'monthly_free'", 1)[0]
    assert 'const placed = placePostReadMeterAfterStory(paywall)' in monthly
    assert 'if (usedSlugs.length >= FREE_ARTICLE_LIMIT)' in monthly
    assert 'if (placed) addSoftMeterInvitation(paywall, FREE_ARTICLE_LIMIT - usedSlugs.length)' in monthly
    assert 'paywall?.remove()' in monthly
    assert "paywall.insertAdjacentElement('beforebegin', invite)" in browser
    assert "invite.setAttribute('data-tct-meter-soft-invitation', '')" in browser
    assert "First month $1, then $4.99/month. Cancel anytime." in browser
    assert '.tct-meter-soft-invitation' in css
    assert "if (!paywall?.parentElement || remaining <= 0 || remaining >= FREE_ARTICLE_LIMIT) return" in browser


def test_versions_are_cache_busted_for_restored_paywall_copy():
    helper = (ROOT / 'tct_engine/membership_paywall.py').read_text()
    assert 'MEMBERSHIP_ASSET_VERSION = "1.13.9.112"' in helper
    assert 'MEMBERSHIP_JS_ASSET_VERSION = "1.13.9.112"' in helper
