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



def paywall_section_html(slug: str) -> str:
    escaped_slug = html.escape(slug, quote=True)
    return f'''<section class="tct-paywall" data-tct-paywall data-slug="{escaped_slug}" aria-label="Treasure Coast Today membership">
  <div class="tct-paywall-topline">Already a subscriber? <button class="tct-member-link" type="button" data-reveal-signin>Sign in</button></div>
  <div class="tct-paywall-meter-status hidden" data-meter-status></div>
  <div class="tct-paywall-brand" data-paywall-brand>Treasure Coast Today Membership</div>
  <h2 class="tct-paywall-offer-headline" data-paywall-headline>Continue reading Treasure Coast Today for just $1.</h2>
  <p class="tct-paywall-copy" data-paywall-copy>Get unlimited, ad-free access to independent local reporting across Martin, St. Lucie and Indian River counties.</p>
  <p class="tct-paywall-meter-reset hidden" data-meter-reset></p>
  <div class="membership-message hidden"></div>
  <div class="tct-paywall-signin hidden" data-paywall-signin>
    <form class="membership-form" data-signin-form>
      <input type="email" autocomplete="email" placeholder="Email address" aria-label="Membership email address" required>
      <button class="tct-member-btn" type="submit">Email me a sign-in link</button>
    </form>
    <div class="membership-message hidden"></div>
  </div>
  <div class="tct-paywall-plans" data-paywall-plans>
    <div class="tct-paywall-plan-offer tct-paywall-plan-offer-monthly">
      <div class="tct-paywall-offer-copy">
        <span class="tct-paywall-eyebrow">Introductory offer</span>
        <div class="tct-paywall-price-line"><strong>$1</strong><span>for your first month</span></div>
        <div class="tct-paywall-plan-note">Then $4.99/month. Cancel anytime.</div>
      </div>
      <button class="tct-member-btn tct-paywall-plan-button" data-plan="monthly" type="button">Continue for $1</button>
    </div>
    <div class="tct-paywall-plan-offer tct-paywall-plan-offer-annual">
      <div class="tct-paywall-offer-copy">
        <span class="tct-paywall-eyebrow">Annual membership</span>
        <div class="tct-paywall-price-line"><strong>$49</strong><span>per year</span></div>
        <div class="tct-paywall-plan-note">About $4.08/month. Cancel anytime.</div>
      </div>
      <button class="tct-member-btn tct-paywall-plan-button" data-plan="annual" type="button">Continue annually</button>
    </div>
  </div>
  <div class="tct-paywall-benefits" aria-label="Membership benefits">
    <span>Comprehensive local reporting</span>
    <span>Ad-free reading</span>
    <span>Support independent journalism</span>
  </div>
  <p class="tct-paywall-secure">Secure checkout powered by Stripe. Subscriptions renew automatically until canceled.</p>
</section>'''


def paywall_html(slug: str) -> str:
    return (
        '<div class="tct-paywall-fade" aria-hidden="true"></div>\n'
        + paywall_section_html(slug)
        + '\n<div id="tct-protected-content" class="article-body tct-protected-content tct-paywalled-content" aria-live="polite"></div>'
    )


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


MEMBER_HINT_KEY = "tct_member_entitled_hint"
MEMBERSHIP_ASSET_VERSION = "1.13.7.9"
MEMBER_PREPAINT_MARKER = "data-tct-member-prepaint"
MEMBER_PREPAINT_SCRIPT = (
    '<script data-tct-member-prepaint>\n'
    "(function(){try{"
    "if(localStorage.getItem('tct_member_entitled_hint')==='1'){document.documentElement.classList.add('tct-member-preverified');return;}"
    "var z=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit'}).formatToParts(new Date());"
    "var y=(z.find(function(p){return p.type==='year'})||{}).value||'';var m=(z.find(function(p){return p.type==='month'})||{}).value||'';"
    "var period=y+'-'+m;var slug=(location.pathname.split('/').pop()||'').replace(/\\.html$/,'');"
    "var raw=localStorage.getItem('tct_monthly_free_article_v1');var state=raw?JSON.parse(raw):null;"
    "var stalePending=state&&state.pending&&!state.meter_token&&(Date.now()-Number(state.started_at||0)>120000);"
    "if(stalePending){localStorage.removeItem('tct_monthly_free_article_v1');state=null;}"
    "if(slug&&(!state||state.period!==period||state.slug===slug)){document.documentElement.classList.add('tct-meter-precheck');setTimeout(function(){document.documentElement.classList.remove('tct-meter-precheck')},5000);}"
    "}catch(_e){}})();\n"
    '</script>'
)


def inject_membership_assets(page_html: str, slug: str) -> str:
    css_href = f"/membership.css?v={MEMBERSHIP_ASSET_VERSION}"
    js_src = f"/membership.js?v={MEMBERSHIP_ASSET_VERSION}"

    # Run the visual member hint before first paint. This only suppresses the
    # sales treatment while entitlement is rechecked; protected article text is
    # still available only through the server-side protected-article function.
    if MEMBER_PREPAINT_MARKER not in page_html:
        page_html = page_html.replace("</head>", f"  {MEMBER_PREPAINT_SCRIPT}\n</head>", 1)

    # Normalize retained pages to cache-busted membership assets so a browser
    # cannot keep the pre-no-flash JS/CSS after this deployment.
    css_pattern = re.compile(r"href=['\"]/membership\.css(?:\?[^'\"]*)?['\"]", re.I)
    if css_pattern.search(page_html):
        page_html = css_pattern.sub(f'href="{css_href}"', page_html, count=1)
    else:
        page_html = page_html.replace("</head>", f'  <link rel="stylesheet" href="{css_href}">\n</head>', 1)

    js_pattern = re.compile(r"src=['\"]/membership\.js(?:\?[^'\"]*)?['\"]", re.I)
    if js_pattern.search(page_html):
        page_html = js_pattern.sub(f'src="{js_src}"', page_html, count=1)
    else:
        page_html = page_html.replace(
            "</body>",
            f'  <script src="/membership-config.js"></script>\n  <script type="module" src="{js_src}"></script>\n</body>',
            1,
        )

    if re.search(r"<body\b[^>]*>", page_html, re.I):
        page_html = re.sub(
            r"<body\b([^>]*)>",
            lambda m: f'<body{m.group(1)} data-article-slug="{html.escape(slug, quote=True)}">' if "data-article-slug=" not in m.group(0) else m.group(0),
            page_html,
            count=1,
            flags=re.I,
        )
    return page_html
