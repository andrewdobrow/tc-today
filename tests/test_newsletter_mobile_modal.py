from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_modal_is_not_hardcoded_into_generated_page_footer():
    source = (ROOT / "scripts" / "generate.py").read_text(encoding="utf-8")
    assert "be625cadfe" not in source


def test_kit_morning_brief_modal_runs_on_desktop_and_mobile():
    js = (ROOT / "main.js").read_text(encoding="utf-8")
    assert js.count('uid: "be625cadfe"') == 1
    assert 'mode: "sitewide-modal"' in js
    assert "loadSitewideKitModal" in js
    assert "window.setTimeout(loadSitewideKitModal, 0)" in js
    assert "RESPONSIVE ACQUISITION MODAL" not in js
    assert "showMobileSubscriptionModal" not in js
    assert "MOBILE_DELAY_MS" not in js
    assert "MOBILE_SCROLL_RATIO" not in js
    assert "SUBSCRIBE NOW" not in js


def test_mobile_subscription_modal_styles_are_retired():
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    assert "TCT v1.13.9.9 — Morning Brief modal restored on mobile" in css
    assert ".tct-mobile-subscription-overlay" not in css
    assert ".tct-mobile-subscription-modal" not in css
    assert ".tct-mobile-subscription-card" not in css


def test_monthly_free_banner_remains_suppressed_on_mobile_while_newsletter_modal_returns():
    membership = (ROOT / "membership.js").read_text(encoding="utf-8")
    main = (ROOT / "main.js").read_text(encoding="utf-8")
    assert "window.matchMedia?.('(max-width: 680px)').matches" in membership
    assert 'mode: "sitewide-modal"' in main
