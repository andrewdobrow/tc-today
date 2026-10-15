#!/usr/bin/env python3
"""Idempotent, single-page Privacy Policy amendment for TCT iOS launch.

Run in tc-today website repo root. Only changes privacy.html. Raises on
unexpected page structure rather than replacing a newer policy silently.
"""
from pathlib import Path

P = Path('privacy.html')
MARKER = '<!-- tct-ios-privacy-disclosures-20261012 -->'


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(f'Expected exactly one existing privacy policy anchor, found {source.count(old)}: {old[:85]!r}')
    return source.replace(old, new, 1)


def updated_privacy(source: str) -> str:
    if MARKER in source:
        return source  # idempotent: do not duplicate disclosures or reset date
    if '<title>Privacy Policy | Treasure Coast Today</title>' not in source:
        raise RuntimeError('Not the expected TCT privacy policy file')

    # Keep the present operator identity while Florida LLC filing remains pending.
    source = replace_once(
        source,
        'Treasure Coast Today is an independent local news website owned and operated by Andrew Dobrow. This policy explains what information is collected when you visit the site, how it is used, and your choices.',
        'Treasure Coast Today is an independent local news website and iPhone app owned and operated by Treasure Coast Today LLC, a Florida limited liability company founded and owned by Andrew Dobrow. This policy explains what information is collected when you use the website or app, how it is used, and your choices.'
    )
    source = replace_once(source, 'Last updated: September 17, 2026', 'Last updated: October 12, 2026')
    source = replace_once(source,
        'We collect limited information needed to operate the site, provide memberships, understand readership and respond to messages:',
        'We collect information needed to operate the website and app, provide memberships and news alerts, understand readership, and respond to messages:')
    source = replace_once(source,
        '        <h2>How we use information</h2>',
        f'''        {MARKER}
        <h2>Information used by our iPhone app</h2>
        <p>Public headlines, stories and event listings can be read in the iPhone app without creating a membership account. The app retrieves content from Treasure Coast Today services over an internet connection. As with ordinary website and API requests, service providers may process technical connection details such as IP address, request times and device/network information.</p>
        <ul>
          <li><strong>Optional news alerts.</strong> If you turn on push notifications, our app receives an Apple Push Notification service (APNs) device token and uses a randomly generated app-installation identifier to register your phone. Our systems store the token, installation identifier, enabled or disabled status, your selected county and breaking-news preferences, the APNs environment, and relevant registration timestamps. This information is used to deliver and manage the alerts you request. You can turn off notifications in the app or through iOS Settings.</li>
          <li><strong>App authentication and membership access.</strong> If you sign in, we process your email address and authentication/session credentials to verify access to subscriber content. The app stores session credentials in iOS Keychain. Membership status is verified by our services; your payment card is handled by Stripe, not by the iPhone app.</li>
          <li><strong>App preferences and reading access.</strong> The app locally stores certain settings, notification-topic preferences and information needed to recognize its monthly free-article allowance. These settings help the app remember your choices and enforce article access rules.</li>
        </ul>

        <h2>How we use information</h2>''')
    source = replace_once(source,
        'We use the information described above to operate and improve the site, provide membership access, process and manage subscriptions, send secure authentication messages, understand readership in aggregate, and respond to messages you send us. We do not sell your personal information.',
        'We use the information described above to operate and improve the website and app, deliver requested push notifications, provide membership access, process and manage subscriptions, send secure authentication messages, understand readership, and respond to messages you send us. We do not sell your personal information.')
    source = replace_once(source,
        '          <li><strong>Resend</strong> as an email-delivery provider for secure membership sign-in messages.</li>',
        '          <li><strong>Resend</strong> as an email-delivery provider for secure membership sign-in messages.</li>\n'
        '          <li><strong>Apple Push Notification service (APNs)</strong> to deliver optional iPhone news alerts. The Apple-issued device token is used for this purpose.</li>')
    source = replace_once(source,
        '        <h2>Children\'s privacy</h2>',
        '''        <h2>Your choices, retention and requests</h2>
        <p>You can decline or disable news alerts and change your selected notification topics through the app and iOS Settings. You can sign out of the app, and you can access your billing and cancellation options through the Treasure Coast Today membership website.</p>
        <p>We retain information for as long as reasonably needed for the purposes described above, including to maintain memberships and comply with applicable legal, accounting, and security obligations. For questions about personal information, or to request access to or deletion of account information, contact <a href="mailto:hello@treasurecoast.today">hello@treasurecoast.today</a>. Some records may need to be retained when required by law.</p>

        <h2>Children's privacy</h2>''')
    source = replace_once(source,
        'Treasure Coast Today is a general-audience local news website and is not directed at children under 13.',
        'Treasure Coast Today is a general-audience local news website and iPhone app, and is not directed at children under 13.')
    return source


def main() -> None:
    if not P.is_file():
        raise SystemExit('Run this script from the website repository root containing privacy.html')
    original = P.read_text(encoding='utf-8')
    updated = updated_privacy(original)
    if updated == original:
        print('Privacy policy iOS disclosure already present. No changes needed.')
        return
    P.write_text(updated, encoding='utf-8')
    print('Updated privacy.html with iPhone app disclosures (LLC ownership unchanged).')


if __name__ == '__main__':
    main()
