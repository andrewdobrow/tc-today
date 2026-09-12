from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_modal_is_not_hardcoded_into_generated_page_footer():
    source = (ROOT / "scripts" / "generate.py").read_text(encoding="utf-8")
    assert "be625cadfe" not in source


def test_desktop_keeps_kit_newsletter_while_mobile_uses_subscription_modal():
    js = (ROOT / "main.js").read_text(encoding="utf-8")
    assert js.count('uid: "be625cadfe"') == 1
    assert 'mode: "desktop-newsletter-modal"' in js
    assert 'const MOBILE_QUERY = "(max-width: 680px)"' in js
    assert "window.matchMedia(MOBILE_QUERY)" in js
    assert "if (mobile.matches) return;" in js
    assert "showMobileSubscriptionModal" in js
    assert "Get unlimited access for $1" in js
    assert "Local news worth knowing." in js


def test_mobile_subscription_modal_uses_fast_or_scroll_trigger_and_seven_day_cooldown():
    js = (ROOT / "main.js").read_text(encoding="utf-8")
    assert "const MOBILE_DELAY_MS = 5000" in js
    assert "const MOBILE_SCROLL_RATIO = 0.85" in js
    assert "window.setTimeout(attempt, MOBILE_DELAY_MS)" in js
    assert "window.innerHeight * MOBILE_SCROLL_RATIO" in js
    assert "const MOBILE_DISMISS_MS = 7 * 24 * 60 * 60 * 1000" in js
    assert "MOBILE_DISMISS_KEY" in js


def test_mobile_subscription_modal_does_not_compete_with_membership_or_paywall_state():
    js = (ROOT / "main.js").read_text(encoding="utf-8")
    assert 'document.body.classList.contains("tct-member-entitled")' in js
    assert "currentArticleIsMonthlyFree()" in js
    assert 'document.querySelector("[data-tct-free-article-banner]")' in js
    assert "paywallIsVisible()" in js
    assert 'window.addEventListener("tct:monthly-free-article", suppressForFreeArticle)' in js


def test_mobile_subscription_modal_has_bounded_first_party_green_presentation():
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    assert "TCT v1.13.8.8 - responsive acquisition modal" in css
    assert ".tct-mobile-subscription-overlay" in css
    assert "max-height:calc(100dvh - 44px)" in css
    assert "background:#174f3d" in css
    assert ".tct-mobile-subscription-close" in css
