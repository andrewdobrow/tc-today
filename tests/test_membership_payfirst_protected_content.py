from __future__ import annotations

import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import sys

from tct_engine.membership_paywall import (
    add_paywall_schema,
    inject_membership_assets,
    paywall_html,
    split_article_body,
)

ROOT = Path(__file__).resolve().parents[1]


def _preview_plain(split) -> str:
    text = re.sub(r"<[^>]+>", " ", split.preview_html)
    return re.sub(r"\s+", " ", text).strip()


def test_character_bounded_cliffhanger_is_consistent_across_paragraph_shapes():
    secret = "MEMBER-ONLY-DETAIL-92341"
    long_lead = (
        "Port St. Lucie officials approved the project after months of debate, and the vote "
        "sets up several immediate changes for residents and businesses across the city that "
        "will begin taking effect over the coming weeks with additional details still pending. "
        "Officials said the next phase includes public meetings, engineering review and a final "
        "implementation schedule that will affect several neighborhoods."
    )
    short_lead = "Port St. Lucie officials approved the project Tuesday night after months of debate."
    tail = (
        "A second paragraph adds context, names the affected neighborhoods and explains why the decision matters "
        "to residents, businesses and nearby property owners before moving into the detailed implementation record. "
        f"The member section later contains {secret} along with the timeline, costs, objections and next steps."
    )
    long_split = split_article_body(f"<p>{long_lead}</p><p>{tail}</p><p>{tail}</p>")
    short_split = split_article_body(f"<p>{short_lead}</p><p>{tail}</p><p>{tail}</p>")
    assert long_split is not None and short_split is not None

    for split in (long_split, short_split):
        preview = _preview_plain(split)
        assert 250 <= len(preview) <= 340
        assert 'data-tct-preview-copy="true"' in split.preview_html
        assert secret not in split.preview_html
        assert split.protected_html.startswith("<!--tct-full-article-v2-->")
        assert secret in split.protected_html

    # A short lead is allowed to flow into paragraph two instead of producing a
    # one-line teaser, while a giant lead cannot dump most of itself for free.
    assert short_split.preview_html.count("<p") >= 2
    assert long_split.preview_html.count("<p") == 1
    assert abs(len(_preview_plain(long_split)) - len(_preview_plain(short_split))) <= 90


def test_short_article_keeps_meaningful_content_behind_paywall():
    first = "The attorney shared information about the importance of documenting collision evidence after a truck crash."
    second = (
        "The lawyer said scene photos, witness information and other records can matter later, "
        "especially when the parties disagree about what happened and who was responsible."
    )
    third = "Additional guidance explains what drivers should preserve and when to seek professional help."
    split = split_article_body(f"<p>{first}</p><p>{second}</p><p>{third}</p>")
    assert split is not None
    preview = _preview_plain(split)
    full = re.sub(r"<[^>]+>", " ", split.protected_html.replace("<!--tct-full-article-v2-->", ""))
    full = re.sub(r"\s+", " ", full).strip()
    assert 150 <= len(preview) <= 340
    assert len(full) - len(preview) >= 90


def _public_service_fixture_body():
    return (
        "<p>Deputies issued an Amber Alert for a missing child Saturday evening and asked residents across the county to check cameras and immediately report credible sightings to law enforcement.</p>"
        "<p>Investigators released identifying details, the last known location and a description of the vehicle connected to the active search while patrol units continued checking nearby neighborhoods.</p>"
        "<p>Authorities said anyone with information should contact the sheriff's office rather than approach the vehicle, and additional verified updates will be released as the search develops.</p>"
    )


def test_public_service_articles_are_not_exempt_from_protected_content_scan(tmp_path, monkeypatch):
    script_path = ROOT / "scripts/sync_protected_articles.py"
    spec = importlib.util.spec_from_file_location("sync_protected_articles_no_exemptions", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)

    articles = tmp_path / "articles"
    articles.mkdir()
    alert_slug = "amber-alert-missing-child"
    alert_body = _public_service_fixture_body()
    (articles / f"{alert_slug}.html").write_text(
        '<h1 class="article-headline">Amber Alert issued for missing child</h1>'
        f'<div class="article-body">{alert_body}</div>',
        encoding="utf-8",
    )

    flock_slug = "flock-camera-homicide-story"
    flock_body = (
        "<p>The sheriff credited Flock safety cameras with helping investigators trace a homicide suspect and described how the system supported the arrest while detectives reconstructed the suspect's movements.</p>"
        "<p>A resident said she sees value in the technology for serious cases such as locating missing children, but also wants clear rules governing retention, access and accountability.</p>"
        "<p>Officials said the homicide investigation remains active and discussed the broader privacy debate surrounding automated license-plate reader systems used by law enforcement agencies.</p>"
    )
    (articles / f"{flock_slug}.html").write_text(
        '<h1 class="article-headline">Sheriff credits Flock safety cameras in homicide investigation</h1>'
        f'<div class="article-body">{flock_body}</div>',
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ROOT", tmp_path)

    rows = module.scan_public_articles()
    assert [row["slug"] for row in rows] == [alert_slug, flock_slug]
    assert all(row["protected_body"].startswith("<!--tct-full-article-v2-->") for row in rows)


def test_prepare_paywall_protects_public_service_article(tmp_path, monkeypatch):
    script_path = ROOT / "scripts/prepare_membership_paywall.py"
    spec = importlib.util.spec_from_file_location("prepare_membership_no_exemptions", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)

    articles = tmp_path / "articles"
    articles.mkdir()
    slug = "boil-water-emergency"
    body = _public_service_fixture_body().replace("Amber Alert for a missing child", "boil water notice for residents")
    page = (
        '<!doctype html><html><head><script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"NewsArticle","isAccessibleForFree":true}'
        '</script></head><body>'
        '<h1 class="article-headline">Boil water notice issued in Stuart</h1>'
        f'<div class="article-body">{body}</div>'
        '<div class="article-share">share</div></body></html>'
    )
    article_path = articles / f"{slug}.html"
    article_path.write_text(page, encoding="utf-8")
    export_path = tmp_path / "protected-export.json"

    monkeypatch.setattr(module, "ARTICLES", articles)
    monkeypatch.setenv("TCT_MEMBERSHIP_UI_ENABLED", "true")
    monkeypatch.setenv("TCT_PROTECTED_EXPORT_PATH", str(export_path))
    monkeypatch.delenv("TCT_PROTECTED_SNAPSHOT_PATH", raising=False)
    module.main()

    rewritten = article_path.read_text(encoding="utf-8")
    assert 'data-tct-paywall' in rewritten
    assert '"isAccessibleForFree":false' in rewritten
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    assert [row["slug"] for row in payload["articles"]] == [slug]


def test_paywall_markup_uses_locked_copy_and_pay_first_buttons():
    markup = paywall_html("example-story")
    assert "Continue reading Treasure Coast Today for just $1." in markup
    assert "Treasure Coast Today Membership" in markup
    assert "Introductory offer" in markup
    assert '<strong>$1</strong><span>for your first month</span>' in markup
    assert "Continue for $1" in markup
    assert markup.count("Continue for $1") == 1
    assert markup.count("Continue annually") == 1
    assert "Already a subscriber?" in markup
    assert "Create account" not in markup
    assert "password" not in markup.lower()


def test_paywalled_schema_and_assets_are_injected_without_body_payload():
    page = '''<!doctype html><html><head><script type="application/ld+json">{"@context":"https://schema.org","@type":"NewsArticle","isAccessibleForFree":true}</script></head><body><h1>Story</h1></body></html>'''
    page = add_paywall_schema(page)
    page = inject_membership_assets(page, "story-slug")
    assert '"isAccessibleForFree":false' in page
    assert '"cssSelector":".tct-paywalled-content"' in page
    assert '/membership.css' in page
    assert '/membership.js' in page
    assert 'data-article-slug="story-slug"' in page


def test_subscribe_page_has_no_registration_gate_before_plan_buttons():
    page = (ROOT / "subscribe.html").read_text()
    annual_at = page.index('data-plan="annual"')
    monthly_at = page.index('data-plan="monthly"')
    assert annual_at > 0 and monthly_at > 0
    assert "Create account" not in page
    assert 'type="password"' not in page
    assert "Email me a sign-in link" in page



def test_membership_article_paywall_uses_publication_grade_equal_plan_hierarchy():
    page = (ROOT / "subscribe.html").read_text()
    css = (ROOT / "membership.css").read_text()
    markup = paywall_html("example-story")
    # The standalone subscribe page keeps its full two-plan treatment.
    assert "Best annual value" in page
    assert 'membership-price-dollar">$1</span>' in page
    assert 'membership-price-period"> first month</span>' in page
    assert '<div class="membership-plan-note">Then $4.99/month</div>' in page
    # The in-article gate uses the same restrained editorial structure for both plans.
    assert "tct-paywall-plan-offer-monthly" in markup
    assert "tct-paywall-plan-offer-annual" in markup
    assert "Continue for $1" in markup
    assert "Continue annually" in markup
    assert "tct-paywall-plan best" not in markup
    release_css = css.split("TCT v1.13.6.8g", 1)[1]
    assert "background:var(--pw-paper)" in css
    assert "border-top:5px solid var(--pw-green)" in css
    assert "grid-template-columns:minmax(0,1fr) auto" in release_css
    assert "linear-gradient(135deg,#f26445" not in release_css


def test_checkout_completion_creates_or_links_identity_then_sends_passwordless_access():
    completion = (ROOT / "supabase/functions/checkout-complete/index.ts").read_text()
    shared = (ROOT / "supabase/functions/_shared/membership.ts").read_text()
    webhook = (ROOT / "supabase/functions/stripe-webhook/index.ts").read_text()
    assert "checkout.sessions.retrieve" in completion
    assert "resolveMembershipUser" in completion
    assert "signInWithOtp" in completion
    assert "shouldCreateUser: false" in completion
    assert "auth.admin.createUser" in shared
    assert "customer_details?.email" in webhook
    assert "resolveMembershipUser" in webhook


def test_protected_content_is_entitlement_or_monthly_meter_checked_server_side():
    protected = (ROOT / "supabase/functions/protected-article/index.ts").read_text()
    config = (ROOT / "supabase/config.toml").read_text()
    assert "withSupabase({ auth: 'none' }" in protected
    assert "is_admin" in protected
    assert "ACTIVE_STATUSES" in protected
    assert "optionalUserId(req, ctx)" in protected
    assert "meterSignature" in protected
    assert "signMeterToken" in protected
    assert "readMeterToken" in protected
    assert "FREE_ARTICLE_USED" in protected
    assert "one_free_article_per_month" in protected
    assert ".from('protected_articles')" in protected
    section = config.split("[functions.protected-article]", 1)[1].split("[functions.", 1)[0]
    assert "verify_jwt = false" in section


def test_protected_sync_uses_dedicated_secret_and_never_browser_config():
    sync_fn = (ROOT / "supabase/functions/sync-protected-articles/index.ts").read_text()
    workflow = (ROOT / ".github/workflows/update.yml").read_text()
    writer = (ROOT / "scripts/write_membership_browser_config.py").read_text()
    assert "TCT_CONTENT_SYNC_SECRET" in sync_fn
    assert "X-TCT-Content-Sync" in sync_fn
    assert "action === 'snapshot'" in sync_fn
    assert "secrets.TCT_CONTENT_SYNC_SECRET" in workflow
    assert "--snapshot-file /tmp/tct-protected-current.json --required" in workflow
    assert "TCT_PROTECTED_SNAPSHOT_PATH: /tmp/tct-protected-current.json" in workflow
    assert "Legacy sync-protected-articles function detected" in workflow
    assert "supabase functions deploy sync-protected-articles --use-api" in workflow
    assert "SUPABASE_ACCESS_TOKEN" in workflow
    assert "TCT_CONTENT_SYNC_SECRET" not in writer


def test_launch_pipeline_exports_protected_text_outside_repo_and_requires_sync():
    workflow = (ROOT / ".github/workflows/update.yml").read_text()
    prep = (ROOT / "scripts/prepare_membership_paywall.py").read_text()
    assert "/tmp/tct-protected-articles.json" in workflow
    assert "--required" in workflow
    assert "outside the public repository" in prep
    assert "data-tct-paywall" in prep


def test_config_writer_fails_closed_if_ui_enabled_without_public_config(monkeypatch, tmp_path):
    path = ROOT / "scripts/write_membership_browser_config.py"
    spec = importlib.util.spec_from_file_location("membership_config_v2", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "OUT", tmp_path / "membership-config.js")
    monkeypatch.setattr(module, "SUBSCRIBE", tmp_path / "subscribe.html")
    monkeypatch.setenv("TCT_MEMBERSHIP_UI_ENABLED", "true")
    monkeypatch.delenv("TCT_SUPABASE_URL", raising=False)
    monkeypatch.delenv("TCT_SUPABASE_PUBLISHABLE_KEY", raising=False)
    try:
        module.main()
    except RuntimeError as exc:
        assert "cannot be enabled" in str(exc)
    else:
        raise AssertionError("launch accepted missing browser configuration")


def test_paywall_prepare_script_keeps_secret_remainder_out_of_public_html(tmp_path, monkeypatch):
    # Exercise the transformation mechanism against a tiny isolated repo shape.
    script_path = ROOT / "scripts/prepare_membership_paywall.py"
    spec = importlib.util.spec_from_file_location("prepare_membership", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)

    root = tmp_path / "repo"
    articles = root / "articles"
    articles.mkdir(parents=True)
    secret = "PROTECTED-SENTINEL-7843"
    page = f'''<html><head><script type="application/ld+json">{{"@type":"NewsArticle","isAccessibleForFree":true}}</script></head><body><h1 class="article-headline">Council approves project</h1><div class="article-body"><p>Lead paragraph explains the decision and gives readers the essential setup without resolving the entire story.</p><p>Second paragraph adds context about the vote, the affected neighborhoods, the timeline and what residents should expect next.</p><p>This later paragraph contains enough member-only reporting to exceed the minimum protected length by a comfortable margin for the test. {secret} stays well behind the teaser boundary with the detailed reaction and implementation record.</p></div><div class="article-share">share</div></body></html>'''
    article = articles / "council-project.html"
    article.write_text(page)
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module, "ARTICLES", articles)
    monkeypatch.setenv("TCT_MEMBERSHIP_UI_ENABLED", "true")
    export = tmp_path / "protected.json"
    monkeypatch.setenv("TCT_PROTECTED_EXPORT_PATH", str(export))
    module.main()

    public = article.read_text()
    payload = json.loads(export.read_text())
    assert secret not in public
    assert secret in payload["articles"][0]["protected_body"]
    assert "data-tct-paywall" in public
    assert '"isAccessibleForFree":false' in public


def test_prepare_rehydrates_existing_paywall_then_resplits_to_uniform_teaser(tmp_path, monkeypatch):
    script_path = ROOT / "scripts/prepare_membership_paywall.py"
    spec = importlib.util.spec_from_file_location("prepare_membership_rehydrate", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)

    root = tmp_path / "repo"
    articles = root / "articles"
    articles.mkdir(parents=True)
    slug = "legacy-story"
    visible = (
        "The first paragraph was previously exposed in full even though it is unusually long and gives away too much of the story. "
        "It keeps going with background that should now be part of a bounded teaser."
    )
    partial_second = "The old paywall also exposed this opening sentence of paragraph two."
    hidden = (
        "The rest of paragraph two contains the development readers are paying to continue reading, followed by several additional "
        "facts, reaction and context that remain protected for members."
    )
    old_page = (
        '<html><head><script type="application/ld+json">{"@type":"NewsArticle","isAccessibleForFree":false}</script></head><body>'
        '<h1 class="article-headline">Legacy story</h1>'
        f'<div class="article-body tct-member-preview"><p>{visible}</p><p>{partial_second}</p></div>'
        f'<div class="tct-member-only"><div class="tct-paywall-fade"></div><section class="tct-paywall" data-tct-paywall data-slug="{slug}"></section>'
        '<div id="tct-protected-content" class="article-body tct-protected-content tct-paywalled-content"></div></div>'
        '<div class="article-share">share</div></body></html>'
    )
    (articles / f"{slug}.html").write_text(old_page)
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps({"articles": [{
        "slug": slug,
        "protected_body": f"<p>{hidden}</p><p>Final member paragraph with more reporting and enough length to remain meaningfully protected from anonymous readers.</p>",
    }]}))
    export = tmp_path / "new-protected.json"

    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module, "ARTICLES", articles)
    monkeypatch.setenv("TCT_MEMBERSHIP_UI_ENABLED", "true")
    monkeypatch.setenv("TCT_PROTECTED_EXPORT_PATH", str(export))
    monkeypatch.setenv("TCT_PROTECTED_SNAPSHOT_PATH", str(snapshot))
    module.main()

    public = (articles / f"{slug}.html").read_text()
    payload = json.loads(export.read_text())
    assert 'data-tct-preview-copy="true"' in public
    preview_match = re.search(r'<div class="tct-preview-copy"[^>]*>(.*?)</div>', public, re.S)
    assert preview_match
    preview_plain = re.sub(r"<[^>]+>", " ", preview_match.group(1))
    preview_plain = re.sub(r"\s+", " ", preview_plain).strip()
    assert 250 <= len(preview_plain) <= 340
    assert hidden not in public
    assert payload["articles"][0]["protected_body"].startswith("<!--tct-full-article-v2-->")
    assert visible in payload["articles"][0]["protected_body"]
    assert partial_second in payload["articles"][0]["protected_body"]
    assert hidden in payload["articles"][0]["protected_body"]

def test_prepare_rehydrates_v154_split_without_leaking_ellipsis(tmp_path, monkeypatch):
    script_path = ROOT / "scripts/prepare_membership_paywall.py"
    spec = importlib.util.spec_from_file_location("prepare_membership_rehydrate_current", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)

    root = tmp_path / "repo"
    articles = root / "articles"
    articles.mkdir(parents=True)
    slug = "current-split-story"
    first_full = (
        "The attorney shared information about the importance of scene documentation following truck accidents. "
        "According to the lawyer, many people fail to properly document evidence at collision scenes."
    )
    solid = "The attorney shared information about the importance of"
    faded = "scene documentation following truck"
    hidden_first = first_full[len((solid + " " + faded)) :].lstrip()
    later = (
        "The lawyer emphasized that this step is frequently overlooked by those involved in truck accidents. "
        "Proper documentation can become important when accounts of the collision conflict."
    )
    old_page = (
        '<html><head><script type="application/ld+json">{"@type":"NewsArticle","isAccessibleForFree":false}</script></head><body>'
        '<h1 class="article-headline">Current split story</h1>'
        '<div class="article-body tct-member-preview">'
        f'<p data-tct-preview-paragraph="true"><span class="tct-preview-solid">{solid}</span> '
        f'<span class="tct-preview-fade-text">{faded}</span><span class="tct-preview-ellipsis">…</span></p></div>'
        f'<div class="tct-member-only"><div class="tct-paywall-fade"></div><section class="tct-paywall" data-tct-paywall data-slug="{slug}"></section>'
        '<div id="tct-protected-content" class="article-body tct-protected-content tct-paywalled-content"></div></div>'
        '<div class="article-share">share</div></body></html>'
    )
    (articles / f"{slug}.html").write_text(old_page)
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps({"articles": [{
        "slug": slug,
        "protected_body": f'<p data-tct-first-paragraph-continuation="true">{hidden_first}</p><p>{later}</p><p>Additional member reporting adds enough length for the new bounded teaser to remain safely protected.</p>',
    }]}))
    export = tmp_path / "current-protected.json"

    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module, "ARTICLES", articles)
    monkeypatch.setenv("TCT_MEMBERSHIP_UI_ENABLED", "true")
    monkeypatch.setenv("TCT_PROTECTED_EXPORT_PATH", str(export))
    monkeypatch.setenv("TCT_PROTECTED_SNAPSHOT_PATH", str(snapshot))
    module.main()

    payload = json.loads(export.read_text())
    stored = payload["articles"][0]["protected_body"]
    assert stored.startswith("<!--tct-full-article-v2-->")
    assert "… accidents" not in stored
    assert "truck accidents" in stored
    assert later in stored

def test_membership_cli_scripts_bootstrap_repo_package_when_executed_by_path():
    env = os.environ.copy()
    env["TCT_MEMBERSHIP_UI_ENABLED"] = "false"
    prep = subprocess.run(
        [sys.executable, str(ROOT / "scripts/prepare_membership_paywall.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert prep.returncode == 0, prep.stderr
    assert "Membership paywall preparation skipped: UI disabled" in prep.stdout

    sync = subprocess.run(
        [sys.executable, str(ROOT / "scripts/sync_protected_articles.py"), "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert sync.returncode == 0, sync.stderr
    assert "--scan-public" in sync.stdout
    assert "--snapshot-file" in sync.stdout


def test_verified_member_hint_suppresses_paywall_before_first_paint_without_granting_content():
    page = '<!doctype html><html><head><title>Story</title></head><body><div class="article-body">Body</div></body></html>'
    page = inject_membership_assets(page, "story-slug")
    css = (ROOT / "membership.css").read_text()
    js = (ROOT / "membership.js").read_text()

    # The tiny synchronous hint runs in <head>, before any body/paywall can paint.
    assert 'data-tct-member-prepaint' in page
    assert "localStorage.getItem('tct_member_entitled_hint')==='1'" in page
    assert "document.documentElement.classList.add('tct-member-preverified')" in page
    assert page.index('data-tct-member-prepaint') < page.index('</head>') < page.index('<body')

    # Retained pages receive cache-busted assets so the no-flash code takes effect
    # immediately after deployment rather than waiting on an old browser cache.
    assert 'href="/membership.css?v=1.13.7.1d"' in page
    assert 'src="/membership.js?v=1.13.7.1d"' in page

    # The hint only changes presentation: the sales card/fade are suppressed and
    # the teaser is shown without its anonymous-reader mask while verification runs.
    assert 'html.tct-member-preverified .tct-member-only' in css
    assert 'display: none !important' in css
    assert 'html.tct-member-preverified .tct-preview-copy' in css
    assert 'mask-image: none !important' in css

    # The hint is written only from a successful server membership decision and
    # cannot substitute for the entitlement check that gates protected content.
    entitled_at = js.index('const entitled = Boolean(data?.entitled)')
    hint_at = js.index('setMemberHint(entitled)', entitled_at)
    protected_fetch_at = js.index("supabase.functions.invoke('protected-article'")
    meter_reservation_at = js.index('const reservation = reserveMeterArticle(slug)')
    assert entitled_at < hint_at
    assert protected_fetch_at > 0
    assert meter_reservation_at > protected_fetch_at
    assert "localStorage.getItem(MEMBER_HINT_KEY)" not in js
    assert "localStorage.setItem(MEMBER_HINT_KEY, '1')" in js
    assert "localStorage.removeItem(MEMBER_HINT_KEY)" in js
    assert "event === 'SIGNED_OUT'" in js


def test_membership_asset_injection_is_idempotent_and_upgrades_old_unversioned_assets():
    page = '''<!doctype html><html><head><link rel="stylesheet" href="/membership.css"></head><body data-article-slug="old"><script src="/membership-config.js"></script><script type="module" src="/membership.js"></script></body></html>'''
    first = inject_membership_assets(page, "old")
    second = inject_membership_assets(first, "old")
    assert first == second
    assert first.count('data-tct-member-prepaint') == 1
    assert first.count('/membership.css?v=1.13.7.1d') == 1
    assert first.count('/membership.js?v=1.13.7.1d') == 1


def test_prepare_body_match_keeps_nested_manual_update_inside_full_article():
    script_path = ROOT / "scripts/prepare_membership_paywall.py"
    spec = importlib.util.spec_from_file_location("prepare_membership_nested_update", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)

    body = (
        '<div class="article-update"><p><strong>UPDATE:</strong> The child was safely located late Wednesday night, and the sheriff thanked residents who shared the alert while deputies searched the surrounding Palm City area.</p></div>'
        '<p><strong>Original report:</strong></p>'
        '<p>The sheriff requested public help locating the missing child after he was last seen leaving a senior living community, and deputies asked residents in nearby neighborhoods to check yards, cameras and common areas.</p>'
        '<p>Additional original reporting described the child, the clothing he was wearing, where he was last seen and how residents could contact deputies with information while the search remained active.</p>'
    )
    page = (
        '<div class="article-body">' + body + '</div>'
        '<aside class="newsletter-inline-slot newsletter-inline-slot--article">newsletter</aside>'
        '<div class="article-share">share</div>'
    )
    match = module.BODY_RE.search(page)
    assert match
    assert match.group(1) == body
    split = split_article_body(match.group(1))
    assert split is not None
    assert 'Original report:' in split.protected_html
    assert 'Additional original reporting' in split.protected_html



def test_one_free_article_monthly_meter_contract_is_server_signed_and_repeat_safe():
    protected = (ROOT / "supabase/functions/protected-article/index.ts").read_text()
    browser = (ROOT / "membership.js").read_text()
    css = (ROOT / "membership.css").read_text()
    helper = (ROOT / "tct_engine/membership_paywall.py").read_text()

    assert "METER_POLICY = 'one_free_article_per_month'" in protected
    assert "METER_TIME_ZONE = 'America/New_York'" in protected
    assert "Deno.env.get('TCT_METER_TOKEN_SECRET')" in protected
    assert "Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')" in protected
    assert "existingMeter?.period === period && existingMeter.slug !== slug" in protected
    assert "existingMeter.period !== period || existingMeter.slug !== slug" in protected
    assert "access: 'monthly_free'" in protected
    assert "meter_token: meterToken" in protected

    assert "const METER_STATE_KEY = 'tct_monthly_free_article_v1'" in browser
    assert "reserveMeterArticle(slug)" in browser
    assert "meter_token: reservation.meterToken || ''" in browser
    assert "data?.access === 'monthly_free'" in browser
    assert "You've read your free article this month." in browser
    assert "Continue reading Treasure Coast Today for just $1." in browser
    assert "if (headline) headline.textContent = afterRead" in browser
    assert "clearPendingMeterFor(slug)" in browser
    assert "METER_PENDING_TTL_MS = 120000" in browser
    assert "html.tct-meter-precheck .tct-member-only" in css
    assert "data-meter-status" in helper
    assert "data-paywall-headline" in helper
    assert "data-meter-reset" in helper


def test_first_free_article_moves_paywall_itself_after_all_unlocked_story_content():
    browser = (ROOT / "membership.js").read_text()
    assert "if (access === 'member') memberOnly?.remove()" in browser
    assert "setMeterPaywallState(paywall" in browser
    assert "tct-paywall-metered-after-read" in browser
    assert "Thanks for reading. Get unlimited, ad-free access" in browser
    assert "placePostReadMeterAfterStory(paywall)" in browser
    assert "#tct-protected-content.is-unlocked" in browser
    assert "memberOnly.contains(unlockedTarget)" in browser
    assert "insertBefore(unlockedTarget, memberOnly)" in browser
    assert "newsletter-inline-slot--article" in browser
    assert "article-share" in browser
    assert "boundary.parentElement.insertBefore(paywall, boundary)" in browser
    assert "boundary.parentElement.insertBefore(memberOnly, boundary)" not in browser
    assert "if (placed) memberOnly?.remove()" in browser


def test_meter_asset_version_busts_cache_for_post_read_card_placement_fix():
    helper = (ROOT / "tct_engine/membership_paywall.py").read_text()
    assert 'MEMBERSHIP_ASSET_VERSION = "1.13.7.1d"' in helper


def test_monthly_free_article_inserts_compact_kit_form_after_second_paragraph_only_for_long_stories():
    browser = (ROOT / "membership.js").read_text()

    assert "const MONTHLY_FREE_NEWSLETTER_UID = '2865b8d821'" in browser
    assert "const MONTHLY_FREE_NEWSLETTER_SRC = 'https://treasure-coast-today.kit.com/2865b8d821/index.js'" in browser
    assert "function placeMonthlyFreeNewsletter()" in browser
    assert "const paragraphs = Array.from(articleBody.children).filter(node => node.tagName === 'P')" in browser
    assert "if (paragraphs.length <= 4) return false" in browser
    assert "const secondParagraph = paragraphs[1]" in browser
    assert "while (secondParagraph.nextSibling) continuation.appendChild(secondParagraph.nextSibling)" in browser
    assert "newsletter-inline-slot newsletter-inline-slot--monthly-free" in browser
    assert "script.setAttribute('data-uid', MONTHLY_FREE_NEWSLETTER_UID)" in browser
    assert "script.src = MONTHLY_FREE_NEWSLETTER_SRC" in browser
    # One definition plus one invocation: the new form is tied only to the
    # successful monthly-free unlock path, never normal member access/paywall views.
    assert browser.count("placeMonthlyFreeNewsletter()") == 2
    monthly_free = browser.index("data?.access === 'monthly_free'")
    invocation = browser.rindex("placeMonthlyFreeNewsletter()")
    assert invocation > monthly_free


def test_update_workflow_auto_repairs_legacy_protected_article_endpoint_for_meter_launch():
    workflow = (ROOT / ".github/workflows/update.yml").read_text()
    assert "Probe monthly free-article meter capability" in workflow
    assert 'json={"action": "meter-capability"}' in workflow
    assert "one_free_article_per_month" in workflow
    assert "Deploy monthly free-article protected endpoint" in workflow
    assert "supabase functions deploy protected-article --use-api" in workflow
