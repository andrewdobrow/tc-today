"""Deterministic article-preview and membership-paywall helpers.

No protected article remainder is persisted in public HTML. Callers write the
returned protected HTML only to a secure transport/export outside the repo.
"""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ArticleSplit:
    preview_html: str
    protected_html: str


_TAG_RE = re.compile(r"<[^>]+>")
_P_RE = re.compile(r"<p\b([^>]*)>(.*?)</p>", re.I | re.S)
_SENTENCE_RE = re.compile(r"(?<=[.!?])(?:[\"'”’)]*)\s+")


def _plain(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub(" ", fragment or ""))).strip()


def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return []
    pieces = [part.strip() for part in _SENTENCE_RE.split(text) if part.strip()]
    return pieces or [text]


PREVIEW_MAX_CHARS = 300
PREVIEW_RATIO = 0.52
PREVIEW_MIN_CHARS = 24
PREVIEW_FADE_MAX_CHARS = 110


def _word_boundary(text: str, target: int) -> int:
    """Return a stable cut close to target without splitting a word."""
    target = max(1, min(int(target), len(text)))
    if target >= len(text):
        return len(text)
    left = text.rfind(" ", max(0, target - 28), target + 1)
    if left >= max(1, int(target * 0.72)):
        return left
    right = text.find(" ", target, min(len(text), target + 20))
    return right if right != -1 else target


def split_article_body(body_html: str, preview_max_chars: int = PREVIEW_MAX_CHARS) -> ArticleSplit | None:
    """Expose only a cliffhanger-sized slice of paragraph one.

    The public preview is character bounded rather than paragraph bounded. For a
    normal lead, roughly half of paragraph one is public, with the final portion
    visibly fading away. The rest of paragraph one and every later paragraph are
    returned only in the protected payload.
    """
    body_html = str(body_html or "")
    paragraphs = list(_P_RE.finditer(body_html))
    if not paragraphs:
        return None

    first = paragraphs[0]
    first_text = _plain(first.group(2))
    if len(first_text) < 36:
        return None

    ratio_target = max(PREVIEW_MIN_CHARS, int(round(len(first_text) * PREVIEW_RATIO)))
    target = min(max(PREVIEW_MIN_CHARS, int(preview_max_chars)), ratio_target)
    # Always leave a real first-paragraph continuation when the lead is long enough.
    target = min(target, max(PREVIEW_MIN_CHARS, len(first_text) - 18))
    cut = _word_boundary(first_text, target)
    if cut <= 0 or cut >= len(first_text):
        return None

    fade_chars = min(PREVIEW_FADE_MAX_CHARS, max(34, int(cut * 0.42)))
    fade_start = _word_boundary(first_text, max(1, cut - fade_chars))
    if fade_start <= 0 or fade_start >= cut:
        fade_start = max(1, cut // 2)

    solid_text = first_text[:fade_start].rstrip()
    faded_text = first_text[fade_start:cut].strip()
    hidden_first = first_text[cut:].lstrip()
    if not solid_text or not faded_text or not hidden_first:
        return None

    opening_attrs = first.group(1) or ""
    preview_paragraph = (
        f'<p{opening_attrs} data-tct-preview-paragraph="true">'
        f'<span class="tct-preview-solid">{html.escape(solid_text)}</span> '
        f'<span class="tct-preview-fade-text">{html.escape(faded_text)}</span>'
        '<span class="tct-preview-ellipsis" aria-hidden="true">…</span>'
        '</p>'
    )
    preview = body_html[: first.start()] + preview_paragraph

    protected = (
        f'<p{opening_attrs} data-tct-first-paragraph-continuation="true">'
        f'{html.escape(hidden_first)}</p>'
        + body_html[first.end() :]
    ).strip()

    # Do not manufacture a paywall for a tiny article where almost nothing is hidden.
    if len(_plain(protected)) < 80:
        return None
    return ArticleSplit(preview_html=preview.strip(), protected_html=protected)


def is_public_service_exception(headline: str, body_html: str) -> bool:
    """Narrow, deterministic life-safety exceptions that remain fully free."""
    text = _plain(f"{headline} {body_html}").lower()
    if any(term in text for term in ("mandatory evacuation", "evacuation order", "ordered to evacuate")):
        return True
    if any(term in text for term in ("hurricane warning", "storm surge warning")):
        return True
    if "boil water" in text and any(term in text for term in ("notice", "advisory", "order")):
        return True
    if "missing" in text and any(term in text for term in ("child", "boy", "girl", "juvenile")) and any(term in text for term in ("amber alert", "missing child", "missing boy", "missing girl")):
        return True
    if "shelter" in text and any(term in text for term in ("emergency shelter", "shelters open", "shelter opens", "shelter locations")):
        return True
    if "bridge" in text and any(term in text for term in ("emergency closure", "closed until further notice", "bridge is closed", "bridge closed")):
        return True
    return False


def paywall_html(slug: str) -> str:
    escaped_slug = html.escape(slug, quote=True)
    return f'''<div class="tct-paywall-fade" aria-hidden="true"></div>
<section class="tct-paywall" data-tct-paywall data-slug="{escaped_slug}" aria-label="Treasure Coast Today membership">
  <div class="tct-paywall-topline">Already a member?&nbsp;<button class="tct-member-link" type="button" data-reveal-signin>Sign in</button></div>
  <h2>Two ways to continue reading</h2>
  <p class="tct-paywall-value">Comprehensive local coverage. No ads. Less than $5 a month.</p>
  <p class="tct-paywall-copy">Get unlimited access to Treasure Coast Today and support independent journalism covering Martin, St. Lucie and Indian River counties.</p>
  <div class="membership-message hidden"></div>
  <div class="tct-paywall-signin hidden" data-paywall-signin>
    <form class="membership-form" data-signin-form>
      <input type="email" autocomplete="email" placeholder="Email address" aria-label="Membership email address" required>
      <button class="tct-member-btn" type="submit">Email me a sign-in link</button>
    </form>
    <div class="membership-message hidden"></div>
  </div>
  <div class="tct-paywall-plans" data-paywall-plans>
    <article class="tct-paywall-plan best">
      <span class="tct-paywall-badge">Best value</span>
      <h3>Annual — $49/year</h3>
      <div class="tct-paywall-price">About $4.08/month</div>
      <div class="tct-paywall-plan-note">Save $10.88 per year</div>
      <button class="tct-member-btn" data-plan="annual" type="button">Subscribe annually</button>
    </article>
    <article class="tct-paywall-plan">
      <span class="tct-paywall-badge tct-paywall-badge-flexible">Most flexible</span>
      <h3>Monthly — $4.99/month</h3>
      <div class="tct-paywall-price">$4.99</div>
      <div class="tct-paywall-plan-note">Cancel anytime</div>
      <button class="tct-member-btn" data-plan="monthly" type="button">Subscribe monthly</button>
    </article>
  </div>
  <p class="tct-paywall-benefits">Unlimited articles · No ads · Support independent local journalism</p>
  <p class="tct-paywall-secure">Secure checkout powered by Stripe. Cancel anytime.</p>
  <p class="tct-paywall-renewal">Subscriptions renew automatically until canceled. Manage or cancel your subscription anytime from your membership account.</p>
</section>
<div id="tct-protected-content" class="article-body tct-protected-content tct-paywalled-content" aria-live="polite"></div>'''


def add_paywall_schema(page_html: str) -> str:
    pattern = re.compile(r'(<script\s+type="application/ld\+json">)(.*?)(</script>)', re.I | re.S)
    for match in pattern.finditer(page_html):
        try:
            data = json.loads(match.group(2))
        except Exception:
            continue
        if data.get("@type") not in {"NewsArticle", "Article"}:
            continue
        data["isAccessibleForFree"] = False
        data["hasPart"] = {
            "@type": "WebPageElement",
            "isAccessibleForFree": False,
            "cssSelector": ".tct-paywalled-content",
        }
        replacement = match.group(1) + json.dumps(data, separators=(",", ":")) + match.group(3)
        return page_html[: match.start()] + replacement + page_html[match.end() :]
    return page_html


def inject_membership_assets(page_html: str, slug: str) -> str:
    if '/membership.css' not in page_html:
        page_html = page_html.replace('</head>', '  <link rel="stylesheet" href="/membership.css">\n</head>', 1)
    if '/membership.js' not in page_html:
        page_html = page_html.replace('</body>', '  <script src="/membership-config.js"></script>\n  <script type="module" src="/membership.js"></script>\n</body>', 1)
    if re.search(r'<body\b[^>]*>', page_html, re.I):
        page_html = re.sub(
            r'<body\b([^>]*)>',
            lambda m: f'<body{m.group(1)} data-article-slug="{html.escape(slug, quote=True)}">' if 'data-article-slug=' not in m.group(0) else m.group(0),
            page_html,
            count=1,
            flags=re.I,
        )
    return page_html
