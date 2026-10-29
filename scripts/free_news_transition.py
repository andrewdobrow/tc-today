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
import sys
from urllib.parse import urlparse

# This is invoked directly as `python scripts/free_news_transition.py` by the
# existing Update workflow. Python otherwise puts scripts/ (not the repository
# root) on sys.path, making `from scripts.*` fail in production although
# pytest imports succeed. Align direct execution with the other TCT CLI scripts.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_membership_paywall import (
    ACTUAL_PAYWALL_MARKER_RE,
    PAYWALLED_RE,
    _rehydrate_legacy_body,
    _restore_free_article_schema,
)

PAYMENT_PATTERN = re.compile(r"^https://(?:buy|checkout|donate)\.stripe\.com/[A-Za-z0-9/_-]+(?:\?[^\s]*)?$")
CUSTOMER_SERVICE = "hello@treasurecoast.today"

# A tiny flat vector heart; never an OS-dependent red/color emoji.
DONATE_HEART_SVG = '<svg class="tct-donate-heart" viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true" focusable="false"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41 .81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>'
LEGACY_DONATE_HEART = '<span class="tct-donate-heart" aria-hidden="true">&#9829;</span>'


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



# Ad loading cannot start until the browser has determined whether a returning
# paid reader is entitled.  A body class alone is too late for Mediavine's
# async wrapper, which is emitted before membership.js verifies the session.
MEDIAVINE_SCRIPT_RE = re.compile(
    r'<script\b[^>]*\bsrc=["\'](?P<src>(?:https?:)?//scripts\.mediavine\.com/tags/[a-z0-9-]+\.js)["\'][^>]*>\s*</script>',
    re.I | re.S,
)
MEDIAVINE_GATE_TAG_RE = re.compile(
    r'<script\b[^>]*\bdata-tct-mediavine-member-gate\b[^>]*>\s*</script>',
    re.I | re.S,
)


def _gate_mediavine_for_paid_members(text: str) -> str:
    """Replace the eager Mediavine wrapper with an entitlement-aware loader.

    Anonymous readers still load ads immediately. Signed-in readers defer
    loading until membership.js gets a server-verified subscription result.
    The existing Mediavine URL is reused unmodified.
    """
    if MEDIAVINE_GATE_TAG_RE.search(text):
        # Generated pages may carry an older gate as well as a reinserted eager
        # script; never let an eager tag bypass a previous gate.
        return MEDIAVINE_SCRIPT_RE.sub("", text)
    matches = list(MEDIAVINE_SCRIPT_RE.finditer(text))
    if not matches:
        return text
    if len(matches) != 1:
        raise RuntimeError("Expected precisely one Mediavine loader per page")
    script_url = html.escape(matches[0].group("src"), quote=True)
    replacement = (
        '<script data-tct-mediavine-member-gate '
        f'data-tct-mediavine-src="{script_url}" '
        'src="/member-ad-gate.js?v=20261029a"></script>'
    )
    return MEDIAVINE_SCRIPT_RE.sub(lambda _: replacement, text, count=1)


def _rewrite_chrome(text: str, page_name: str) -> str:
    text = _gate_mediavine_for_paid_members(text)
    # Force the patched membership client on every retained page after rollout.
    text = re.sub(
        r'(/membership\\.js\\?v=)[a-zA-Z0-9._-]+',
        r'\\g<1>1.13.9.115',
        text,
    )
    # Replace subscription sales with donations, but do not remove the existing
    # Sign in / account links. Paid readers still need to verify their ad-free
    # entitlement and manage their already-paid subscriptions.
    text = re.sub(
        r'<a\b(?=[^>]*class="[^"]*\bmembership-subscribe-btn\b)[^>]*>.*?</a>',
        '<a href="/donate.html" class="support-btn membership-subscribe-btn tct-donate-header" aria-label="Support Treasure Coast Today">' +
        DONATE_HEART_SVG + ' <span class="membership-subscribe-label">Support TCT</span></a>',
        text, flags=re.I | re.S,
    )
    # If a legacy site/page uses an Advertise primary CTA, route it to the Support TCT donation page.
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
    # Keep member entitlement scripts so existing paying readers remain ad-free
    # through the end of their already-paid periods. Only remove meter prepaint,
    # which is obsolete when article access becomes universally free.
    if page_name != "subscribe.html":
        member_prepaint = (
            '<script data-tct-member-prepaint>'
            '(function(){try{if(localStorage.getItem("tct_member_entitled_hint")!=="1")return;'
            'var apply=function(){if(!document.body)return false;'
            'document.body.classList.add("mv-no-ads");return true;};'
            'if(!apply()){var observer=new MutationObserver(function(){if(apply())observer.disconnect();});'
            'observer.observe(document.documentElement,{childList:true});}'
            '}catch(_e){}})();'
            '</script>'
        )
        text = re.sub(
            r'<script\b[^>]*data-tct-member-prepaint[^>]*>.*?</script>',
            lambda _: member_prepaint, text, count=1, flags=re.I | re.S,
        )
        text = text.replace(' class="footer-column footer-connect footer-membership-ask"',
                            ' class="footer-column footer-connect footer-donation-ask"')
    text = text.replace('<a href="/subscribe.html">Membership</a>', f'<a href="/donate.html">{DONATE_HEART_SVG} Donate</a>')
    text = re.sub(
        r'<a\b(?=[^>]*class="[^"]*\bfooter-subscribe-cta\b)[^>]*>.*?</a>',
        f'<a class="footer-subscribe-cta" href="/donate.html"><span>{DONATE_HEART_SVG} Donate to local news</span>'
        '<small>Every story stays free</small></a>', text, flags=re.I | re.S,
    )
    text = text.replace('Unlimited articles. Help fund independent Treasure Coast reporting.',
                        'Every article is free. Your voluntary support helps fund independent local reporting.')
    # Upgrade existing free-news pages, including inline footer links which
    # no longer contain their original /subscribe.html href.
    text = text.replace(LEGACY_DONATE_HEART, DONATE_HEART_SVG)
    if not re.search(r'href="/donation-model\.css(?:\?v=[^"]*)?"', text) and "</head>" in text:
        text = text.replace("</head>", '  <link rel="stylesheet" href="/donation-model.css?v=20261028d">\n</head>', 1)
    text = re.sub(r'href="/donation-model\.css(?:\?v=[^"]*)?"',
                  'href="/donation-model.css?v=20261028d"', text)
    return text


def _rewrite_home_support(text: str) -> str:
    pattern = re.compile(
        r'<a\b(?=[^>]*\bdata-support-card="true")[^>]*>.*?</a>',
        re.I | re.S,
    )
    replacement = f"""<a href="/donate.html" class="grid-card tct-membership-card tct-donation-card" data-cat="all" data-support-card="true" aria-label="Donate to Treasure Coast Today">
        <div class="tct-membership-card-inner">
          <span class="tct-membership-kicker">Reader-supported journalism</span>
          <h2 class="tct-membership-headline">Local news. Free for everyone.</h2>
          <p class="tct-membership-copy">No paywall. Independent reporting for Martin, St. Lucie and Indian River counties, supported by readers and advertisers.</p>
          <span class="tct-membership-options" aria-hidden="true"><span>Read for free</span><span>Donate what you choose</span><span>Stay informed</span></span>
          <span class="tct-membership-cta">{DONATE_HEART_SVG} Donate to support the newsroom <b>&rarr;</b></span>
        </div>
      </a>"""
    return pattern.sub(replacement, text, count=1)


def _rewrite_privacy(text: str) -> str:
    """Publish accurate public-access, donations, legacy accounts, and ad disclosures.

    The Mediavine Programmatic Advertising (Ver 1.1) section is contractual
    supplied copy. Do not change any of its paragraphs or required heading.
    """
    text = re.sub(
        r'Last updated:\s*[^<]+',
        'Last updated: October 28, 2026', text, count=1,
    )
    # Focused unit-test snippets do not contain the full policy. Enforce all
    # expected disclosures against actual full published pages, not tiny inputs.
    full_policy = '<div class="policy-body">' in text
    note = """<h2>Free articles and voluntary reader contributions</h2>
        <p>Treasure Coast Today's news articles are freely available without a subscription, sign-in or contribution. Readers may optionally contribute to support our reporting. TCT is operated by Treasure Coast Today LLC, a for-profit business and not a tax-exempt charity; contributions are not tax-deductible charitable donations and do not purchase ad-free access, subscription rights or editorial influence.</p>
        <p>Our one-time, choose-your-own-amount contribution checkout is hosted by Stripe. We may receive transaction amounts, payment status, dates, Stripe identifiers, and contact details supplied for confirmations or receipts. Stripe handles payment credentials; TCT does not collect or store full card numbers. We retain payment records when needed for customer support, accounting, fraud prevention or applicable legal obligations.</p>
        <p>Existing paid subscriptions and billing records continue to be handled through Stripe and Supabase while previously purchased periods conclude. Eligible subscribers may sign in to receive the ad-free website and iPhone app experience already included in their paid terms. New articles do not require paid access. We display clearly labeled sponsorships and advertising, including Mediavine on the website and Google AdMob in the iPhone app, as described below.</p>
        """

    # Current site can be rebuilt from this script during the regular Update
    # workflow. Keep Apple StoreKit disclosures in the generated policy.
    stripe_description = "<p>Our one-time, choose-your-own-amount contribution checkout is hosted by Stripe. We may receive transaction amounts, payment status, dates, Stripe identifiers, and contact details supplied for confirmations or receipts. Stripe handles payment credentials; TCT does not collect or store full card numbers. We retain payment records when needed for customer support, accounting, fraud prevention or applicable legal obligations.</p>"
    apple_disclosure = "<!-- tct-ios-storekit-tips-20261028 -->\n        <p><strong>Optional tips in our iPhone app.</strong> In the iPhone app, optional one-time, repeatable tips are purchased only through Apple's In-App Purchase (StoreKit), not through Stripe. Apple processes the payment and associated billing details under its own terms and <a href=\"https://www.apple.com/legal/privacy/\">privacy policy</a>. TCT may receive limited purchase reporting, such as transaction amounts, dates, and product identifiers, through App Store Connect; our app verifies and completes purchases through StoreKit. TCT does not collect or store full payment card numbers for Apple purchases. Tips are voluntary and do not unlock articles or features, remove advertisements, create a subscription, or confer editorial influence. No TCT account is needed to leave an in-app tip.</p>"
    if "<!-- tct-ios-storekit-tips-20261028 -->" not in text and stripe_description in text:
        text = text.replace(stripe_description, stripe_description + "\n        " + apple_disclosure, 1)
    if "<h2>Free articles and voluntary reader contributions</h2>" not in text:
        marker = "<h2>Information we collect</h2>"
        if marker not in text:
            raise RuntimeError("Privacy policy: information-collection section missing")
        text = text.replace(marker, note + marker, 1)
    updates = (
        (
            "We collect information needed to operate the website and app, provide memberships and news alerts, understand readership, and respond to messages:",
            "We collect information needed to operate the website and app, manage optional contributions and pre-existing paid accounts, deliver requested news alerts and emails, understand readership, and respond to messages:",
        ),
        (
            "<li><strong>Membership account information.</strong> If you purchase or use a Treasure Coast Today membership, we use your email address to create or link your membership identity, send secure sign-in links and verify access.</li>",
            "<li><strong>Existing subscriber account information.</strong> For previously purchased memberships, we use the associated email address and account identifiers to send sign-in links, verify remaining ad-free benefits and provide access to billing management. No account is required to read public articles.</li>",
        ),
        (
            "<li><strong>Payment information.</strong> Membership payments are processed by Stripe. Treasure Coast Today does not receive or store your full card number. We receive identifiers and subscription status needed to provide and manage membership access.</li>",
            "<li><strong>Payment and contribution information.</strong> Stripe processes voluntary reader payments and historical subscriptions. We receive related confirmations, amounts, dates, customer contact information when provided, Stripe payment identifiers and existing subscription status. We do not receive or store complete payment card numbers.</li>",
        ),
        (
            "Public headlines, stories and event listings can be read in the iPhone app without creating a membership account.",
            "Headlines, news articles and event listings are available without purchasing a membership. Older installed app versions may temporarily retain legacy article-access screens until readers update.",
        ),
        (
            "<li><strong>App authentication and membership access.</strong> If you sign in, we process your email address and authentication/session credentials to verify access to subscriber content. The app stores session credentials in iOS Keychain. Membership status is verified by our services; your payment card is handled by Stripe, not by the iPhone app.</li>",
            "<li><strong>App authentication and remaining paid benefits.</strong> Existing paid readers who sign in provide an email address and session credentials so the app can verify their remaining ad-free entitlement. Credentials are stored in iOS Keychain. Stripe handles historical website subscription payments; optional iPhone tips are processed by Apple. No login is required for ordinary free news reading.</li>",
        ),
        (
            "<li><strong>App preferences and reading access.</strong> The app locally stores certain settings, notification-topic preferences and information needed to recognize its monthly free-article allowance. These settings help the app remember your choices and enforce article access rules.</li>",
            "<li><strong>App preferences and legacy reading limits.</strong> The app locally stores settings and notification preferences. Older versions may also retain a historical monthly article-meter record on the device; new public-access versions do not use a paid reading allowance to unlock ordinary news articles.</li>",
        ),
        (
            "We use the information described above to operate and improve the website and app, deliver requested push notifications, provide membership access, process and manage subscriptions, send secure authentication messages, understand readership, and respond to messages you send us.",
            "We use the information described above to operate and improve the website and app, deliver requested push notifications and newsletters, process optional contributions, manage pre-existing subscriptions and their ad-free benefits, send secure account messages, understand readership, and respond to messages you send us.",
        ),
        (
            "<li><strong>Stripe</strong> for membership checkout, recurring billing and billing-account management.</li>",
            "<li><strong>Stripe</strong> for optional one-time contributions, receipts, and management of historical membership billing.</li>",
        ),
        (
            "<li><strong>Supabase</strong> for membership authentication, account records, subscription entitlement and protected article delivery.</li>",
            "<li><strong>Supabase</strong> for remaining subscriber authentication, account records, legacy billing status, article services and site functions.</li>",
        ),
        (
            "<li><strong>Resend</strong> as an email-delivery provider for secure membership sign-in messages.</li>",
            "<li><strong>Resend</strong> as an email-delivery provider for secure existing-account sign-in messages.</li>",
        ),
        (
            "We retain information for as long as reasonably needed for the purposes described above, including to maintain memberships and comply with applicable legal, accounting, and security obligations.",
            "We retain information as reasonably necessary to administer remaining paid benefits, optional contributions, requested services and applicable legal, accounting, security and recordkeeping obligations.",
        ),
    )
    for old, new in updates:
        if old in text:
            text = text.replace(old, new, 1)
        elif new not in text and full_policy:
            raise RuntimeError("Privacy migration requires an updated source template: " + old[:70])
    if "<strong>Kit</strong>" not in text:
        match = "<li><strong>Resend</strong> as an email-delivery provider for secure existing-account sign-in messages.</li>"
        text = text.replace(
            match, match + '\n          <li><strong>Kit</strong> for readers who voluntarily subscribe to the Morning Brief email newsletter; readers may unsubscribe through the links in those emails.</li>'
            + '\n          <li><strong>Formspree</strong> for information submitted through advertising inquiry forms, such as a contact name, company and message.</li>',
            1,
        )

    # Update pre-existing policy text and append StoreKit payment/service entries
    # without altering the contractual Mediavine section below.
    older_app_payment = "<li><strong>App authentication and remaining paid benefits.</strong> Existing paid readers who sign in provide an email address and session credentials so the app can verify their remaining ad-free entitlement. Credentials are stored in iOS Keychain. Stripe, not the iPhone app, processes payment details. No login is required for ordinary free news reading.</li>"
    updated_app_payment = "<li><strong>App authentication and remaining paid benefits.</strong> Existing paid readers who sign in provide an email address and session credentials so the app can verify their remaining ad-free entitlement. Credentials are stored in iOS Keychain. Stripe handles historical website subscription payments; optional iPhone tips are processed by Apple. No login is required for ordinary free news reading.</li>"
    if older_app_payment in text:
        text = text.replace(older_app_payment, updated_app_payment, 1)
    payment_entry = "<li><strong>Payment and contribution information.</strong> Stripe processes voluntary reader payments and historical subscriptions. We receive related confirmations, amounts, dates, customer contact information when provided, Stripe payment identifiers and existing subscription status. We do not receive or store complete payment card numbers.</li>"
    apple_payment_entry = "<li><strong>Apple In-App Purchase.</strong> Apple handles optional iPhone tip payments through StoreKit. TCT may receive limited sales reporting through App Store Connect, including amounts, dates and product identifiers, but does not collect your full payment card number or require an app account for tipping.</li>"
    if apple_payment_entry not in text and payment_entry in text:
        text = text.replace(payment_entry, payment_entry + "\n          " + apple_payment_entry, 1)
    stripe_service = "<li><strong>Stripe</strong> for optional one-time contributions, receipts, and management of historical membership billing.</li>"
    apple_service = "<li><strong>Apple In-App Purchase (StoreKit)</strong> for voluntary, one-time tips offered within the iPhone app. Apple processes the purchase and provides associated transaction records. See <a href=\"https://www.apple.com/legal/privacy/\">Apple's Privacy Policy</a>.</li>"
    if apple_service not in text and stripe_service in text:
        text = text.replace(stripe_service, stripe_service + "\n          " + apple_service, 1)
    if full_policy and ("<!-- tct-ios-storekit-tips-20261028 -->" not in text
                        or apple_payment_entry not in text or apple_service not in text):
        raise RuntimeError("Privacy policy: missing Apple In-App Purchase disclosures")
    if full_policy and "<h3>Mediavine Programmatic Advertising (Ver 1.1)</h3>" not in text:
        raise RuntimeError("Required Mediavine privacy disclosure heading missing")
    return text


def _rewrite_subscription_terms(text: str) -> str:
    """Keep historical subscriber terms, but distinguish free news at cutover."""
    text = re.sub(
        r'(<p class="policy-updated">Last updated: )[^<]+',
        r'\g<1>October 27, 2026', text, count=1,
    )
    notice = (
        '<section class="policy-callout" id="tct-existing-subscription-notice">'
        '<strong>October 27, 2026: TCT is transitioning to free news.</strong> '
        'All articles are available to everyone without payment. We are closing '
        'new paid reading memberships. Subscribers who have already paid retain '
        'their ad-free benefit through the end of their paid terms; future '
        'renewals will be stopped at the billing transition. '
        'You can <a href="/subscribe.html">sign in to manage your existing '
        'billing account</a> or <a href="mailto:hello@treasurecoast.today">'
        'contact TCT</a> for confirmation of your renewal status. '
        'The terms below document previously sold memberships.'
        '</section>'
    )
    if 'id="tct-existing-subscription-notice"' not in text:
        marker = '<div class="policy-body">'
        if marker not in text:
            raise RuntimeError("Subscription terms: policy body not found")
        text = text.replace(marker, marker + "\n        " + notice, 1)
    updates = (
        ("<h2>Membership plans and pricing</h2>",
         "<h2>Historical membership plans and pricing</h2>"),
        ("The advertised introductory offer is $1",
         "The former introductory offer was $1"),
        ("The introductory offer does not repeat each month.",
         "The introductory offer did not repeat each month."),
        ("The annual plan costs $49 per year and renews annually until canceled.",
         "The former annual plan cost $49 per year and was sold with automatic renewal unless canceled."),
        ("Both plans are recurring subscriptions. By subscribing, you authorize Stripe",
         "Historically, both plans were sold as recurring subscriptions. When you subscribed, you authorized Stripe"),
        ("An active membership provides unlimited access to TCT subscriber stories and an ad-free reading experience on supported TCT services while your account is entitled.",
         "Articles are now free for everyone. An existing paid membership continues to provide the previously promised ad-free experience on supported TCT services through the end of the already-paid period while the subscriber remains entitled."),
    )
    for old, new in updates:
        if old in text:
            text = text.replace(old, new, 1)
        elif new not in text:
            raise RuntimeError("Historical membership terms changed unexpectedly: " + old[:70])
    text = text.replace(
        "Please review these terms and the <a href=\"/privacy.html\">Privacy Policy</a> before subscribing.",
        "These terms remain available for previous subscribers. Read our <a href=\"/privacy.html\">Privacy Policy</a> for current reader-support and advertising information.",
        1,
    )
    return text


def _rewrite_ownership(text: str) -> str:
    text = text.replace(
        "Treasure Coast Today is supported by reader memberships, advertising, and clearly labeled sponsored content and partnerships, with additional funding from its owner.",
        "Treasure Coast Today is funded by advertising, clearly labeled sponsored content and partnerships, optional reader contributions, and investment from its owner. Earlier memberships funded the site prior to its transition to free news.",
        1,
    )
    text = text.replace(
        "Reader memberships, advertising, and clearly labeled sponsorships support Treasure Coast Today. Sponsored content is identified as paid content and kept separate from independent reporting. Subscribers, advertisers, and sponsors do not determine whether or how we report on a person, business, or organization.",
        "Optional reader contributions, advertising, and clearly labeled sponsorships support Treasure Coast Today. Reader contributions to Treasure Coast Today LLC are not charitable tax-deductible donations. Sponsored content is identified as paid content and kept separate from independent reporting. Contributors, former subscribers, advertisers, and sponsors do not determine whether or how we report on a person, business, or organization.",
        1,
    )
    return text


def _rewrite_about(text: str) -> str:
    marker = "<h2>Advertise with us</h2>"
    if marker not in text:
        raise RuntimeError("About page: advertising section not found")
    if "<h2>Free news, supported by readers and advertisers</h2>" not in text:
        text = text.replace(
            marker,
            '<h2>Free news, supported by readers and advertisers</h2>'
            '<p>All Treasure Coast Today news articles are free to read. '
            'Our reporting is supported by local sponsorships, advertising and '
            'voluntary reader contributions. You never have to pay or donate '
            'to access a story. <a href="/donate.html" class="about-contact">'
            'Support TCT with a one-time contribution &rarr;</a></p>'
            '<p>Treasure Coast Today LLC is a for-profit local news business, '
            'so contributions are not charitable tax-deductible donations. '
            'Financial support never buys influence over independent coverage.</p>\n        '
            + marker,
            1,
        )
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
          <a class="tct-donate-button" href="{html.escape(payment_link, quote=True)}" rel="noopener noreferrer">{DONATE_HEART_SVG} Support TCT Today</a>
          <p class="tct-donate-disclosure">Donations are processed securely using Stripe.</p>
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
        # A few editor-authored overrides already had a complete public body
        # before this migration, but retained an old isAccessibleForFree:false
        # JSON-LD flag and paywall hasPart. Fix *metadata only* on fully
        # public stories; do not rewrite redirect shells or locked previews.
        if (path.parent == root / "articles"
                and '<div class="article-body">' in text
                and not ACTUAL_PAYWALL_MARKER_RE.search(text)):
            text = _restore_free_article_schema(text)
        text = _rewrite_chrome(text, path.name)
        if path == root / "index.html":
            text = _rewrite_home_support(text)
        if path == root / "privacy.html":
            text = _rewrite_privacy(text)
        if path == root / "subscribe.html":
            text = _close_new_subscriptions(text)
        if path == root / "subscription-terms.html":
            text = _rewrite_subscription_terms(text)
        if path == root / "ownership.html":
            text = _rewrite_ownership(text)
        if path == root / "about.html":
            text = _rewrite_about(text)
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
