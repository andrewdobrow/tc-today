"""Keep Facebook preview images valid on recently generated articles."""
from __future__ import annotations

import datetime as dt
import html
import re
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FALLBACK = "https://treasurecoast.today/og-image.png"
FACEBOOK_UA = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
OG = re.compile(r'(<meta\s+property="og:image"\s+content=")[^"]*("\s*/?>)', re.I)
TW = re.compile(r'(<meta\s+name="twitter:image"\s+content=")[^"]*("\s*/?>)', re.I)
DIMENSIONS = re.compile(r'\s*<meta\s+property="og:image:(?:width|height)"\s+content="[^"]*"\s*/?>', re.I)


def image_usable(url, session):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    # Don't disturb intentionally editor-selected first-party assets.
    if parsed.hostname == "treasurecoast.today":
        return True
    try:
        response = session.get(
            url, headers={"User-Agent": FACEBOOK_UA, "Accept": "image/webp,image/png,image/jpeg,*/*"},
            timeout=(4, 8),
        )
        if response.status_code != 200 or not response.headers.get("content-type", "").lower().startswith("image/"):
            return False
        with Image.open(BytesIO(response.content)) as image:
            return image.width >= 200 and image.height >= 200 and image.format in ("JPEG", "PNG", "WEBP", "GIF")
    except (requests.RequestException, OSError, ValueError):
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    args = parser.parse_args()
    cutoff = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=args.days)
    cache = {}
    counts = {"verified": 0, "fallback": 0}
    with requests.Session() as session:
        for page in sorted((ROOT / "articles").glob("*.html")):
            try:
                if dt.date.fromisoformat(page.name[:10]) < cutoff:
                    continue
            except ValueError:
                continue
            content = page.read_text(encoding="utf-8")
            match = OG.search(content)
            if not match:
                continue
            url = html.unescape(match.group(0).split('content="', 1)[1].split('"', 1)[0])
            if url not in cache:
                cache[url] = image_usable(url, session)
            modified = DIMENSIONS.sub("", content)  # Current 1200x630 values are not measured.
            if cache[url]:
                counts["verified"] += 1
            else:
                counts["fallback"] += 1
                modified = OG.sub(lambda m: m.group(1) + FALLBACK + m.group(2), modified, count=1)
                modified = TW.sub(lambda m: m.group(1) + FALLBACK + m.group(2), modified, count=1)
            if modified != content:
                page.write_text(modified, encoding="utf-8")
    print(f"Facebook social image guard: {counts}; checked {len(cache)} unique images")


if __name__ == "__main__":
    main()
