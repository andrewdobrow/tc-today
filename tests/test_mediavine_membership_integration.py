from pathlib import Path

from tct_engine.membership_paywall import inject_membership_assets, paywall_html, paywall_section_html

ROOT = Path(__file__).resolve().parents[1]


def test_paywall_exposes_mediavine_leader_and_no_ads_feature():
    markup = paywall_html("example-story")
    assert '<div class="mv-leader"></div>' in markup
    assert markup.index('class="mv-leader"') < markup.index('data-tct-paywall')
    assert '<li>No ads</li>' in paywall_section_html("example-story")


def test_membership_assets_normalize_prepaint_for_early_mv_no_ads_targeting():
    legacy = """<html><head><script data-tct-member-prepaint>(function(){})();</script></head><body></body></html>"""
    updated = inject_membership_assets(legacy, "example-story")
    assert updated.count("data-tct-member-prepaint") == 1
    assert "mv-no-ads" in updated
    assert "MutationObserver" in updated
    assert "/membership.css?v=1.13.9.36" in updated
    assert "/membership.js?v=1.13.9.38" in updated


def test_membership_client_tracks_verified_mv_no_ads_entitlement():
    js = (ROOT / "membership.js").read_text(encoding="utf-8")
    assert "document.body?.classList.toggle('mv-no-ads', active)" in js
    assert "document.body.classList.toggle('mv-no-ads', entitled)" in js
    assert "document.body.classList.add('mv-no-ads')" in js


def test_mediavine_leader_reserves_mobile_and_desktop_height_without_paid_gap():
    css = (ROOT / "membership.css").read_text(encoding="utf-8")
    assert ".mv-leader" in css
    assert "min-height: 90px" in css
    assert "@media (min-width: 901px)" in css
    assert "min-height: 250px" in css
    assert "body.mv-no-ads .mv-leader" in css


def test_article_sidebar_is_static_for_mediavine_targeting():
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    generator = (ROOT / "scripts" / "generate.py").read_text(encoding="utf-8")
    assert ".article-side-rail {\n  position: static;\n  top: auto;" in css
    assert ".article-side-rail {{ min-width: 0; position: static; top: auto;" in generator


def test_subscribe_page_lists_no_ads_on_both_plans():
    page = (ROOT / "subscribe.html").read_text(encoding="utf-8")
    assert page.count("<li>No ads</li>") >= 2


def test_monthly_free_postread_paywall_keeps_mediavine_leader_above_offer():
    js = (ROOT / "membership.js").read_text(encoding="utf-8")
    start = js.index("function placePostReadMeterAfterStory(paywall){")
    end = js.index("function renderProtectedBody", start)
    block = js[start:end]
    assert "const mediavineLeader = memberOnly ? qs('.mv-leader', memberOnly) : null" in block
    assert "paywall.insertAdjacentElement('beforebegin', mediavineLeader)" in block
    assert block.index("paywall.insertAdjacentElement('beforebegin', mediavineLeader)") < block.index("memberOnly?.remove()")


def test_legacy_adsense_markup_is_removed_without_touching_mediavine_loader(tmp_path):
    import importlib
    import os
    import sys
    import types

    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    generate = importlib.import_module("scripts.generate")

    page = tmp_path / "legacy.html"
    page.write_text(
        '<html><head>'
        '<meta name="google-adsense-account" content="ca-pub-9679836198092378">'
        '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-9679836198092378" crossorigin="anonymous"></script>'
        f'{generate.MEDIAVINE_SCRIPT_TAG}'
        '</head><body>Story</body></html>',
        encoding="utf-8",
    )

    report = generate._remove_legacy_adsense_sitewide(tmp_path)
    cleaned = page.read_text(encoding="utf-8")

    assert report == {"scanned": 1, "updated": 1}
    assert "google-adsense-account" not in cleaned
    assert "pagead2.googlesyndication.com" not in cleaned
    assert generate.MEDIAVINE_SCRIPT_SRC in cleaned


def test_html_generators_no_longer_emit_adsense_account_meta_tag():
    for rel in ("scripts/generate.py", "generate.py", "scripts/build_audience_features.py"):
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert '<meta name="google-adsense-account"' not in source
