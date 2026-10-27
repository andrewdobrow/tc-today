#!/usr/bin/env python3
"""Turn the published TCT site into free-access journalism with reader support.

Run only after the generator/audience build and the secure Supabase snapshot.
Never publish truncated previews when a protected body is missing. No secret,
protected-content JSON, or billing/customer data is written to the repository.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from scripts.prepare_membership_paywall import (
    ACTUAL_PAYWALL_MARKER_RE,
    PAYWALLED_RE,
    _rehydrate_legacy_body,
    _restore_free_article_schema,
)

ROOT = Path(__file__).resolve().parents[1]
PAYMENT_PATTERN = re.compile(r"^https://(?:buy|checkout)\.stripe\.com/[A-Za-z0-9/_-]+(?:\?[^\s]*)?$")
CUSTOMER_SERVICE = "hello@treasurecoast.today"


def load_snapshot(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise RuntimeError("A full Supabase protected-content snapshot is required before opening TCT articles.")
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("articles") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError("Protected-content snapshot is invalid.")
    result = {}
    for item in rows:
        if not isinstance(item, dict):
            raise RuntimeError("Unexpected protected-content snapshot row.")
        slug = str(item.get("slug") or "")
        body = str(item.get("protected_body") or "")
        if slug and body:
            if slug in result:
                raise RuntimeError(f"Duplicate protected snapshot slug: {slug}")
            result[slug] = body
    return result


def restore_article(text: str, slug: str, protected: dict[str, str]) -> str:
    if not ACTUAL_PAYWALL_MARKER_RE.search(text):
        return text
    match = PAYWALLED_RE.search(text)
    if not match:
        raise RuntimeError(f"Cannot safely locate preview/protected-content boundary: {slug}")
    if slug not in protected:
        raise RuntimeError(f"Protected body missing from secure snapshot: {slug}")
    full_body = _rehydrate_legacy_body(match.group(1), protected[slug])
    if not full_body.strip() or "<p" not in full_body.lower():
        raise RuntimeError(f"Invalid full story body in secure snapshot: {slug}")
    page = text[:match.start()] + '<div class="article-body">' + full_body + '</div>' + text[match.end():]
    if ACTUAL_PAYWALL_MARKER_RE.search(page):
        raise RuntimeError(f"Unexpected second paywall remains: {slug}")
    return _restore_free_article_schema(page)


def _rewrite_chrome(text: str, page_name: str) -> str:
    # Remove only the sales/header anchors; preserve the email newsletter link.
    text = re.sub(
        r'<a\b(?=[^>]*class="[^"]*\bmembership-subscribe-btn\b)[^>]*>.*?</a>'
        r'(?:\s*<a\b(?=[^>]*class="[^"]*\bmembership-header-(?:signin|welcome)\b)[^>]*>.*?</a>){0,2}',
        '<a href="/donate.html" class="support-btn membership-subscribe-btn tct-donate-header" aria-label="Donate to support Treasure Coast Today">'
        '<span class="membership-subscribe-label">Donate</span></a>',
        text, flags=re.I | re.S
    )
    text = re.sub(r'<a\b(?=[^>]*class="[^"]*\bmembership-header-(?:signin|welcome)\b)[^>]*>.*?</a>', "", text, flags=re.I | re.S)
    # If a legacy site/page uses an Advertise primary CTA, make it Donate.
    text = re.sub(r'(<a\b(?=[^>]*class="[^"]*\bsupport-btn\b)[^>]*href=")/advertise\.html(")', r'\1/donate.html\2', text, flags=re.I)
    # The primary desktop nav gets Advertise immediately after Events. Mobile
    # retains a discoverable Advertise link in its hamburger drawer.
    def nav_update(match: re.Match) -> str:
        nav = match.group(0)
        nav = re.sub(r'\s*<a\b(?=[^>]*href="/advertise\.html")(?=[^>]*class="[^"]*\bnav-section-link\b)[^>]*>.*?</a>', '', nav, flags=re.I | re.S)
        if 'href="/advertise.html"' not in nav:
            nav, count = re.subn(
                r'(<a\b[^>]*href="/events\.html"[^>]*>Events</a>)',
                r'\1\n        <a href="/advertise.html" class="cat-btn"' +
                (' aria-current="page" class="cat-btn"' if False else '') +
                ' style="text-decoration:none">Advertise</a>',
                nav, count=1, flags=re.I,
            )
            if count != 1:
                raise RuntimeError(f"Desktop navigation lacks Events on {page_name}")
        if page_name == "advertise.html":
            nav = nav.replace('href="/advertise.html" class="cat-btn"', 'href="/advertise.html" class="cat-btn active" aria-current="page"')
            nav = nav.replace('class="cat-btn nav-sections-toggle active"', 'class="cat-btn nav-sections-toggle"')
        return nav
    text = re.sub(r'<nav\b(?=[^>]*class="[^"]*\bcategory-nav--primary\b)[^>]*>.*?</nav>', nav_update, text, count=1, flags=re.I | re.S)
    # Remove the automatic hide-ads member prepaint script and membership meter
    # from the new public site; keep membership account tools on legacy billing.
    if page_name != "subscribe.html":
        text = re.sub(r'\s*<script\b[^>]*data-tct-member-prepaint[^>]*>.*?</script>', '', text, flags=re.I | re.S)
        text = re.sub(r'\s*<link\b[^>]*href="/membership\.css[^"]*"[^>]*>', '', text, flags=re.I)
        text = re.sub(r'\s*<script\b[^>]*src="/membership-config\.js"[^>]*></script>', '', text, flags=re.I)
        text = re.sub(r'\s*<script\b[^>]*src="/membership\.js[^"]*"[^>]*></script>', '', text, flags=re.I)
        text = text.replace(' class="footer-column footer-connect footer-membership-ask"', ' class="footer-column footer-connect footer-donation-ask"')
    text = text.replace('<a href="/subscribe.html">Membership</a>', '<a href="/donate.html">Donate</a>')
    text = re.sub(
        r'<a\b(?=[^>]*class="[^"]*\bfooter-subscribe-cta\b)[^>]*>.*?</a>',
        '<a class="footer-subscribe-cta" href="/donate.html"><span>Donate to local news</span>'
        '<small>Every story stays free</small></a>', text, flags=re.I | re.S,
    )
    text = text.replace('Unlimited articles. Help fund independent Treasure Coast reporting.',
                        'Every article is free. Your voluntary support helps fund independent local reporting.')
    if 'href="/donation-model.css"' not in text and "</head>" in text:
        text = text.replace("</head>", '  <link rel="stylesheet" href="/donation-model.css">\n</head>', 1)
    return text


def _rewrite_home_support(text: str) -> str:
    pattern = re.compile(
        r'<a\b(?=[^>]*\bdata-support-card="true")[^>]*>.*?</a>',
        re.I | re.S,
    )
    replacement = """<a href="/donate.html" class="grid-card tct-membership-card tct-donation-card" data-cat="all" data-support-card="true" aria-label="Donate to Treasure Coast Today">
        <div class="tct-membership-card-inner">
          <span class="tct-membership-kicker">Reader-supported journalism</span>
          <h2 class="tct-membership-headline">Local news. Free for everyone.</h2>
          <p class="tct-membership-copy">No paywall. Independent reporting for Martin, St. Lucie and Indian River counties, supported by readers and advertisers.</p>
          <span class="tct-membership-options" aria-hidden="true"><span>Read for free</span><span>Donate what you choose</span><span>Stay informed</span></span>
          <span class="tct-membership-cta">Support the newsroom <b>&rarr;</b></span>
        </div>
      </a>"""
    return pattern.sub(replacement, text, count=1)


def _rewrite_privacy(text: str) -> str:
    text = re.sub(r'Last updated:\s*[^<]+', 'Last updated: October 27, 2026', text, count=1)
    note = """<h2>Donations and free access</h2>
        <p>Treasure Coast Today's news articles are free to read. Readers may choose to make voluntary payments to support our for-profit newsroom. Stripe hosts donation checkout and processes payment details. We may receive payment confirmation, amount, date and the contact information you choose to provide for receipts and accounting. No paid account or donation is required to read stories.</p>
        <p>We may display advertising and clearly labeled sponsored content. Our advertising partners, including Mediavine, may use cookies and similar technologies as described below. Existing subscription records may be retained for billing, cancellation and legal obligations; new reading access is not based on subscription status.</p>
        """
    if "<h2>Donations and free access</h2>" not in text:
        text = text.replace("<h2>Information we collect</h2>", note + "<h2>Information we collect</h2>", 1)
    return text


def _rewrite_subscription_terms(text: str) -> str:
    message = ('<p><strong>October 27, 2026 update:</strong> TCT is moving to free news '
               'supported by voluntary reader donations and advertisements. '
               'These historical terms continue to govern earlier paid memberships, '
               'renewals, cancellation, and any remaining billing obligations. '
               'New paid reading memberships are not being offered.</p>')
    if 'historical terms continue to govern' not in text:
        text = text.replace('<div class="policy-body">', '<div class="policy-body">\n' + message, 1)
    return text


def _close_new_subscriptions(text: str) -> str:
    text = re.sub(r"<title>.*?</title>", "<title>Manage Existing Membership | Treasure Coast Today</title>", text, count=1, flags=re.I | re.S)
    text = re.sub(r'(<meta name="description" content=")[^"]*', r'\g<1>Manage an existing Treasure Coast Today billing account. New paid reading memberships are closed; all local news is free.', text, count=1)
    text = re.sub(r'(<meta\s+id="membership-robots"\s+name="robots"\s+content=")[^"]*', r'\g<1>noindex,follow', text, count=1)
    if 'id="tct-legacy-membership-notice"' not in text:
        notice = ('<section id="tct-legacy-membership-notice" role="status">'
                  '<h1>All TCT news is now free.</h1>'
                  '<p>We are no longer offering new paid reading memberships. Existing subscribers can still sign in to review their account and manage billing. If you would like to help fund independent reporting, <a href="/donate.html">make a voluntary donation</a>.</p>'
                  '<p>For cancellation or billing support, email <a href="mailto:hello@treasurecoast.today">hello@treasurecoast.today</a>.</p>'
                  '</section>')
        text = text.replace('<main class="membership-landing">', '<main class="membership-landing">\n' + notice, 1)
    if '<body class="membership-page' in text:
        text = text.replace('<body class="membership-page', '<body class="tct-subscriptions-closed membership-page', 1)
    return text


def create_donation_page(root: Path, payment_link: str) -> None:
    source = (root / "about.html").read_text(encoding="utf-8")
    source = _rewrite_chrome(source, "donate.html")
    title = "Donate to Treasure Coast Today | Support Free Local News"
    desc = "Keep independent Treasure Coast reporting free and accessible. Make a voluntary one-time donation through Stripe."
    source = re.sub(r"<title>.*?</title>", f"<title>{html.escape(title)}</title>", source, count=1, flags=re.I | re.S)
    source = re.sub(r'(<meta name="description" content=")[^"]*', r'\g<1>' + html.escape(desc, quote=True), source, count=1)
    source = re.sub(r'(<link rel="canonical" href=")[^"]*', r'\g<1>https://treasurecoast.today/donate.html', source, count=1)
    source = re.sub(r'(<meta property="og:url" content=")[^"]*', r'\g<1>https://treasurecoast.today/donate.html', source, count=1)
    source = re.sub(r'(<meta property="og:title" content=")[^"]*', r'\g<1>' + html.escape(title, quote=True), source, count=1)
    main = f'''<main class="tct-donate-page">
      <div class="tct-donate-content">
        <span class="tct-donate-eyebrow">Support independent local reporting</span>
        <h1>Local news should be free for everyone.</h1>
        <p class="tct-donate-lead">Treasure Coast Today covers Martin, St. Lucie and Indian River counties without a paywall. If our reporting matters to you, help keep it going.</p>
        <div class="tct-donate-panel">
          <h2>Make a donation</h2>
          <p>Choose your own amount on Stripe's secure checkout. Contributions are voluntary, and you never have to donate to read a story.</p>
          <a class="tct-donate-button" href="{html.escape(payment_link, quote=True)}" rel="noopener noreferrer">Donate securely with Stripe</a>
          <p class="tct-donate-disclosure">Treasure Coast Today LLC is a for-profit business, not a tax-exempt charity. Contributions are not tax-deductible charitable donations. Payment processing is handled by Stripe.</p>
        </div>
        <p class="tct-donate-secondary">Prefer to support us as a local business? <a href="/advertise.html">Explore advertising and sponsorships</a>.</p>
      </div>
    </main>'''
    if not re.search(r"<main\b[^>]*>.*?</main>", source, flags=re.I | re.S):
        raise RuntimeError("Cannot build donation page: about.html main region is missing")
    source = re.sub(r"<main\b[^>]*>.*?</main>", lambda _: main, source, count=1, flags=re.I | re.S)
    (root / "donate.html").write_text(source, encoding="utf-8")


def transition(root: Path, snapshot_path: Path, payment_link: str) -> dict:
    if not PAYMENT_PATTERN.fullmatch(payment_link):
        raise RuntimeError("Set a genuine Stripe-hosted donation Payment Link in TCT_DONATION_PAYMENT_LINK; do not use a placeholder.")
    # Snapshot must be validated *before* modifying any file. If there are
    # protected pages, an absent body aborts before committing/deploying.
    snapshot = load_snapshot(snapshot_path)
    paths = sorted(root.rglob("*.html"))
    article_updates = {}
    for path in paths:
        if path.parent != root / "articles":
            continue
        page = path.read_text(encoding="utf-8", errors="ignore")
        if ACTUAL_PAYWALL_MARKER_RE.search(page):
            article_updates[path] = restore_article(page, path.stem, snapshot)
    updated = 0
    for path in paths:
        original = path.read_text(encoding="utf-8", errors="ignore")
        text = article_updates.get(path, original)
        text = _rewrite_chrome(text, path.name)
        if path == root / "index.html":
            text = _rewrite_home_support(text)
        if path == root / "privacy.html":
            text = _rewrite_privacy(text)
        if path == root / "subscribe.html":
            text = _close_new_subscriptions(text)
        if path == root / "subscription-terms.html":
            text = _rewrite_subscription_terms(text)
        if text != original:
            path.write_text(text, encoding="utf-8")
            updated += 1
    create_donation_page(root, payment_link)
    # Scan after output generation and fail closed rather than deploying stale teasers.
    locked = []
    for path in (root / "articles").glob("*.html"):
        if ACTUAL_PAYWALL_MARKER_RE.search(path.read_text(encoding="utf-8", errors="ignore")):
            locked.append(path.name)
    if locked:
        raise RuntimeError(f"Paywalls survive public migration: {locked[:6]}")
    return {"rehydrated": len(article_updates), "updated_pages": updated, "total_html": len(paths)}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--payment-link", required=True)
    args = p.parse_args()
    print(json.dumps(transition(args.root.resolve(), args.snapshot, args.payment_link), indent=2))
