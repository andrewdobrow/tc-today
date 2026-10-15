#!/usr/bin/env python3
"""Step 1D: add a standalone TCT subscription-terms page and link it on membership page.

Run at root of tc-today. No API, Supabase, Stripe, or iOS files are modified.
All sources are read and every anchor validated before writing any changes.
"""
from pathlib import Path
import re
import sys

ROOT = Path.cwd()
SUBSCRIBE = ROOT / 'subscribe.html'
PRIVACY = ROOT / 'privacy.html'
TERMS = ROOT / 'subscription-terms.html'

TERMS_MAIN = '''  <main>
    <div class="policy-wrap">
      <span class="policy-eyebrow">Treasure Coast Today Membership</span>
      <h1 class="policy-headline">Subscription Terms</h1>
      <p class="policy-updated">Last updated: October 13, 2026</p>
      <div class="policy-body">
        <p>These terms apply to paid Treasure Coast Today (TCT) memberships purchased through our website and accessed through the website or iPhone app. Treasure Coast Today is operated by Treasure Coast Today LLC, a Florida limited liability company. Please review these terms and the <a href="/privacy.html">Privacy Policy</a> before subscribing.</p>

        <h2>Membership plans and pricing</h2>
        <p><strong>Monthly membership:</strong> The advertised introductory offer is $1 for the first month of an eligible new monthly subscription, followed by $4.99 per month until canceled. The introductory offer does not repeat each month. Special promotional offers may have different conditions, which will be disclosed at checkout.</p>
        <p><strong>Annual membership:</strong> The annual plan costs $49 per year and renews annually until canceled. It includes the same membership reading benefits as the monthly plan.</p>
        <p>All prices are in U.S. dollars. Applicable taxes, any discounts and the total amount due are shown at checkout. Your Stripe checkout confirmation provides the payment amount and recurring billing details.</p>

        <h2>Automatic renewal and payments</h2>
        <p>Both plans are recurring subscriptions. By subscribing, you authorize Stripe, our payment processor, to charge your selected payment method when your plan begins and again on each renewal date unless you cancel before the next renewal. The monthly promotional price applies only to the specified introductory period; subsequent charges use the standard monthly rate unless a different offer is explicitly shown at checkout.</p>
        <p>Stripe processes payments and maintains your billing details. Treasure Coast Today does not store your complete payment card number. If a payment fails or a subscription is no longer active, paid reading access may be interrupted.</p>

        <h2>How to cancel your subscription</h2>
        <p><strong>You may cancel at any time.</strong> Sign in at <a href="/subscribe.html">treasurecoast.today/subscribe.html</a> using your subscription email, open <strong>Manage billing</strong>, and cancel through the secure Stripe billing portal. In the iPhone app, signed-in members can choose <strong>Manage or Cancel Subscription</strong> to open website account management.</p>
        <p>Ordinary subscription cancellation prevents the next renewal charge. Your TCT account remains available, and paid access continues through the end of the current paid billing period. Cancel before your next renewal date to avoid the next recurring charge. You may also <a href="/contact.html">contact us</a> for billing assistance.</p>

        <h2>Refunds and unused subscription time</h2>
        <p>Payments for subscription periods that have already begun are generally nonrefundable. We do not automatically issue partial or prorated refunds for unused time after cancellation, except when required by applicable law or when Treasure Coast Today expressly approves an exception. If you believe a charge was made in error, was duplicated, or requires attention, contact <a href="mailto:hello@treasurecoast.today">hello@treasurecoast.today</a>.</p>

        <h2>Canceling a subscription versus deleting an account</h2>
        <p><strong>Cancel Subscription</strong> stops future subscription renewals while preserving your TCT account and paid access through the end of the paid billing period.</p>
        <p><strong>Delete Account</strong> is a separate permanent action offered in the iPhone app. Deleting your account immediately cancels associated subscription renewals, removes your TCT login and membership access, and does not automatically refund unused subscription time. Certain payment and transaction records may be retained when legally required. Do not delete your account if you only want to stop future renewals.</p>

        <h2>Access and member benefits</h2>
        <p>An active membership provides unlimited access to TCT subscriber stories and an ad-free reading experience on supported TCT services while your account is entitled. You can use the same subscription email to sign in on the website and iPhone app. Service availability depends on an internet connection and may be affected by maintenance or technical issues.</p>
        <p>Subscriptions are purchased and billed through <strong>Treasure Coast Today and Stripe</strong>, not Apple. Apple does not manage or refund these website subscriptions.</p>

        <h2>Changes to plans or these terms</h2>
        <p>We may adjust plans, prices or these terms over time. Where applicable, we will provide advance notice before a price change takes effect, as required by law. You may cancel to avoid a future renewal at a changed price. The latest terms will be posted on this page with an updated date.</p>

        <h2>Support and privacy</h2>
        <p>For questions about subscription charges, cancellations, or access, email <a href="mailto:hello@treasurecoast.today">hello@treasurecoast.today</a> or use our <a href="/contact.html">Contact page</a>. For information about the use and deletion of personal data, see our <a href="/privacy.html">Privacy Policy</a>.</p>
      </div>
      <div class="policy-nav">
        <a href="/subscribe.html">Membership</a>
        <a href="/privacy.html">Privacy Policy</a>
        <a href="/contact.html">Contact</a>
      </div>
    </div>
  </main>'''


def replace_once(original: str, pattern: str, replacement: str, *, label: str, flags=0):
    updated, count = re.subn(pattern, lambda _: replacement, original, count=1, flags=flags)
    if count != 1:
        raise ValueError(f'Source mismatch: unable to locate {label}. No files changed.')
    return updated


def new_terms_html(template):
    s = replace_once(template, r'<title>[^<]*</title>',
        '<title>Subscription Terms | Treasure Coast Today</title>', label='privacy title', flags=re.I)
    s = replace_once(s, r'<meta\s+name="description"\s+content="[^"]*">',
        '<meta name="description" content="Treasure Coast Today subscription terms: monthly and annual pricing, automatic renewal, cancellation, refunds and account deletion.">',
        label='privacy description', flags=re.I)
    s = replace_once(s, r'<link\s+rel="canonical"\s+href="[^"]*">',
        '<link rel="canonical" href="https://treasurecoast.today/subscription-terms.html">',
        label='privacy canonical', flags=re.I)
    s = replace_once(s, r'(?s)  <main>.*?  </main>', TERMS_MAIN, label='privacy main content')
    # Remove the ad network JavaScript from this standalone legal page; do not change the privacy page.
    s = re.sub(r'^<script\s+type="text/javascript"\s+async="async"\s+data-noptimize="1"[^\n]*mediavine[^\n]*</script>\s*\n?', '', s, flags=re.M)
    # Terms page footer should also link to itself.
    s = replace_once(s, r'(<a href="/privacy.html">Privacy</a>)',
        '<a href="/privacy.html">Privacy</a><a href="/subscription-terms.html">Subscription Terms</a>',
        label='privacy footer link')
    return s


def update_subscribe(s):
    link = ('      <p class="membership-renewal membership-landing-renewal" '
            'data-tct-subscription-terms>Cancel anytime: ordinary cancellation stops renewal and keeps access '
            'through the paid period. No prorated refunds except where required by law or approved by TCT. '
            '<a href="/subscription-terms.html">Read Subscription Terms</a> '
            'and <a href="/privacy.html">Privacy Policy</a> before subscribing.</p>')
    if 'data-tct-subscription-terms' not in s:
        anchor = re.findall(r'(?m)^\s*<p class="membership-renewal membership-landing-renewal">[^\n]*</p>',s)
        if len(anchor) != 1:
            raise ValueError('Source mismatch: expected exactly one membership renewal summary. No files changed.')
        s=s.replace(anchor[0],anchor[0]+'\n'+link,1)
    if 'data-tct-cancel-faq' not in s:
        old=r'<details><summary>Can I cancel\?</summary><p>.*?</p></details>'
        new=('''<details data-tct-cancel-faq><summary>Can I cancel?</summary><p>Yes. Sign in, select Manage billing, and cancel in the Stripe portal. Canceling stops future renewals but keeps your TCT account and paid reading access through the end of the current billing period. No prorated refunds, except where required by law or approved by TCT. <a href="/subscription-terms.html">Full subscription terms</a>.</p></details>
        <details data-tct-account-deletion-faq><summary>Is deleting my account the same as canceling?</summary><p>No. Deleting your account is permanent: it immediately ends membership access and cancels active renewals. If you only want to stop future billing, use Manage billing instead.</p></details>''')
        s=replace_once(s,old,new,label='cancel membership FAQ')
    if 'href="/subscription-terms.html">Subscription Terms</a>' not in s:
        footer_anchor='<a href="/privacy.html">Privacy</a>'
        if s.count(footer_anchor)!=1:raise ValueError('Source mismatch: membership footer privacy link is not unique. No files changed.')
        s=s.replace(footer_anchor,footer_anchor+'<a href="/subscription-terms.html">Subscription Terms</a>',1)
    # Respect the user's digital-first terminology preference in the existing membership copy.
    s=s.replace('a local publication focused on the Treasure Coast', 'a local news site focused on the Treasure Coast')
    return s


def main():
    for f in (SUBSCRIBE, PRIVACY):
        if not f.is_file():
            raise ValueError(f'Could not find {f.name} in this directory. Run from the website repository root.')
    subscribe_before=SUBSCRIBE.read_text(encoding='utf8')
    privacy=PRIVACY.read_text(encoding='utf8')
    new_subscribe=update_subscribe(subscribe_before)
    new_terms=new_terms_html(privacy)
    # Existing manually edited terms must never be overwritten. The exact generated page can be rerun safely.
    if TERMS.exists():
        old_terms=TERMS.read_text(encoding='utf8')
        if old_terms!=new_terms:
            raise ValueError('subscription-terms.html already exists and differs; refusing to overwrite. No files changed.')
    if new_subscribe!=subscribe_before: SUBSCRIBE.write_text(new_subscribe,encoding='utf8')
    if not TERMS.exists(): TERMS.write_text(new_terms,encoding='utf8')
    print('Step 1D applied. Review subscribe.html and new subscription-terms.html. No workflow or payment changes made.')

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(str(exc),file=sys.stderr)
        sys.exit(1)
