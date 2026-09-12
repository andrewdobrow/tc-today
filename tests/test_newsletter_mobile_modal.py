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
    assert "$1 FOR YOUR FIRST MONTH" in js
    assert "Unlimited Treasure Coast news." in js
    assert ">SUBSCRIBE NOW</a>" in js


def test_mobile_subscription_modal_uses_fast_or_short_scroll_trigger_and_seven_day_cooldown():
    js = (ROOT / "main.js").read_text(encoding="utf-8")
    assert "const MOBILE_DELAY_MS = 5000" in js
    assert "const MOBILE_SCROLL_RATIO = 0.45" in js
    assert "window.setTimeout(attempt, MOBILE_DELAY_MS)" in js
    assert "Math.max(180, window.innerHeight * MOBILE_SCROLL_RATIO)" in js
    assert "const MOBILE_DISMISS_MS = 7 * 24 * 60 * 60 * 1000" in js
    assert "MOBILE_DISMISS_KEY" in js


def test_monthly_free_article_is_eligible_for_mobile_subscription_modal():
    js = (ROOT / "main.js").read_text(encoding="utf-8")
    membership = (ROOT / "membership.js").read_text(encoding="utf-8")
    assert "currentArticleIsMonthlyFree()" in js
    assert "if (!currentArticleIsMonthlyFree() && paywallIsVisible()) return true;" in js
    assert "Your free article is unlocked" in js
    assert 'document.querySelector("[data-tct-free-article-banner]")' not in js
    assert 'tct:monthly-free-article' not in js
    assert "window.matchMedia?.('(max-width: 680px)').matches" in membership


def test_mobile_subscription_modal_retries_after_membership_state_settles():
    js = (ROOT / "main.js").read_text(encoding="utf-8")
    assert "const MEMBER_HINT_KEY" in js
    assert "subscriberLikely()" in js
    assert "retryTimer = window.setTimeout" in js
    assert "1500" in js


def test_mobile_subscription_modal_has_simple_green_presentation():
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    assert "TCT v1.13.8.9 - simple mobile subscription modal" in css
    assert ".tct-mobile-subscription-overlay" in css
    assert "width:min(100%,390px)" in css
    assert "background:#174f3d" in css
    assert ".tct-mobile-subscription-close" in css
    assert "border-radius:999px" in css
