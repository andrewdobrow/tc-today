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


PREVIEW_MAX_CHARS = 340
PREVIEW_MIN_CHARS = 150
PREVIEW_MIN_HIDDEN_CHARS = 90
FULL_BODY_MARKER = "<!--tct-full-article-v2-->"


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


def _preview_target(total_chars: int, preview_max_chars: int) -> int:
    """Choose a consistent teaser size while always leaving meaningful content hidden."""
    ceiling = max(PREVIEW_MIN_CHARS, int(preview_max_chars))
    target = min(ceiling, max(PREVIEW_MIN_CHARS, total_chars - PREVIEW_MIN_HIDDEN_CHARS))
    target = min(target, total_chars - PREVIEW_MIN_HIDDEN_CHARS)
    return max(0, target)


def split_article_body(body_html: str, preview_max_chars: int = PREVIEW_MAX_CHARS) -> ArticleSplit | None:
    """Expose a consistent character-bounded teaser across paragraph boundaries.

    The visible teaser aims for about 340 characters on normal articles, regardless
    of whether the lead paragraph is unusually short or unusually long. At least
    90 characters remain hidden, and the protected store receives the complete
    article body so future teaser migrations never depend on public HTML.
    """
    body_html = str(body_html or "")
    paragraphs = list(_P_RE.finditer(body_html))
    if not paragraphs:
        return None

    paragraph_rows: list[tuple[str, str]] = []
    for match in paragraphs:
        text = _plain(match.group(2))
        if text:
            paragraph_rows.append((match.group(1) or "", text))
    if not paragraph_rows:
        return None

    total_chars = sum(len(text) for _, text in paragraph_rows) + max(0, len(paragraph_rows) - 1)
    target = _preview_target(total_chars, preview_max_chars)
    if target < PREVIEW_MIN_CHARS or total_chars - target < PREVIEW_MIN_HIDDEN_CHARS:
        return None

    preview_parts: list[str] = []
    used = 0
    for attrs, text in paragraph_rows:
        separator_cost = 1 if preview_parts else 0
        remaining = target - used - separator_cost
        if remaining <= 0:
            break
        if len(text) <= remaining:
            preview_parts.append(f'<p{attrs}>{html.escape(text)}</p>')
            used += separator_cost + len(text)
            continue

        cut = _word_boundary(text, remaining)
        if cut < 24 and preview_parts:
            break
        cut = max(1, min(cut, len(text) - 1))
        preview_parts.append(f'<p{attrs}>{html.escape(text[:cut].rstrip())}</p>')
        used += separator_cost + cut
        break

    preview_inner = "".join(preview_parts).strip()
    preview_plain = _plain(preview_inner)
    if len(preview_plain) < PREVIEW_MIN_CHARS:
        return None
    if total_chars - len(preview_plain) < PREVIEW_MIN_HIDDEN_CHARS:
        return None

    preview = (
        '<div class="tct-preview-copy" data-tct-preview-copy="true">'
        + preview_inner
        + '</div>'
    )
    protected = FULL_BODY_MARKER + body_html.strip()
    return ArticleSplit(preview_html=preview, protected_html=protected)


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
