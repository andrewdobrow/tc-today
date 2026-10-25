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
    assert "const FREE_ARTICLE_LIMIT = 2" in browser
    assert "meter_token: existingMeterToken" in browser
    assert "const FREE_ARTICLE_LIMIT = 2" in protected


def test_first_free_story_receives_clear_coral_nonblocking_invitation():
    browser = (ROOT / 'membership.js').read_text()
    css = (ROOT / 'membership.css').read_text()
    monthly = browser.split("data?.access === 'monthly_free'", 1)[1].split("return { access:'monthly_free'", 1)[0]
    assert 'const placed = placePostReadMeterAfterStory(paywall)' in monthly
    assert 'if (usedSlugs.length >= FREE_ARTICLE_LIMIT)' in monthly
    assert 'if (placed) addSoftMeterInvitation(paywall, FREE_ARTICLE_LIMIT - usedSlugs.length)' in monthly
    assert 'paywall?.remove()' in monthly
    assert "paywall.insertAdjacentElement('beforebegin', invite)" in browser
    assert "invite.setAttribute('data-tct-meter-soft-invitation', '')" in browser
    assert "invite.className = 'tct-paywall tct-meter-soft-invitation'" in browser
    assert "panel.className = 'tct-paywall-offer-panel'" in browser
    assert "strip.className = 'tct-paywall-subscriber-strip'" in browser
    assert "action.className = 'tct-member-btn tct-paywall-primary-button tct-meter-soft-action'" in browser
    assert "syncPaywallFullBleed(invite)" in browser
    soft = browser.split("function addSoftMeterInvitation(paywall, remaining){", 1)[1].split("function readMeterState(){", 1)[0]
    assert "heading.textContent = 'You only have one free article left.'" in soft
    assert "counter.textContent = 'Treasure Coast Today membership'" in soft
    assert "Your next article is still free. Subscribe anytime for unlimited access." in soft
    assert "Continue reading for" not in soft
    assert "$4.99/month after your first month. Cancel anytime." in browser
    assert '.tct-meter-soft-invitation' in css
    assert '.tct-paywall.tct-paywall-full-bleed.tct-meter-soft-invitation .tct-paywall-offer-headline' in css
    assert 'linear-gradient(145deg, #fffaf8 0%, #fdeee9 54%, #f9ddd4 100%)' in css
    assert "if (!paywall?.parentElement || remaining <= 0 || remaining >= FREE_ARTICLE_LIMIT) return" in browser


def test_versions_are_cache_busted_for_restored_paywall_copy():
    helper = (ROOT / 'tct_engine/membership_paywall.py').read_text()
    assert 'MEMBERSHIP_ASSET_VERSION = "1.13.9.114"' in helper
    assert 'MEMBERSHIP_JS_ASSET_VERSION = "1.13.9.113"' in helper


def test_coral_hard_and_soft_paywall_headlines_cannot_be_clipped():
    css = (ROOT / "membership.css").read_text()
    # Inspect the final canonical coral rules, not earlier legacy declarations.
    canonical = css.split("/* TCT v1.13.7.25", 1)[1]
    hard = canonical.split(".tct-paywall.tct-paywall-full-bleed .tct-paywall-offer-headline {", 1)[1].split("}", 1)[0]
    assert "white-space: normal" in hard
    assert "text-wrap: balance" in hard
    assert "overflow-wrap: anywhere" in hard
    assert "text-wrap: nowrap" not in hard
    assert "max-width: 680px" in hard

    soft = css.split(".tct-paywall.tct-paywall-full-bleed.tct-meter-soft-invitation .tct-paywall-offer-headline {", 1)[1].split("}", 1)[0]
    assert "white-space: normal" in soft
    assert "text-wrap: balance" in soft
    assert "overflow-wrap: anywhere" in soft

    mobile = css.rsplit("@media (max-width: 680px)", 1)[1]
    assert "white-space: normal" in mobile
    assert "overflow-wrap: anywhere" in mobile
    assert ".tct-paywall-meter-status" in mobile
