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


def split_article_body(body_html: str, second_paragraph_sentences: int = 2) -> ArticleSplit | None:
    """Keep paragraph one plus 1-2 sentences of paragraph two public.

    Returns None for bodies too short to have a meaningful protected remainder.
    """
    body_html = str(body_html or "")
    paragraphs = list(_P_RE.finditer(body_html))
    if len(paragraphs) < 2:
        return None

    first, second = paragraphs[0], paragraphs[1]
    second_text = _plain(second.group(2))
    sentences = _sentences(second_text)
    if not sentences:
        return None
    visible_count = min(max(1, second_paragraph_sentences), len(sentences))
    visible_text = " ".join(sentences[:visible_count]).strip()
    hidden_text = " ".join(sentences[visible_count:]).strip()

    preview = body_html[: first.end()]
    between = body_html[first.end() : second.start()]
    opening_attrs = second.group(1) or ""
    preview += between + f"<p{opening_attrs}>{html.escape(visible_text)}</p>"

    protected_parts: list[str] = []
    if hidden_text:
        protected_parts.append(f"<p{opening_attrs}>{html.escape(hidden_text)}</p>")
    protected_parts.append(body_html[second.end() :])
    protected = "".join(protected_parts).strip()

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
</section>
<div id="tct-protected-content" class="article-body tct-protected-content" aria-live="polite"></div>'''


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
            "cssSelector": ".tct-member-only",
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
