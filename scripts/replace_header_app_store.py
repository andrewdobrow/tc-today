#!/usr/bin/env python3
"""Replace the retired masthead Morning Brief promo with the official App Store badge.

Runs after article/event generation and also in deploy-only, so archived pages,
regional landing pages, and untouched pages all receive the same masthead.
This intentionally leaves Kit's newsletter signup forms and modal alone.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
APP_URL = "https://apps.apple.com/us/app/treasure-coast-today/id6821545564"
BADGE_URL = "https://developer.apple.com/assets/elements/badges/download-on-the-app-store.svg"

APP_BADGE = (
    f'<a class="masthead-app-store" href="{APP_URL}" '
    'aria-label="Download Treasure Coast Today on the App Store" rel="noopener">'
    f'<img src="{BADGE_URL}" alt="Download on the App Store" '
    'width="135" height="40" decoding="async"></a>'
)
MOBILE_LINK = (
    f'<a href="{APP_URL}" class="mobile-nav-link" data-tct-app-store-link>'
    'Get the TCT iPhone App</a>'
)
LEGACY_MASTHEAD = re.compile(
    r'<a\b[^>]*\bclass="masthead-newsletter"[^>]*>.*?</a>',
    re.I | re.S,
)
MOBILE_EVENTS_LINK = re.compile(r'<a href="/events\.html" class="mobile-nav-link[^"]*"[^>]*>Events</a>', re.I)


CSS_ASSET_VERSION = re.search(
    r'ASSET_VERSION = "([^"]+)"',
    (ROOT / "scripts/build_audience_features.py").read_text(encoding="utf-8"),
)
if CSS_ASSET_VERSION is None:
    raise RuntimeError("Unable to resolve TCT shared CSS version")
CSS_ASSET_VERSION = CSS_ASSET_VERSION.group(1)
CSS_REFERENCE = re.compile(r'(/style\.css\?v=)\d+(?:\.\d+)+')

KIT_MODAL_EMBED = (
    '<script async data-uid="be625cadfe" '
    'src="https://treasure-coast-today.kit.com/be625cadfe/index.js"></script>'
)
MAIN_JS_SCRIPT = re.compile(r"""<script\b[^>]*src=["']/main\.js(?:\?[^"']*)?["'][^>]*></script>""", re.I)

def ensure_official_kit_embed(html: str) -> str:
    """Install Kit's HTML embed once, with timing and frequency owned by Kit."""
    if 'site-masthead' not in html or '</body>' not in html.lower():
        return html
    if re.search(r"""<script\b[^>]*data-uid=["']be625cadfe["']""", html, re.I):
        return html
    match = MAIN_JS_SCRIPT.search(html)
    if match:
        return html[:match.start()] + KIT_MODAL_EMBED + "\n  " + html[match.start():]
    return re.sub(r'</body>', KIT_MODAL_EMBED + "\n</body>", html, count=1, flags=re.I)



MOBILE_NAV_BOOTSTRAP = """<script data-tct-mobile-nav-boot>
(function () {
  // Independent of main.js and third-party scripts, including Kit.
  var media = window.matchMedia("(max-width: 900px)");
  function setOpen(button, panel, open) {
    if (!button || !panel) return;
    var active = Boolean(open && media.matches);
    panel.hidden = !active;
    button.setAttribute("aria-expanded", active ? "true" : "false");
    button.setAttribute("aria-label", active ? "Close navigation menu" : "Open navigation menu");
    document.documentElement.classList.toggle("mobile-nav-open", active);
  }
  document.addEventListener("click", function(event) {
    var button = event.target.closest && event.target.closest(".mobile-nav-toggle-button");
    var panel = document.getElementById("tct-mobile-nav");
    if (button && panel) {
      // Capture before legacy main.js handlers; prevent a double toggle.
      event.preventDefault();
      event.stopPropagation();
      setOpen(button, panel, panel.hidden);
      return;
    }
    if (!panel || panel.hidden) return;
    var toggle = document.querySelector(".mobile-nav-toggle-button");
    if (panel.contains(event.target) && !(event.target.closest && event.target.closest("a"))) return;
    setOpen(toggle, panel, false);
  }, true);
  document.addEventListener("keydown", function(event) {
    if (event.key !== "Escape") return;
    var panel = document.getElementById("tct-mobile-nav");
    if (!panel || panel.hidden) return;
    var button = document.querySelector(".mobile-nav-toggle-button");
    setOpen(button, panel, false);
    if (button) button.focus();
  }, true);
  function onResize() {
    if (media.matches) return;
    setOpen(document.querySelector(".mobile-nav-toggle-button"),
            document.getElementById("tct-mobile-nav"), false);
  }
  if (media.addEventListener) media.addEventListener("change", onResize);
  else if (media.addListener) media.addListener(onResize);
})();
</script>"""


def ensure_mobile_nav_bootstrap(html: str) -> str:
    """Install a small independent hamburger handler on every mobile-nav page."""
    if 'mobile-nav-toggle-button' not in html or 'id="tct-mobile-nav"' not in html:
        return html
    if 'data-tct-mobile-nav-boot' in html:
        return html
    match = MAIN_JS_SCRIPT.search(html)
    if match:
        return html[:match.start()] + MOBILE_NAV_BOOTSTRAP + "\n  " + html[match.start():]
    return re.sub(r'</body>', MOBILE_NAV_BOOTSTRAP + "\n</body>", html, count=1, flags=re.I)

def replace_header_promo(html: str) -> str:
    # Only replace the header promo, not the independent newsletter signups.
    updated = LEGACY_MASTHEAD.sub(APP_BADGE, html)
    if ('id="tct-mobile-nav"' in updated
            and 'data-tct-app-store-link' not in updated):
        updated = MOBILE_EVENTS_LINK.sub(
            lambda match: MOBILE_LINK + "\n          " + match.group(0),
            updated,
            count=1,
        )
    if 'class="masthead-app-store"' in updated:
        # Older archives may still reference cached CSS that doesn't know the
        # new badge. Ensure every served page gets the current mobile layout.
        updated = CSS_REFERENCE.sub(
            lambda match: match.group(1) + CSS_ASSET_VERSION, updated
        )
    return ensure_mobile_nav_bootstrap(ensure_official_kit_embed(updated))


def reconcile(root: Path = ROOT) -> dict[str, int]:
    scanned = updated = 0
    for path in root.rglob("*.html"):
        if any(part.startswith(".") or part in ("node_modules", "venv", "__pycache__")
               for part in path.relative_to(root).parts):
            continue
        scanned += 1
        before = path.read_text(encoding="utf-8")
        after = replace_header_promo(before)
        if before != after:
            path.write_text(after, encoding="utf-8")
            updated += 1
    print(f"App Store masthead: scanned={scanned}, updated={updated}")
    return {"scanned": scanned, "updated": updated}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    reconcile(args.root)
