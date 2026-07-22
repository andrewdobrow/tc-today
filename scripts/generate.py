"""
Treasure Coast Today - news generation pipeline - v6.5.18 Authoritative Custom Canonicals + Atomic Publishing
Covers Martin, St. Lucie, and Indian River counties.
Runs 4x/day via GitHub Actions.
"""

import os
import json
import re
import hashlib
import feedparser
import requests
import anthropic
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

# -- CONFIG --

TCT_PRESENTATION_VERSION = "6.4-unified-presentation-hotfix"

CATEGORIES = {
    "local_gov": {
        "label": "Local Government",
        "front_page_cap": 10,
        "feeds": [
            "https://www.wptv.com/news/local-news.rss",
            "https://www.wptv.com/news/political.rss",
            "https://www.wptv.com/news/local-news/investigations.rss",
            "https://news.google.com/rss/search?q=martin+county+florida+commission+budget+zoning+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=st+lucie+county+florida+commission+council+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=indian+river+county+florida+commission+council+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=stuart+florida+city+council+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=port+st+lucie+city+council+mayor+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=fort+pierce+city+commission+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=vero+beach+city+council+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=martin+county+school+district+florida+when:3d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=st+lucie+county+school+district+florida+when:3d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=indian+river+county+school+district+florida+when:3d&hl=en-US&gl=US&ceid=US:en",
        ],
    },
    "crime": {
        "label": "Crime & Safety",
        "front_page_cap": 8,
        "feeds": [
            "https://www.wptv.com/news/local-news.rss",
            "https://www.wptv.com/news/region-martin-county.rss",
            "https://www.wptv.com/news/region-st-lucie-county.rss",
            "https://www.wptv.com/news/region-indian-river-county.rss",
            "https://news.google.com/rss/search?q=martin+county+sheriff+arrest+charged+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=st+lucie+county+police+arrest+charged+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=indian+river+county+sheriff+arrest+charged+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=port+st+lucie+fort+pierce+police+arrest+when:2d&hl=en-US&gl=US&ceid=US:en",
        ],
    },
    "business": {
        "label": "Business & Development",
        "front_page_cap": 8,
        "feeds": [
            "https://www.wptv.com/news/local-news.rss",
            "https://www.wptv.com/news/region-martin-county.rss",
            "https://www.wptv.com/news/region-st-lucie-county.rss",
            "https://www.wptv.com/news/region-indian-river-county.rss",
            "https://news.google.com/rss/search?q=martin+county+florida+business+development+real+estate+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=st+lucie+county+florida+business+jobs+development+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=indian+river+county+florida+business+development+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=treasure+coast+florida+new+business+restaurant+opening+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=port+st+lucie+real+estate+development+construction+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=stuart+florida+business+downtown+development+when:2d&hl=en-US&gl=US&ceid=US:en",
        ],
    },

    "sports": {
        "label": "Sports",
        "front_page_cap": 6,
        "feeds": [
            "https://www.wptv.com/sports.rss",
            "https://www.wptv.com/sports/sports-headlines.rss",
            "https://news.google.com/rss/search?q=martin+county+high+school+sports+game+score+when:3d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=st+lucie+county+high+school+sports+game+when:3d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=treasure+coast+florida+football+basketball+baseball+soccer+when:3d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=st+lucie+mets+florida+when:7d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=jensen+beach+south+fork+martin+county+high+school+sports+when:7d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=vero+beach+indian+river+high+school+sports+when:7d&hl=en-US&gl=US&ceid=US:en",
        ],
    },
    "things_to_do": {
        "label": "Things To Do",
        "front_page_cap": 5,
        "feeds": [
            "https://www.wptv.com/news/good-news.rss",
            "https://www.wptv.com/lifestyle/taste-and-see.rss",
            "https://news.google.com/rss/search?q=treasure+coast+florida+events+festival+weekend+when:7d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=stuart+florida+events+arts+culture+when:7d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=port+st+lucie+events+parks+recreation+when:7d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=vero+beach+florida+events+arts+beach+when:7d&hl=en-US&gl=US&ceid=US:en",
        ],
    },
    "florida": {
        "label": "Florida",
        "front_page_hero": False,
        "feeds": [
            "https://www.wptv.com/news/state.rss",
            "https://news.google.com/rss/search?q=florida+insurance+property+homeowners+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=florida+hurricane+storm+weather+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=florida+new+law+takes+effect+residents+when:3d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=florida+gas+prices+cost+of+living+utilities+when:3d&hl=en-US&gl=US&ceid=US:en",
        ],
    },
    "martin": {
        "label": "Martin County",
        "front_page_hero": False,
        "feeds": [
            "https://www.wptv.com/news/region-martin-county.rss",
            "https://news.google.com/rss/search?q=martin+county+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=stuart+florida+news+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=jensen+beach+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=palm+city+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=hobe+sound+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
        ],
    },
    "st_lucie": {
        "label": "St. Lucie County",
        "front_page_hero": False,
        "feeds": [
            "https://www.wptv.com/news/region-st-lucie-county.rss",
            "https://news.google.com/rss/search?q=st+lucie+county+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=port+st+lucie+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=fort+pierce+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=st+lucie+county+florida+when:7d&hl=en-US&gl=US&ceid=US:en",
        ],
    },
    "indian_river": {
        "label": "Indian River County",
        "front_page_hero": False,
        "feeds": [
            "https://www.wptv.com/news/region-indian-river-county.rss",
            "https://www.wptv.com/news/local-news.rss",
            "https://news.google.com/rss/search?q=indian+river+county+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=vero+beach+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=sebastian+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
        ],
    },
}
HEADLINES_PER_CATEGORY = 12
CARDS_PER_CATEGORY     = 6

COUNTY_KEYS = {"martin", "st_lucie", "indian_river"}

# A genuine milestone should regain prominence without pretending the story was
# newly published. For 72 hours after a significant update, ranking moves the
# story 70% of the way from its original publication time toward the update time.
# Truly new reporting can still outrank it, and the boost expires automatically.
SIGNIFICANT_UPDATE_BOOST_RATIO = 0.70
SIGNIFICANT_UPDATE_BOOST_HOURS = 72

# Treasure Coast Today uses one editorial clock everywhere readers see or
# compare freshness. ZoneInfo handles EST/EDT transitions automatically.
EASTERN = ZoneInfo("America/New_York")

def _parse_editorial_datetime(value):
    """Parse RFC822, ISO datetime, or YYYY-MM-DD into an aware UTC datetime."""
    from datetime import timezone as _tz
    from email.utils import parsedate_to_datetime as _parse_rfc822
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        dt = _parse_rfc822(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_tz.utc)
        return dt.astimezone(_tz.utc)
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_tz.utc)
        return dt.astimezone(_tz.utc)
    except Exception:
        pass
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").replace(tzinfo=_tz.utc)
    except Exception:
        return None

def _canonical_content_hash(headline="", teaser="", body="", image_url=""):
    """Stable hash of reader-visible canonical content.

    Build timestamps, source metadata, sitemap changes, and workflow runs are
    deliberately excluded. The hash changes only when the article a reader sees
    changes.
    """
    def _norm(value):
        return re.sub(r"\s+", " ", str(value or "")).strip()
    payload = "\n\n".join([
        _norm(headline),
        _norm(teaser),
        _norm(body),
        _norm(image_url),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _story_display_timestamp(entry):
    """Timestamp shown on cards: real editorial modification, else publication."""
    return (entry.get("editorial_updated_at")
            or entry.get("first_published")
            or entry.get("date")
            or "")

def _effective_story_datetime(entry):
    """Return an aware Eastern datetime for card/archive ordering.

    A real editorial modification ranks at its actual modification time. Stories
    that have never evolved rank at their immutable original publication time.
    Missing or malformed values sort last. Routine workflow runs do not affect
    this function because build timestamps and filesystem mtimes are ignored.
    """
    raw = _story_display_timestamp(entry or {})
    parsed = _parse_editorial_datetime(raw)
    if parsed is not None:
        return parsed.astimezone(EASTERN)
    return datetime(1900, 1, 1, tzinfo=EASTERN)

def _editorial_freshness_dt(entry, now=None):
    """Return effective ranking time with a temporary partial milestone boost.

    Original publication remains immutable. A significant update temporarily moves
    the ranking timestamp 70% toward the update time, then fully expires after 72h.
    Repairs, rewrites, and ordinary lastmod changes never receive this treatment.
    """
    from datetime import timezone as _tz
    now = now or datetime.now(_tz.utc)
    published = _parse_editorial_datetime(entry.get("first_published") or entry.get("date"))
    if published is None:
        published = datetime(1900, 1, 1, tzinfo=_tz.utc)
    updated = _parse_editorial_datetime(entry.get("significant_update_at"))
    if not updated or updated < published:
        return published
    age_hours = (now - updated).total_seconds() / 3600
    if age_hours < 0 or age_hours > SIGNIFICANT_UPDATE_BOOST_HOURS:
        return published
    return published + (updated - published) * SIGNIFICANT_UPDATE_BOOST_RATIO

def category_max_age_hours(category_key):
    """Different sections need different freshness windows.

    The front page still prioritizes fresh stories later, but section pages should
    not collapse just because a county feed only has a few stories in the last
    48 hours. County/schools/sports/events content remains useful longer than
    front-page breaking news.
    """
    if category_key in COUNTY_KEYS:
        return 168  # 7 days for county pages
    if category_key in {"sports", "business"}:
        return 168  # 7 days for slower-moving local beats
    if category_key == "things_to_do":
        return 336  # 14 days for event/activity planning
    if category_key == "florida":
        return 72
    return 72


OUTPUT_DIR   = Path(__file__).parent.parent
SITE_URL     = "https://treasurecoast.today"
SITE_NAME    = "Treasure Coast Today"
SITE_TAGLINE = "Your Treasure Coast, every day."

# Sources that are paywalled or provide minimal content — skip article text fetching
# and cap hero urgency scores to deprioritize them for hero selection
THIN_SOURCE_DOMAINS = ["tcpalm.com", "sun-sentinel.com", "palmbeachpost.com"]

# Sources we can usually use for full article text. TCPalm stays discovery-only
# because its pages are paywalled and tend to produce thin/blocked extraction.
FULL_TEXT_DOMAINS = ["wptv.com", "wpbf.com", "cbs12.com", "wflx.com", "hometownnewstc.com", "floridapolitics.com"]

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Populated once per run by classify_stories(); {headline_lower: set(category_keys)}.
# None means classification unavailable -> keyword filtering is used instead.
STORY_CLASSIFICATION = None

# Model selection — flip these to switch the whole pipeline between tiers.
# TEST: running everything on Sonnet to evaluate article quality vs Haiku.
MODEL_ARTICLES = "claude-sonnet-4-5"   # article generation, enrichment, ranking, rewrites
MODEL_SELECTION = "claude-sonnet-4-5"  # hero selection, structural decisions

# Content bank — loaded once at startup, used for card enrichment
CONTENT_BANK_FEEDS = [
    "https://www.wptv.com/news/local-news.rss",
    "https://www.wptv.com/news/education/back-to-school.rss",
    "https://www.wptv.com/news/state.rss",
    "https://www.wptv.com/feeds/rss/news",
    "https://www.wptv.com/feeds/rss/local",
    "https://news.google.com/rss/search?q=treasure+coast+florida+when:3d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=martin+county+florida+when:3d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=port+st+lucie+florida+when:3d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=vero+beach+florida+when:3d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=fort+pierce+florida+when:3d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=stuart+florida+news+when:3d&hl=en-US&gl=US&ceid=US:en",
]
# Image bank — local Florida outlets
IMAGE_BANK_FEEDS = [
    "https://www.wptv.com/news/local-news.rss",
    "https://www.wptv.com/news/education/back-to-school.rss",
    "https://www.wptv.com/news/state.rss",
    "https://www.wptv.com/news/region-martin-county.rss",
    "https://www.wptv.com/news/region-st-lucie-county.rss",
    "https://www.wptv.com/news/region-indian-river-county.rss",
    "https://www.wptv.com/news/good-news.rss",
    "https://news.google.com/rss/search?q=treasure+coast+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=martin+county+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=port+st+lucie+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=vero+beach+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=florida+news+when:1d&hl=en-US&gl=US&ceid=US:en",
]
FEED_PUBLISHER_MAP = {
    "tcpalm.com":        "TCPalm",
    "wptv.com":          "WPTV",
    "wpbf.com":          "WPBF",
    "cbs12.com":         "CBS12",
    "sun-sentinel.com":  "Sun Sentinel",
    "palmbeachpost.com": "Palm Beach Post",
    "hometownnewstc.com":"Hometown News",
    "wflx.com":          "Fox 29",
    "bbci.co.uk":        "BBC News",
    "npr.org":           "NPR",
    "yahoo.com":         "Yahoo News",
    "apnews.com":        "AP News",
    "reuters.com":       "Reuters",
    "usatoday.com":      "USA Today",
    "cnn.com":           "CNN",
    "nbcnews.com":       "NBC News",
}

def get_image_credit(source_url):
    """Return a clean publisher name from a feed URL. Returns empty string if unknown."""
    if not source_url:
        return ""
    source_lower = source_url.lower()
    for domain, name in FEED_PUBLISHER_MAP.items():
        if domain in source_lower:
            return name
    return ""


# Local fallback images — /images/fallback/ in repo
FALLBACK_IMAGE_MAP = {
    "local_gov":    ["local_gov-1.jpg",    "local_gov-2.jpg",    "local_gov-3.jpg"],
    "crime":        ["crime-1.jpg",        "crime-2.jpg",        "crime-3.jpg"],
    "business":     ["business-1.jpg",     "business-2.jpg",     "business-3.jpg"],
    "sports":       ["sports-1.jpg",       "sports-2.jpg",       "sports-3.jpg"],
    "things_to_do": ["things_to_do-1.jpg", "things_to_do-2.jpg", "things_to_do-3.jpg"],
    "florida":      ["florida-1.jpg",      "florida-2.jpg",      "florida-3.jpg"],
    "martin":       ["martin-1.jpg",       "martin-2.jpg",       "martin-3.jpg"],
    "st_lucie":     ["st_lucie-1.jpg",     "st_lucie-2.jpg",     "st_lucie-3.jpg"],
    "indian_river": ["indian_river-1.jpg", "indian_river-2.jpg", "indian_river-3.jpg"],
    "top_news":     ["local_gov-1.jpg",    "crime-1.jpg",        "business-1.jpg"],
}

# Tracks how many times each category's fallback has been used this run,
# so fallbacks cycle sequentially instead of repeating.
_FALLBACK_ROTATION = {}

def get_fallback_image(category_key, headline="", sequential=False):
    base_names = FALLBACK_IMAGE_MAP.get(category_key, FALLBACK_IMAGE_MAP["top_news"])
    available = []
    for base in base_names:
        stem = base.rsplit(".", 1)[0]
        for ext in ["jpg", "jpeg", "png", "webp"]:
            path = OUTPUT_DIR / "images" / "fallback" / f"{stem}.{ext}"
            if path.exists():
                available.append(f"{stem}.{ext}")
                break
    if not available:
        return "", ""
    if sequential:
        # Cycle through available images in order per category
        n = _FALLBACK_ROTATION.get(category_key, 0)
        idx = n % len(available)
        _FALLBACK_ROTATION[category_key] = n + 1
    else:
        seed = headline or category_key or "top_news"
        idx  = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(available)
    return f"{SITE_URL}/images/fallback/{available[idx]}", "Treasure Coast Today"

def upscale_image_url(url):
    """Upscale BBC CDN images by replacing the size segment with 1024."""
    if not url or "ichef.bbci.co.uk" not in url:
        return url
    return re.sub(r"/\d{2,3}/", "/1024/", url, count=1)


def extract_image(entry):
    """Try every known location for an image in an RSS entry."""
    def valid(u):
        if not u or len(u) < 15: return False
        return not any(x in u.lower() for x in ["1x1","pixel","spacer","tracking","data:"])
    for t in (getattr(entry,"media_thumbnail",None) or []):
        if isinstance(t,dict) and valid(t.get("url","")): return upscale_image_url(t["url"])
    for m in (getattr(entry,"media_content",None) or []):
        if not isinstance(m,dict): continue
        u = m.get("url","")
        if valid(u) and ("image" in m.get("type","") or any(u.lower().endswith(e) for e in (".jpg",".jpeg",".png",".webp"))): return upscale_image_url(u)
    for enc in (getattr(entry,"enclosures",None) or []):
        if isinstance(enc,dict) and "image" in enc.get("type",""):
            u = enc.get("href",enc.get("url",""))
            if valid(u): return u
    html = ""
    for field in ["description","summary"]:
        val = entry.get(field,"") or getattr(entry,field,"")
        if isinstance(val,list) and val:
            html = val[0].get("value","") if isinstance(val[0],dict) else str(val[0])
        elif isinstance(val,str):
            html = val
        if html: break
    for match in re.finditer(r'<img[^>]+src=["\']([^"\']{20,})["\']', html):
        u = match.group(1)
        if valid(u): return u
    return ""


def extract_publisher_url(entry):
    """Extract actual publisher URL from a Google News RSS entry."""
    link = entry.get("link", "") or getattr(entry, "link", "")
    if "news.google.com" not in link:
        return link
    for field in ["summary", "description"]:
        val = entry.get(field, "") or getattr(entry, field, "")
        if isinstance(val, list) and val:
            html = val[0].get("value", "") if isinstance(val[0], dict) else str(val[0])
        elif isinstance(val, str):
            html = val
        else:
            continue
        matches = re.findall(r'href=["\']?(https?://(?!news\.google)[^"\'>]+)', html)
        if matches:
            return matches[0]
    return link


def sanitize_text(text):
    if not text: return ""
    return text.replace("\\", " ").replace('"', "'").replace("\n", " ").replace("\r", " ").replace("\t", " ").strip()



def fetch_og_image(url):
    """Fetch an article page and extract its og:image (or twitter:image) meta tag.
    This is the most reliable image source because it comes from the article itself,
    guaranteeing the image actually matches the story. Returns "" on any failure."""
    if not url:
        return ""
    try:
        import re as _re_og
        resp = requests.get(url, timeout=10,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; TCTBot/1.0)"})
        if resp.status_code != 200:
            return ""
        html = resp.text[:200000]  # only need the <head>
        # Try og:image then twitter:image, in either attribute order
        patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        ]
        for pat in patterns:
            m = _re_og.search(pat, html, _re_og.IGNORECASE)
            if m:
                img = m.group(1).strip()
                if img.startswith("http"):
                    return img
        return ""
    except Exception:
        return ""



_EVENT_LINK_CACHE = {}


def _event_link_root_host(host):
    host = (host or "").lower().split(":", 1)[0].strip(".")
    parts = [p for p in host.split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def find_official_event_link(source_url, headline=""):
    """Find a high-confidence official event/ticket/registration link in a source page.

    The source article itself is never returned. Only real hrefs present on that page
    are considered; no URL is guessed or fabricated. Low-confidence results are omitted.
    """
    if not source_url or not source_url.startswith("http"):
        return "", ""
    cache_key = (source_url, headline)
    if cache_key in _EVENT_LINK_CACHE:
        return _EVENT_LINK_CACHE[cache_key]

    try:
        from urllib.parse import urljoin, urlparse, parse_qs, unquote
        import html as _html

        resp = requests.get(
            source_url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TCTBot/1.0)"},
        )
        if resp.status_code != 200:
            _EVENT_LINK_CACHE[cache_key] = ("", "")
            return "", ""

        source_host = urlparse(source_url).netloc.lower().replace("www.", "")
        source_root = _event_link_root_host(source_host)
        page = resp.text[:600000]
        candidates = []
        stops = {
            "this", "that", "with", "from", "will", "your", "about", "event",
            "events", "week", "weekend", "local", "florida", "treasure", "coast",
        }
        headline_tokens = {
            w for w in re.findall(r"[a-z0-9]+", (headline or "").lower())
            if len(w) >= 5 and w not in stops
        }
        blocked_hosts = {
            "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com",
            "linkedin.com", "tiktok.com", "pinterest.com", "google.com", "apple.com",
        }
        preferred_hosts = {
            "eventbrite.com", "ticketmaster.com", "tickets.com", "etix.com",
            "showclix.com", "universe.com", "simpletix.com", "humanitix.com",
        }

        anchor_pattern = r"<a\b[^>]*?href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>"
        for match in re.finditer(anchor_pattern, page, re.IGNORECASE | re.DOTALL):
            href = _html.unescape(match.group(1).strip())
            anchor_html = match.group(2)
            anchor = _html.unescape(re.sub(r"<[^>]+>", " ", anchor_html))
            anchor = re.sub(r"\s+", " ", anchor).strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue

            url = urljoin(source_url, href)
            parsed = urlparse(url)
            host = parsed.netloc.lower().replace("www.", "")
            if _event_link_root_host(host) == source_root:
                query = parse_qs(parsed.query)
                redirect_value = ""
                for key in ("url", "u", "target", "redirect", "destination"):
                    vals = query.get(key)
                    if vals and vals[0].startswith("http"):
                        redirect_value = unquote(vals[0])
                        break
                if redirect_value:
                    url = redirect_value
                    parsed = urlparse(url)
                    host = parsed.netloc.lower().replace("www.", "")

            root = _event_link_root_host(host)
            if not host or root == source_root:
                continue
            if any(root == b or root.endswith("." + b) for b in blocked_hosts):
                continue
            lower_url = url.lower()
            lower_anchor = anchor.lower()
            if any(x in lower_url for x in (
                "/privacy", "/terms", "/contact", "/advertis", "/author/",
                "doubleclick", "googlesyndication", "utm_source=syndication",
            )):
                continue

            score = 0
            if root in preferred_hosts:
                score += 7
            if host.endswith(".gov") or root.endswith(".gov"):
                score += 5
            elif host.endswith(".org") or root.endswith(".org"):
                score += 3

            if any(term in lower_anchor for term in (
                "official event", "event website", "official website", "visit website",
            )):
                score += 8
            if any(term in lower_anchor for term in (
                "buy tickets", "get tickets", "tickets", "register", "registration",
                "rsvp", "reserve", "sign up",
            )):
                score += 7
            if any(term in lower_anchor for term in (
                "event details", "more information", "learn more", "full schedule",
                "event page", "festival website", "details here",
            )):
                score += 5

            candidate_tokens = set(re.findall(r"[a-z0-9]+", (anchor + " " + url).lower()))
            overlap = len(headline_tokens & candidate_tokens)
            score += min(overlap, 4)

            if score >= 7:
                label = anchor if 3 <= len(anchor) <= 80 else "Visit the official event page"
                if lower_anchor in {"click here", "here", "website", "learn more"}:
                    label = "Visit the official event page"
                candidates.append((score, url, label))

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            _, url, label = candidates[0]
            result = (url, label)
        else:
            result = ("", "")
    except Exception:
        result = ("", "")

    _EVENT_LINK_CACHE[cache_key] = result
    return result


def build_image_bank():
    """Fetch images from RSS feeds that reliably include them (BBC, ESPN, TechCrunch)."""
    bank = []
    for url in IMAGE_BANK_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:60]:
                title = entry.get("title", "").strip()
                img   = extract_image(entry)
                if title and img:
                    bank.append({"title": title, "image_url": img, "source": url})
        except Exception as e:
            print(f"  Image bank feed error ({url[:50]}): {e}")
    print(f"  Image bank built: {len(bank)} entries with images")
    return bank


def match_image(headline, image_bank, cat_key="", used_images=None):
    """Fuzzy-match a headline against the image bank with geographic and category conflict detection."""
    used_images = used_images or set()
    stops = {"that","this","with","from","have","been","after","over","into","says","said","will","than","more","also","when","were","they","their","about"}
    geo_words = {"ukraine","ukrainian","russia","russian","china","chinese","israel","israeli","gaza","iran","iranian",
                 "france","french","germany","german","australia","australian","india","indian","pakistan","pakistani",
                 "korea","korean","japan","japanese","mexico","mexican","brazil","brazilian","cuba","cuban"}

    # Category-to-source mapping — prevent cross-category image mismatches
    cat_source_hints = {
        "sports":       ["sport", "espn"],
        "crime":        ["police", "sheriff", "crime"],
        "local_gov":    ["commission", "council", "government"],
    }
    # Sources that should NOT be used for certain categories
    cat_source_blocks = {
        "local_gov":    [],
        "crime":        [],
        "business":     [],
        "sports":       [],
        "things_to_do": [],
        "florida":      [],
        "martin":       [],
        "st_lucie":     [],
        "indian_river": [],
    }

    def tokens(text):
        return set(w.lower().strip(".,;:()") for w in text.split() if len(w) > 3 and w.lower() not in stops)

    hw = tokens(headline)
    hl_geo = hw & geo_words
    blocked_sources = cat_source_blocks.get(cat_key, [])
    best_score, best_img, best_credit = 0, "", ""

    for entry in image_bank:
        img_url = entry.get("image_url", "")
        if canonical_image_url(img_url) in used_images:
            continue
        source = entry.get("source", "").lower()
        # Block sports images on non-sports categories
        if any(b in source for b in blocked_sources):
            continue
        entry_tokens = tokens(entry["title"])
        overlap = len(hw & entry_tokens)
        if overlap > best_score and overlap >= 3:
            entry_geo = entry_tokens & geo_words
            if hl_geo and entry_geo and not (hl_geo & entry_geo):
                continue
            best_score   = overlap
            best_img     = upscale_image_url(entry["image_url"])
            best_credit  = get_image_credit(entry.get("source", ""))

    # Fallback pass: if no 3-token match, try distinctive long tokens (>=6 chars).
    # Two shared distinctive terms (e.g. "longview"+"mill", "frankie"+"valli") are a
    # confident match even when the rewritten headline shares few common words.
    if not best_img:
        distinctive = {w for w in hw if len(w) >= 7}
        if distinctive:
            for entry in image_bank:
                source = entry.get("source", "").lower()
                if any(b in source for b in blocked_sources):
                    continue
                entry_tokens = {w for w in tokens(entry["title"]) if len(w) >= 7}
                overlap = len(distinctive & entry_tokens)
                if overlap > best_score and overlap >= 3:
                    entry_geo = tokens(entry["title"]) & geo_words
                    if hl_geo and entry_geo and not (hl_geo & entry_geo):
                        continue
                    best_score  = overlap
                    best_img    = upscale_image_url(entry["image_url"])
                    best_credit = get_image_credit(entry.get("source", ""))

    return best_img, best_credit


PLACEHOLDER_URL_PATTERNS = [
    "brand-icons", "brand_icons",
    "default-image", "default_image", "defaultimage",
    "top_image", "top-image",
    "htv_default", "htv-default",
    "news-slate", "news_slate",
    "og-image.png", "og_image.png",
    "eenewslogo", "site-logo", "site_logo",
    "station-logo", "stationlogo",
    "wpec-16x9", "wpbf", "wflx",
    "aolfp/images", "cbsnewsstatic.com/hub",
    "yimg.com/cv/apiv2",
    "foxtv.com/img",
    "gray.tv/gray/arc-fusion-assets",
    "townnews.com/content/tncms/custom",
    "bloximages",
]

def is_placeholder_image(img_url):
    url_lower = img_url.lower()
    return any(pat in url_lower for pat in PLACEHOLDER_URL_PATTERNS)


def find_image(headline, entries):
    """Match headline back to RSS entry for image, link, and publish time."""
    h = headline.lower()[:50]
    for entry in entries:
        t = entry.get("title", "").lower()[:50]
        if h in t or t in h:
            return {
                "image_url": entry.get("image_url", ""),
                "link":      entry.get("link", ""),
                "published": entry.get("published", ""),
            }
    return {"image_url": "", "link": "", "published": ""}


def extract_publisher_url(entry):
    """Extract actual publisher URL from a Google News RSS entry.
    Google News embeds the publisher URL as an href in the description HTML.
    Falls back to entry link for non-Google feeds.
    """
    link = entry.get("link", "")
    if "news.google.com" not in link:
        return link  # Already a direct publisher URL
    desc = entry.get("summary", entry.get("description", ""))
    if isinstance(desc, list):
        desc = desc[0].get("value", "") if desc else ""
    matches = re.findall(r'href="(https?://(?!news\.google)[^"]+)"', desc)
    if matches:
        return matches[0]
    return link


def sanitize_text(text):
    """Remove characters that break JSON parsing."""
    if not text:
        return ""
    return text.replace("\\", " ").replace('"', "'").replace("\n", " ").replace("\r", " ").replace("\t", " ").strip()



def get_domain(url):
    """Return a normalized domain for source classification."""
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def classify_source(link):
    """Classify a source so the writer knows whether it has usable body text."""
    domain = get_domain(link)
    if any(d in domain for d in THIN_SOURCE_DOMAINS):
        return "discovery_only"
    if any(d in domain for d in FULL_TEXT_DOMAINS):
        return "full_source"
    if "news.google.com" in domain or "yahoo.com" in domain:
        return "aggregator"
    return "unknown"


def extract_rss_text(entry):
    """Prefer the richest text field in an RSS entry."""
    best = ""
    for field in ["content", "summary", "description"]:
        val = entry.get(field, "") or getattr(entry, field, "")
        if isinstance(val, list) and val:
            candidate = val[0].get("value", "") if isinstance(val[0], dict) else str(val[0])
        elif isinstance(val, str):
            candidate = val
        else:
            candidate = ""
        candidate = clean_summary(candidate)
        if len(candidate) > len(best):
            best = candidate
    return best


def clean_summary(text):
    """Strip navigation text, bylines, HTML tags, and noise from RSS summaries."""
    if not text:
        return ""
    import re as _re
    # Remove HTML tags
    text = _re.sub(r"<[^>]+>", " ", text)
    # Remove URLs
    text = _re.sub(r"https?://\S+", "", text)
    # Remove common RSS noise patterns
    noise_patterns = [
        r"(?i)read more.*$",
        r"(?i)click here.*$",
        r"(?i)continue reading.*$",
        r"(?i)\[\+\d+ chars\].*$",
        r"(?i)^by [A-Z][a-z]+ [A-Z][a-z]+",
        r"(?i)related articles?:.*$",
        r"(?i)also read:.*$",
        r"(?i)share this:.*$",
        r"(?i)follow us.*$",
        r"&amp;|&lt;|&gt;|&quot;|&#\d+;",
    ]
    for pattern in noise_patterns:
        text = _re.sub(pattern, "", text, flags=_re.MULTILINE)
    # Remove characters that break JSON parsing
    text = text.replace("\\", " ").replace('"', "'").replace("\n", " ").replace("\r", " ").replace("\t", " ")
    # Collapse whitespace
    text = _re.sub(r"\s+", " ", text).strip()
    return text


def fetch_headlines(feeds, limit=HEADLINES_PER_CATEGORY, feed_cache=None):
    """Pull headlines, dedupe, fetch usable full article text for open sources, then limit."""

    def fetch_one_feed(url):
        # Use cache if available
        if feed_cache is not None and url in feed_cache:
            return url, feed_cache[url]
        try:
            import socket
            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(8)
            feed = feedparser.parse(url)
            socket.setdefaulttimeout(old_timeout)
            return url, feed.entries
        except Exception as e:
            print(f"  Feed error ({url[:60]}): {e}")
            return url, []

    # Fetch all feeds in parallel — a slow/blocked feed won't stall the others
    feed_results = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(fetch_one_feed, url): url for url in feeds}
        try:
            for fut in as_completed(futures, timeout=25):
                try:
                    url, feed_entries = fut.result(timeout=10)
                    feed_results.append((url, feed_entries))
                except Exception as e:
                    print(f"  Feed timeout ({futures[fut][:60]}): {e}")
        except (FuturesTimeoutError, TimeoutError):
            for f in futures:
                f.cancel()

    seen, entries = set(), []

    # Obituary signals — filter these out entirely so they never become heroes
    # OR cards. Specific to obituary/funeral listings; won't catch news coverage
    # of notable deaths (which uses "dies", "killed", "death of" without this language).
    _OBIT_SIGNALS = [
        "survived by", "is survived by", "funeral home", "funeral & cremation",
        "funeral and cremation", "cremation service", "cremation services",
        "celebration of life", "laid to rest", "in lieu of flowers",
        "visitation will", "visitation is", "services are being handled",
        "services being handled", "arrangements by", "arrangements are",
        "arrangements entrusted", "passed away peacefully", "passed away at",
        "entered into rest", "went to be with the lord", "obituary", "obituaries",
    ]

    def _is_obituary(title, summary):
        blob = (title + " " + (summary or "")).lower()
        return any(sig in blob for sig in _OBIT_SIGNALS)

    for url, feed_entries in feed_results:
        try:
            for entry in feed_entries[:15]:
                title = sanitize_text(entry.get("title", "").strip())
                if not title or title.lower() in seen:
                    continue
                seen.add(title.lower())

                link = extract_publisher_url(entry)
                summary = extract_rss_text(entry)[:2500]

                # Skip obituaries entirely
                if _is_obituary(title, summary):
                    continue

                source_type = classify_source(link)

                entries.append({
                    "title":       title,
                    "summary":     summary,
                    "link":        link,
                    "feed_url":    url,
                    "source_type": source_type,
                    "source_quality": "unclassified",
                    "image_url":   extract_image(entry),
                    "published":   entry.get("published", "") or entry.get("updated", ""),
                })
        except Exception as e:
            print(f"  Feed error ({url[:60]}): {e}")

    # Sort by published date (freshest first), then fetch bodies for the candidate pool.
    def pub_sort(h):
        try:
            from email.utils import parsedate_to_datetime
            from datetime import timezone
            return parsedate_to_datetime(h["published"]).astimezone(timezone.utc).timestamp()
        except Exception:
            return 0

    entries.sort(key=pub_sort, reverse=True)
    result = entries[:limit]

    def enrich_one(h):
        link = h.get("link", "")
        summary_words = len((h.get("summary") or "").split())

        # Never try to turn paywalled/discovery sources into full articles.
        if h.get("source_type") == "discovery_only":
            h["source_quality"] = "discovery_only"
            return h

        # Google News aggregators — treat as brief minimum, don't penalize
        if h.get("source_type") == "aggregator":
            h["source_quality"] = "brief" if summary_words >= 20 else "thin"
            return h

        # Try full body extraction for open/local sources.
        if h.get("source_type") == "full_source" and link:
            # 2500 words: high enough that truncation effectively never cuts a normal
            # article (even long investigations and listicles, whose ranked items come
            # last). The cap exists only to guard against a pathologically long or
            # junk-filled scraped page, not to save tokens — the savings were pennies and
            # the cost was dropping the exact facts the article is about.
            full = fetch_article_text(link, max_words=2500)
            if full and len(full.split()) >= 140:
                h["article_text"] = full
                h["source_quality"] = "full"
                return h
            # Scrape failed or was blocked (e.g. WPTV returns 403 to bots). Many
            # full_source feeds embed the ENTIRE article in the RSS content:encoded
            # field, which extract_rss_text already captured into summary. Analysis of
            # the WPTV feed shows bodies of 66-1349 words, all complete articles — the
            # short ones are legitimate brief news items (a fatal crash, a fire report),
            # not truncated snippets. Use the embedded text directly when it is a real
            # body (60+ words) rather than discarding the story as thin. This is what
            # keeps WPTV county stories alive.
            if summary_words >= 60:
                h["article_text"] = h.get("summary", "")
                h["source_quality"] = "full"
                return h

        # Fallback quality labels based on actual RSS text depth.
        if summary_words >= 140:
            h["source_quality"] = "summary"
        elif summary_words >= 40:
            h["source_quality"] = "brief"
        else:
            h["source_quality"] = "thin"
        return h

    # Keep this parallel and bounded; otherwise a few slow publisher pages can stall the run.
    try:
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = [ex.submit(enrich_one, h) for h in result]
            for fut in as_completed(futures, timeout=45):
                try:
                    fut.result(timeout=1)
                except Exception:
                    pass
    except Exception:
        # If the timeout trips, use whatever was enriched so far.
        pass

    full_count = sum(1 for h in result if h.get("source_quality") == "full")
    summary_count = sum(1 for h in result if h.get("source_quality") in ("summary", "brief"))
    discovery_count = sum(1 for h in result if h.get("source_quality") == "discovery_only")
    print(f"  Source quality: {full_count} full, {summary_count} summary/brief, {discovery_count} discovery-only, {len(result)} total")


    return result


# Category relevance filtering for broad feeds.
# This is intentionally conservative: it promotes clearly on-topic stories, but
# falls back to the unfiltered pool if a section would otherwise go thin.
def _text_for_category_match(h):
    return " ".join([
        h.get("title", ""),
        h.get("headline", ""),
        h.get("summary", ""),
        h.get("teaser", ""),
        h.get("body", "")[:1200],
        h.get("article_text", "")[:1200],
    ]).lower()


def _has_any(text, terms):
    return any(term in text for term in terms)

def _story_locality_blob(item):
    return " ".join([
        item.get("source_title", ""),
        item.get("title", ""),
        item.get("headline", ""),
        item.get("summary", ""),
        item.get("source_summary", ""),
        item.get("teaser", ""),
        item.get("body", "")[:1800],
        item.get("article_text", "")[:1800],
    ]).lower()

def _strip_quoted_phrases(text):
    # Place names inside entertainment titles do not establish geography.
    text = re.sub(r'"[^"\n]{1,200}"', " ", text or "")
    text = re.sub(r"'[^'\n]{1,200}'", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def _trusted_county_feed(category_key, item):
    feed_url = (item.get("feed_url", "") or "").lower()
    trusted_hints = {
        "martin": "wptv.com/news/region-martin-county.rss",
        "st_lucie": "wptv.com/news/region-st-lucie-county.rss",
        "indian_river": "wptv.com/news/region-indian-river-county.rss",
    }
    return trusted_hints.get(category_key, "") in feed_url

def _county_locality_evidence(category_key, item):
    """Require real geographic evidence, not a person's name or title word."""
    raw = _story_locality_blob(item)
    unquoted = _strip_quoted_phrases(raw)

    strong_places = {
        "martin": [
            "martin county", "jensen beach", "palm city", "hobe sound",
            "port salerno", "jupiter island", "indiantown", "sewall's point",
            "sewalls point",
        ],
        "st_lucie": [
            "st. lucie county", "st lucie county", "port st. lucie",
            "port st lucie", "fort pierce", "st. lucie west", "st lucie west",
        ],
        "indian_river": [
            "indian river county", "vero beach", "fellsmere", "wabasso",
            "gifford", "sebastian inlet", "sebastian river",
        ],
    }
    if _has_any(unquoted, strong_places.get(category_key, [])):
        return True

    entertainment_context = _has_any(raw, [
        "tv show", "television show", "television series", "streaming series",
        "series premiere", "season premiere", "episode", "film", "movie",
        "character", "actor", "actress", "sitcom", "debuts this week",
        "save the universe",
    ])

    contextual_patterns = {
        "martin": [
            r"\bstuart,?\s+(?:florida|fla\.?|fl)\b",
            r"\b(?:in|near|around|outside|north of|south of|east of|west of)\s+stuart\b",
            r"\bcity of stuart\b",
            r"\bstuart\s+(?:police|fire rescue|city commission|city hall|airport|"
            r"high school|middle school|elementary|hospital|bridge|road|street|"
            r"residents?|officials?|business|restaurant|home|man|woman|family)\b",
            r"\b(?:downtown|police in|officials in|residents of)\s+stuart\b",
        ],
        "indian_river": [
            r"\bsebastian,?\s+(?:florida|fla\.?|fl)\b",
            r"\b(?:in|near|around|outside|north of|south of)\s+sebastian\b",
            r"\bcity of sebastian\b",
            r"\bsebastian\s+(?:police|city council|city hall|river|inlet|"
            r"residents?|officials?|business|restaurant|home|man|woman|family)\b",
        ],
    }
    if any(re.search(p, unquoted, re.IGNORECASE) for p in contextual_patterns.get(category_key, [])):
        return True

    # Dedicated publisher county feeds can establish locality when a short title omits
    # the city. Search feeds do not count, and entertainment-title content is blocked.
    if _trusted_county_feed(category_key, item) and not entertainment_context:
        return True
    return False

def _has_treasure_coast_locality(item):
    raw = _strip_quoted_phrases(_story_locality_blob(item))
    return "treasure coast" in raw or any(
        _county_locality_evidence(key, item) for key in COUNTY_KEYS
    )


# Publication quality gates. A category can fall back to older real reporting, but
# a thin RSS blurb must never be expanded into a fake-looking article or promoted
# merely to keep a section populated.
MIN_HERO_BODY_WORDS = 120
MIN_CARD_BODY_WORDS = 90
MIN_SOURCE_WORDS = 80

def _word_count(text):
    return len(re.findall(r"\b[\w'-]+\b", text or ""))

def _paragraph_count(text):
    return len([p for p in re.split(r"\n\s*\n", text or "") if p.strip()])

def _sentence_count(text):
    return len([s for s in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if s.strip()])

def _source_word_count(item):
    try:
        stored = int(item.get("source_word_count", 0) or 0)
    except Exception:
        stored = 0
    if stored:
        return stored
    source_text = item.get("article_text", "") or item.get("source_summary", "") or item.get("summary", "")
    return _word_count(source_text)

def _source_candidate_publishable(item):
    """Require enough verified source material before Claude writes anything.

    This runs before category generation, so a thin RSS blurb cannot become a hero,
    card, permalink, or even consume article-generation tokens. Archive recovery fills
    the section when the live source pool is too thin.
    """
    if not item or not item.get("title"):
        return False
    quality = (item.get("source_quality", "") or "").lower()
    if quality not in {"full", "summary"}:
        return False
    return _source_word_count(item) >= MIN_SOURCE_WORDS

def _publishable_article(item, hero=False):
    """Return True only when an item is substantial enough for a permalink.

    Custom/manual articles and active weather alerts remain editorial exceptions.
    Automated feed stories must have a real source, enough verified source material,
    and enough finished copy to stand alone as an article.
    """
    if not item or not item.get("headline"):
        return False
    if item.get("is_custom") or item.get("is_weather_alert"):
        return True
    if item.get("_section_placeholder"):
        return False
    if item.get("_archive_only"):
        return bool(item.get("_archive_verified_quality"))

    quality = (item.get("source_quality", "") or "").lower()
    if quality in {"thin", "brief", "discovery_only"}:
        return False

    body = (item.get("body", "") or "").strip()
    min_words = MIN_HERO_BODY_WORDS if hero else MIN_CARD_BODY_WORDS
    if _word_count(body) < min_words:
        return False
    # Prefer real paragraph structure, but allow a well-developed single paragraph
    # with at least five factual sentences.
    if _paragraph_count(body) < 2 and _sentence_count(body) < 5:
        return False

    source_words = _source_word_count(item)
    if source_words < MIN_SOURCE_WORDS:
        return False
    return True

def _archive_article_metrics(entry):
    """Get body depth for an archived page, reading legacy HTML when needed."""
    try:
        wc = int(entry.get("article_word_count", 0) or 0)
        pc = int(entry.get("article_paragraph_count", 0) or 0)
    except Exception:
        wc, pc = 0, 0
    if wc:
        return wc, pc

    slug = entry.get("slug", "")
    if not slug:
        return 0, 0
    path = OUTPUT_DIR / "articles" / f"{slug}.html"
    try:
        html_text = path.read_text(encoding="utf-8", errors="ignore")
        match = re.search(
            r'<div class="article-body">(.*?)</div>\s*<div class="article-share">',
            html_text, re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return 0, 0
        body_html = match.group(1)
        pc = len(re.findall(r"<p(?:\s[^>]*)?>", body_html, re.IGNORECASE))
        import html as _html
        plain = _html.unescape(re.sub(r"<[^>]+>", " ", body_html))
        wc = _word_count(plain)
        entry["article_word_count"] = wc
        entry["article_paragraph_count"] = pc
        return wc, pc
    except Exception:
        return 0, 0

def _archive_article_body(entry):
    """Return the existing full article body as plain paragraphs for hero previews."""
    slug = entry.get("slug", "")
    if not slug:
        return ""
    path = OUTPUT_DIR / "articles" / f"{slug}.html"
    try:
        html_text = path.read_text(encoding="utf-8", errors="ignore")
        match = re.search(
            r'<div class="article-body">(.*?)</div>\s*<div class="article-share">',
            html_text, re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return ""
        body_html = match.group(1)
        body_html = re.sub(r"</p>", "\n\n", body_html, flags=re.IGNORECASE)
        body_html = re.sub(r"</h[2-4]>", "\n\n", body_html, flags=re.IGNORECASE)
        import html as _html
        plain = _html.unescape(re.sub(r"<[^>]+>", " ", body_html))
        plain = re.sub(r"[ \t]+", " ", plain)
        plain = re.sub(r"\n\s*\n+", "\n\n", plain)
        return plain.strip()
    except Exception:
        return ""

def _archive_entry_publishable(entry):
    if entry.get("is_custom"):
        return True
    wc, pc = _archive_article_metrics(entry)
    return wc >= MIN_HERO_BODY_WORDS and (pc >= 2 or wc >= 180)


# Hero selection is stricter than card inclusion. Cards may use softer fallback
# logic to keep a section populated, but a section lead must clearly belong to
# that section.
def _hero_eligible(category_key, h):
    text = _text_for_category_match(h)
    title = (h.get("title", "") or "").lower()
    quality = h.get("source_quality", "")

    if quality in {"thin", "brief", "discovery_only"}:
        return False


    # LLM classification is a positive signal, never a bypass around deterministic
    # locality/topic safety rules. The previous early return here meant that one bad
    # classifier label skipped every outside-area block and hard negative below.
    _classified_cats = None
    if STORY_CLASSIFICATION is not None:
        # Look up by the ORIGINAL RSS title first. Generated heroes/cards carry it in
        # source_title; raw feed items have it in title. The rewritten headline is a
        # last resort — it will usually miss, since the map is keyed on RSS titles.
        for _key in (
            (h.get("source_title", "") or "").lower(),
            title,
            (h.get("headline", "") or "").lower(),
        ):
            if not _key:
                continue
            cats = STORY_CLASSIFICATION.get(_key)
            if cats is not None:
                _classified_cats = cats
                break
        if _classified_cats == {"none"}:
            return False

    # Outside-coverage-area block: WPTV serves Palm Beach County and the wider
    # South Florida market, which is NOT the Treasure Coast. If a story is clearly
    # about a place outside Martin/St. Lucie/Indian River counties AND does not
    # mention any Treasure Coast location, it should never be a hero.
    _outside_places = [
        "palm beach", "west palm", "riviera beach", "delray beach", "boca raton",
        "boynton beach", "lake worth", "jupiter", "juno beach", "north palm beach",
        "wellington", "royal palm", "belle glade", "pahokee", "greenacres",
        "westlake", "loxahatchee", "palm beach gardens", "lake park", "mangonia",
        "haverhill", "atlantis", "lantana", "manalapan", "south bay", "glades",
        "miami", "fort lauderdale", "broward", "okeechobee", "orlando", "tampa",
        "jacksonville", "gainesville", "naples", "sarasota", "fort myers",
        "kissimmee", "daytona", "melbourne", "cocoa", "brevard", "st. augustine",
    ]
    _treasure_coast_places = [
        "martin county", "st. lucie", "st lucie", "indian river", "treasure coast",
        "stuart", "jensen beach", "palm city", "hobe sound", "port salerno",
        "port st. lucie", "port st lucie", "fort pierce", "vero beach", "sebastian",
        "fellsmere", "indiantown", "jupiter island", "hutchinson island",
    ]
    _has_outside = any(p in text for p in _outside_places)
    _has_local   = _has_treasure_coast_locality(h)
    # Florida is the statewide section, so Tampa/Orlando/etc. are valid there.
    # Every other section is Treasure Coast-local and must reject an outside-only story.
    if category_key != "florida" and _has_outside and not _has_local:
        return False

    # Universal obituary block — obituaries should NEVER be a hero in any section,
    # including county pages. This is specific to obituary listings (funeral home
    # references, "survived by") and won't catch news coverage of notable deaths,
    # which uses "dies", "killed", "death of" without funeral-listing language.
    _obit_signals = ["survived by", "is survived by", "funeral home",
                     "funeral and cremation", "cremation service", "memorial service at",
                     "laid to rest", "celebration of life", "visitation will",
                     "in lieu of flowers", "services are being handled",
                     "services being handled", "arrangements by", "arrangements are"]
    if any(sig in text for sig in _obit_signals):
        return False

    topic_terms = {
        "local_gov": ["commission", "commissioner", "city council", "county council", "school board", "zoning", "rezoning", "ordinance", "budget", "tax", "millage", "mayor", "public meeting", "vote", "approved", "approval", "proposal", "hearing", "development order", "planning", "public policy", "ban", "takes effect", "school district", "superintendent", "principal", "education", "student", "teacher", "curriculum", "school closure", "school merger"],
        "crime": ["arrest", "arrested", "charged", "charges", "sheriff", "police", "deputies", "deputy", "officer", "shooting", "stabbed", "stabbing", "homicide", "murder", "crash", "fatal", "killed", "injured", "fire rescue", "missing", "suspect", "victim", "jail", "court", "public safety", "fraud", "burglary", "robbery"],
        "business": ["business", "development", "developer", "real estate", "housing", "restaurant", "store", "retail", "mall", "company", "jobs", "hiring", "economic", "economy", "construction", "project", "commercial", "warehouse", "factory", "plant", "opening", "closing", "closes", "expansion", "wawa", "publix", "downtown", "permit", "property", "market", "walmart", "campbell soup"],
        "sports": ["sports", "football", "basketball", "baseball", "softball", "soccer", "volleyball", "tennis", "golf", "lacrosse", "wrestling", "track", "cross country", "swimming", "game", "score", "win", "wins", "won", "loss", "defeats", "beats", "championship", "playoff", "tournament", "athlete", "coach", "team", "mets", "st. lucie mets", "st lucie mets"],
        "things_to_do": ["event", "events", "festival", "concert", "show", "weekend", "things to do", "restaurant", "food", "arts", "art", "music", "theater", "theatre", "park", "market", "farmers market", "fair", "fundraiser", "community", "parade", "holiday", "museum", "exhibit", "taste", "family-friendly", "activities"],
        "florida": ["florida", "statewide", "state of florida", "insurance", "property insurance", "homeowners insurance", "hurricane", "tropical storm", "weather", "storm", "flooding", "law takes effect", "takes effect", "new law", "new laws", "gas prices", "cost of living", "utility", "utilities", "fpl", "electric bill", "toll", "beaches", "red tide", "environment", "manatee", "everglades", "housing", "rent", "sinkhole", "evacuation", "desantis", "legislature", "lawmakers", "state law", "florida supreme court", "medicaid", "schools statewide", "springs", "wildlife", "boating", "fishing", "tourism", "state park"],
    }

    # Block obituary listings (non-notable individuals) but not news coverage of notable deaths.
    # Terms like "obituary", "survived by", "funeral home" only appear in obit listings —
    # news coverage of notable deaths uses "dies", "killed", "death of" which we allow.
    obit_terms = ["obituary", "obituaries", "survived by", "is survived by",
                  "funeral home", "in memoriam", "memorial service at",
                  "laid to rest", "celebration of life"]

    hard_negatives = {
        "sports":       ["sues", "lawsuit", "campbell soup", "spaghettios", "worms", "walmart",
                         "fertilizer", "ban", "commission", "politics", "arrest", "charged",
                         "shooting", "homicide", "murder", "missing", "fatal crash", "zoning",
                         "ordinance", "budget", "tax", "city council", "county council",
                         "restaurant opens", "business opens", "store opens", "new store",
                         "house fire", "died", "death", "dead", "killed", "fundraiser",
                         "gofundme", "fire broke out", "passed away", "fatal"] + obit_terms,
        "business":     ["shooting", "homicide", "murder", "missing", "fatal crash",
                         "arrest", "arrested", "charged", "stabbing", "robbery", "burglary",
                         "meth", "methamphetamine", "cocaine", "fentanyl", "heroin",
                         "narcotics", "drug bust", "drug trafficking", "trafficking",
                         "seizes", "seized", "dea", "smuggling", "cartel", "overdose",
                         "game recap", "score", "wins over", "defeats", "beats", "championship",
                         "playoff", "tournament", "festival", "concert", "parade"] + obit_terms,
        "crime":        ["restaurant", "business opens", "store opens", "new store", "hiring",
                         "festival", "concert", "event", "game recap", "score", "wins", "defeats",
                         "zoning", "ordinance", "budget vote", "commission vote", "development order"],
        "things_to_do": ["shooting", "homicide", "murder", "fatal crash", "arrest", "charged",
                         "stabbing", "robbery", "burglary", "zoning", "ordinance", "budget",
                         "tax", "lawsuit", "commission vote"] + obit_terms,
        "local_gov":    ["concert", "festival", "game recap", "score", "wins over", "defeats",
                         "arrest", "shooting", "homicide", "murder",
                         "governor debate", "gop debate", "primary debate", "gubernatorial",
                         "for governor", "for senate", "for congress", "governor's race",
                         "governor race", "senate race", "reelection campaign", "gop primary",
                         "democratic primary", "primary challenger", "skips debate",
                         "campaign trail", "poll shows", "leads in poll", "debate stage",
                         "presidential", "white house", "congress passes", "u.s. house",
                         "u.s. senate", "byron donalds", "desantis"] + obit_terms,
        "florida":      ["game recap", "score", "wins over", "defeats", "beats",
                         "world cup", "soccer", "nfl", "nba", "super bowl"] + obit_terms,
        "martin":       [],
        "st_lucie":     [],
        "indian_river": [],
    }

    if category_key in COUNTY_KEYS:
        return _county_locality_evidence(category_key, h)

    if category_key in topic_terms:
        if _has_any(text, hard_negatives.get(category_key, [])):
            return False
        # Block national / global syndicated filler that has no local hook. WPTV and
        # other feeds carry survey/study/ranking pieces ("Study finds Gen X most
        # trusted...") that match a category on a loose word (e.g. "vote of
        # confidence" hitting local_gov's "vote"). These have international or
        # nationwide scope and no Treasure Coast connection. For non-Florida topic
        # categories, block a story that shows clear national/global scope AND names
        # no local place.
        if category_key != "florida":
            _tc_anchor = [
                "martin county", "st. lucie", "st lucie", "indian river", "treasure coast",
                "stuart", "jensen beach", "palm city", "hobe sound", "port salerno",
                "port st. lucie", "port st lucie", "fort pierce", "vero beach", "sebastian",
                "fellsmere", "indiantown", "jupiter island", "hutchinson island",
                "florida",
            ]
            _national_scope = [
                "across 15 countries", "countries", "nationwide", "across america",
                "american drivers", "americans", "global study", "worldwide", "u.k.",
                "united states", "across the country", "national survey", "study finds",
                "survey found", "survey finds", "study found", "ranking of states",
                "50 states", "study reveals", "researchers found", "new study",
            ]
            if _has_any(text, _national_scope) and not _has_any(text, _tc_anchor):
                return False
        # Keep statewide / out-of-area news OUT of local topic categories (it belongs
        # only in Florida). Rather than requiring a local place name in every story
        # (which wrongly drops local stories whose generated body doesn't repeat the
        # town), we only BLOCK stories that came from a statewide feed or clearly
        # reference an out-of-area place with no Treasure Coast connection.
        if category_key != "florida":
            feed_url = (h.get("feed_url", "") or "").lower()
            _tc_places = [
                "martin county", "st. lucie", "st lucie", "indian river", "treasure coast",
                "stuart", "jensen beach", "palm city", "hobe sound", "port salerno",
                "port st. lucie", "port st lucie", "fort pierce", "vero beach", "sebastian",
                "fellsmere", "indiantown", "jupiter island", "hutchinson island",
            ]
            if "state.rss" in feed_url or "floridapolitics" in feed_url:
                # From a statewide feed — only allow if it explicitly names a local place
                if not _has_any(text, _tc_places):
                    return False
            # Hyperlocal topic sections require a Treasure Coast anchor. This blocks
            # national MLB/World Cup/political stories even when the classifier tags
            # them as sports or business.
            if not _has_any(text, _tc_places):
                return False
        if _classified_cats is not None:
            return category_key in _classified_cats
        return _has_any(title, topic_terms[category_key]) or _has_any(text, topic_terms[category_key])

    if _classified_cats is not None:
        return category_key in _classified_cats
    return True


def _category_score(category_key, h):
    text = _text_for_category_match(h)
    title = (h.get("title", "") or "").lower()
    score = 0

    local_places = [
        "treasure coast", "martin county", "st. lucie", "st lucie", "indian river",
        "stuart", "jensen beach", "palm city", "hobe sound", "port salerno",
        "port st. lucie", "port st lucie", "fort pierce", "vero beach",
        "sebastian", "fellsmere", "okeechobee", "jupiter island"
    ]

    county_terms = {
        "martin": ["martin county", "stuart", "jensen beach", "palm city", "hobe sound", "port salerno", "jupiter island"],
        "st_lucie": ["st. lucie", "st lucie", "port st. lucie", "port st lucie", "fort pierce", "st. lucie west", "st lucie west"],
        "indian_river": ["indian river", "vero beach", "sebastian", "fellsmere"],
    }

    positive_terms = {
        "local_gov": [
            "commission", "commissioner", "city council", "county council", "school board",
            "zoning", "rezoning", "ordinance", "budget", "tax", "millage", "mayor",
            "councilman", "councilwoman", "public meeting", "vote", "approved", "approval",
            "proposal", "hearing", "development order", "planning", "public policy"
        ],
        "crime": [
            "arrest", "arrested", "charged", "charges", "sheriff", "police", "deputies",
            "deputy", "officer", "shooting", "stabbed", "stabbing", "homicide", "murder",
            "crash", "fatal", "killed", "injured", "fire rescue", "missing", "suspect",
            "victim", "jail", "court", "public safety", "fraud", "burglary", "robbery"
        ],
        "business": [
            "business", "development", "developer", "real estate", "housing", "restaurant",
            "store", "retail", "mall", "company", "jobs", "hiring", "economic", "economy",
            "construction", "project", "commercial", "warehouse", "factory", "plant",
            "opening", "closing", "closes", "expansion", "wawa", "publix", "downtown",
            "permit", "approved", "zoning", "property", "market"
        ],
                "sports": [
            "sports", "football", "basketball", "baseball", "softball", "soccer", "volleyball",
            "tennis", "golf", "lacrosse", "wrestling", "track", "cross country", "swimming",
            "game", "score", "win", "wins", "won", "loss", "defeats", "beats", "championship",
            "playoff", "tournament", "athlete", "coach", "team", "mets", "st. lucie mets", "st lucie mets"
        ],
        "things_to_do": [
            "event", "events", "festival", "concert", "show", "weekend", "things to do",
            "restaurant", "food", "arts", "art", "music", "theater", "theatre", "park",
            "beach", "market", "farmers market", "fair", "fundraiser", "community", "parade",
            "holiday", "museum", "exhibit", "taste", "family-friendly", "activities"
        ],
        "florida": [
            "florida", "state", "desantis", "legislature", "tallahassee", "supreme court",
            "insurance", "hurricane", "weather", "statewide", "lawmakers", "law", "governor",
            "environment", "economy", "housing", "property insurance"
        ],
    }

    negative_terms = {
        "business": ["shooting", "arrest", "charged", "homicide", "murder", "missing", "crash", "fatal"],
        "sports": ["arrest", "charged", "shooting", "homicide", "murder", "missing", "crash", "politics", "commission", "sues", "lawsuit", "campbell soup", "spaghettios", "worms", "walmart", "fertilizer", "ban"],
        "things_to_do": ["arrest", "charged", "shooting", "homicide", "murder", "fatal crash", "tax", "budget"],
        "local_gov": ["concert", "festival", "restaurant review", "game recap"],
    }

    if category_key in county_terms:
        feed_url = (h.get("feed_url", "") or "").lower()
        county_feed_hints = {
            "martin": "region-martin-county",
            "st_lucie": "region-st-lucie-county",
            "indian_river": "region-indian-river-county",
        }
        title_l = (h.get("title", "") or "").lower()

        # Count mentions of the target county vs other counties
        def _county_mentions(terms):
            return sum(text.count(t) for t in terms)

        target_mentions = _county_mentions(county_terms[category_key])
        other_counties  = {k: v for k, v in county_terms.items() if k != category_key}
        other_mentions  = {k: _county_mentions(v) for k, v in other_counties.items()}
        max_other       = max(other_mentions.values()) if other_mentions else 0
        max_other_key   = max(other_mentions, key=other_mentions.get) if other_mentions else None

        in_target_feed = county_feed_hints.get(category_key, "") in feed_url
        in_other_feed  = any(county_feed_hints.get(k, "___") in feed_url for k in other_counties)

        # HARD BLOCK: if the story is primarily about another county
        # (another county appears in the title, or is mentioned more than the
        # target county, or came from another county's dedicated WPTV feed),
        # it does not belong in this county section.
        target_in_title = _has_any(title_l, county_terms[category_key])
        other_in_title  = any(_has_any(title_l, other_counties[k]) for k in other_counties)

        if other_in_title and not target_in_title:
            return -10  # Clearly about another county
        if in_other_feed and not in_target_feed:
            return -10  # WPTV filed it under another county
        if max_other > target_mentions and target_mentions == 0:
            return -10  # Only mentions other counties, never the target

        # Positive signals for the target county
        if in_target_feed:
            score += 9
        if target_in_title:
            score += 6
        elif target_mentions > 0:
            score += 4
        # Penalize competing county mentions even if target is present
        if max_other > target_mentions:
            score -= 4

        if h.get("source_quality") == "full":
            score += 2
        elif h.get("source_quality") in {"summary", "brief"}:
            score += 1
        return score

    terms = positive_terms.get(category_key, [])
    if terms:
        for term in terms:
            if term in title:
                score += 3
            elif term in text:
                score += 1

    if category_key != "florida" and _has_any(text, local_places):
        score += 2

    if h.get("source_quality") == "full":
        score += 2

    for term in negative_terms.get(category_key, []):
        if term in text:
            score -= 3

    return score


def filter_category_headlines(category_key, headlines, target=HEADLINES_PER_CATEGORY, min_keep=6):
    """Return the best on-topic headlines for a section without blanking weak sections.

    Broad WPTV feeds are useful because they provide full bodies, but they can put crime,
    schools, business, and county stories in the same pool. This layer promotes stories
    that actually match the current section. If the filter would leave too little content,
    it falls back to the original list so Claude still has something to work with.
    """
    if not headlines:
        return headlines

    scored = []
    for h in headlines:
        # Classification-first: when the LLM classified this story, its assignment
        # dominates. Assigned to this category -> strong score. Assigned 'none'
        # (non-local filler) -> excluded entirely. Not in the map -> keyword score.
        if STORY_CLASSIFICATION is not None:
            _cats = STORY_CLASSIFICATION.get((h.get("title", "") or "").lower())
            if _cats is not None:
                if "none" in _cats and len(_cats) == 1:
                    continue  # non-local content, drop from every category
                if category_key in _cats:
                    score = 10  # classified for this category
                else:
                    continue  # classified, but for other categories — skip here
                h["category_match_score"] = score
                h["hero_eligible"] = "yes" if _hero_eligible(category_key, h) else "no"
                scored.append((score, h))
                continue
        score = _category_score(category_key, h)
        h["category_match_score"] = score
        h["hero_eligible"] = "yes" if _hero_eligible(category_key, h) else "no"
        scored.append((score, h))

    # For broad/local categories, require only a weak positive score. The goal is
    # to remove obvious mismatches, not starve the section.
    threshold = 1
    if category_key in {"business", "sports", "things_to_do", "local_gov", "crime"}:
        threshold = 2
    if category_key in {"martin", "st_lucie", "indian_river"}:
        threshold = 2  # Cross-county hard-blocks already prevent bleed; keep this low so counties aren't starved

    filtered = [h for score, h in scored if score >= threshold]
    hero_ready = [h for _, h in scored if h.get("hero_eligible") == "yes"]

    if len(filtered) < min_keep:
        if hero_ready:
            filler = [h for score, h in sorted(scored, key=lambda x: x[0], reverse=True) if h not in hero_ready]
            combined = hero_ready + filler
            print(f"  Category filter: only {len(filtered)} strong matches; preserving {len(hero_ready)} hero-eligible items and filling cards")
            return combined[:target]
        print(f"  Category filter: only {len(filtered)} strong matches and no hero-eligible items; using best scored pool")
        return [h for score, h in sorted(scored, key=lambda x: x[0], reverse=True)][:target]

    filtered.sort(key=lambda h: (h.get("hero_eligible") == "yes", h.get("category_match_score", 0), h.get("source_quality") == "full"), reverse=True)
    print(f"  Category filter: {len(filtered)} on-topic matches from {len(headlines)}; {len(hero_ready)} hero-eligible")
    return filtered[:target]

# -- CLAUDE EDITORIAL ENGINE --

LOCAL_SYSTEM_PROMPT = (
    "You write factual local news articles for Treasure Coast Today, covering Martin, St. Lucie, and Indian River counties in Florida. "
    "Your readers live here. Always prioritize genuinely local stories over state or national ones. "
    "Write in plain direct English. No em dashes. No fluff. No absence language. "
    "Every sentence must be a confirmed fact from the provided source material. "
    "Name specific towns, streets, facilities, and local officials when available. "
    "Towns include: Stuart, Jensen Beach, Palm City, Hobe Sound, Port Salerno, Port St. Lucie, Fort Pierce, Vero Beach, Sebastian, Fellsmere. "
    "Always preserve proper nouns exactly as they appear in the source. "
    "Never fabricate names, numbers, dates, or quotes not in the source. "
    "Never write absence phrases like 'no further details available' or 'details were not disclosed'. "
    "CRITICAL: Never reference your own information, input, or what you were or were not given. Never write "
    "phrases like 'the available information', 'the source does not specify', 'was not detailed', 'not provided', "
    "'not included in the information', or any comment about what you do or do not know. If a specific fact (a name, "
    "a number, a ranked list) is not in the source, simply do not mention that fact at all. Write only what IS "
    "known, as a normal news article would. Never turn a gap in your input into a sentence, and never build "
    "analysis or speculation on top of a missing fact. If you find yourself about to explain what is missing, stop "
    "and omit it entirely. "
    "Always produce a complete, readable article."
)

FLORIDA_SYSTEM_PROMPT = (
    "You write factual news articles for the Florida section of Treasure Coast Today. "
    "This section covers the whole state — legislation, courts, economy, environment, politics, weather, and major events anywhere in Florida. "
    "Do NOT narrow to the Treasure Coast; this is the statewide section. "
    "Write in plain direct English. No em dashes. No fluff. No absence language. "
    "Every sentence must be a confirmed fact from the provided source material. "
    "Never fabricate names, numbers, dates, or quotes not in the source. "
    "Write around missing details — do not reference their absence. "
    "CRITICAL: Never reference your own information, input, or what you were or were not given. Never write "
    "phrases like 'the available information', 'the source does not specify', 'was not detailed', 'not provided', "
    "'not included in the information', or any comment about what you do or do not know. If a specific fact (a name, "
    "a number, a ranked list) is not in the source, simply do not mention that fact at all. Write only what IS "
    "known, as a normal news article would. Never turn a gap in your input into a sentence, and never build "
    "analysis or speculation on top of a missing fact. If you find yourself about to explain what is missing, stop "
    "and omit it entirely. "
    "Always produce a complete, readable article."
)



def strip_absence_language(text):
    """Remove sentences containing absence/uncertainty language from article text."""
    if not text:
        return text
    absence_patterns = [
        "no information was", "no details were", "no details have",
        "details were not", "details have not", "details are not",
        "has not been confirmed", "have not been confirmed",
        "was not disclosed", "were not disclosed",
        "it remains unclear", "it is unclear", "remains unknown",
        "officials have not", "has not responded", "did not respond",
        "not immediately available", "not yet available",
        "could not be reached", "could not be confirmed",
        "no official statement", "no statement has",
        "reporting is ongoing", "investigation is ongoing",
        # References to the model's own input/knowledge gap — never belong in an article.
        "available information", "the information provided", "information provided",
        "was not detailed", "were not detailed", "not detailed in",
        "the source does not", "source did not specify", "not specified in",
        "not provided in", "not included in the", "were not listed",
        "was not listed", "not named in", "were not named", "not mentioned in",
        "specifics were not", "specific details were not", "were not available in",
    ]
    sentences = text.replace("\n\n", "<<PARA>>").split(".")
    cleaned = []
    for s in sentences:
        s_lower = s.lower()
        if not any(p in s_lower for p in absence_patterns):
            cleaned.append(s)
    result = ".".join(cleaned)
    return result.replace("<<PARA>>", "\n\n").strip()


def strip_markdown(text, headline=""):
    """Remove markdown formatting and headline restatements from article text."""
    if not text:
        return text
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^[-*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    # Remove common Guardian/newsletter openers
    greetings = ["good morning.", "good afternoon.", "good evening.", "good morning,", "good afternoon,", "good evening,"]
    lower = text.lower()
    for g in greetings:
        if lower.startswith(g):
            text = text[len(g):].lstrip()
            break

    # Remove first paragraph if it looks like a headline restatement
    if headline:
        paragraphs = text.split("\n\n")
        if paragraphs:
            first = paragraphs[0].strip()
            if len(first.split()) < 20:
                hl_words = set(re.sub(r"[^a-z0-9 ]", " ", headline.lower()).split())
                p_words  = set(re.sub(r"[^a-z0-9 ]", " ", first.lower()).split())
                if len(hl_words & p_words) >= min(4, len(hl_words) // 2):
                    text = "\n\n".join(paragraphs[1:]).strip()
    return text


def generate_category_content(category_key, category_label, headlines):
    # Build headlines with raw published strings for Claude to copy back
    def sanitize(text):
        if not text:
            return ""
        import re as _re
        # Remove characters that break JSON
        text = text.replace("\\", " ").replace('"', "'").replace("\n", " ").replace("\r", " ").replace("\t", " ")
        # Remove non-printable characters
        text = "".join(c for c in text if c.isprintable())
        # Remove any remaining control sequences
        text = _re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", text)
        # Collapse whitespace
        text = _re.sub(r"\s+", " ", text).strip()
        return text

    def hl_line(i, h):
        pub     = sanitize(h.get("published", ""))
        pub_str = f" [pub:{pub}]" if pub else ""
        title   = sanitize(h.get("title", ""))
        quality = h.get("source_quality", "unknown")
        stype   = h.get("source_type", "unknown")
        hero_eligible = h.get("hero_eligible", "unknown")
        match_score = h.get("category_match_score", "")
        content = h.get("article_text", "") or h.get("summary", "")
        # 14000 chars (~2300 words): the input the model writes from. Set high enough
        # that a normal article is never truncated, so key facts (ranked lists, names,
        # numbers) always reach the model. Only a pathologically long page would be cut.
        return f"{i+1}. {title} [source_type:{stype}] [source_quality:{quality}] [hero_eligible:{hero_eligible}] [category_match_score:{match_score}]{pub_str}\n   {sanitize(content)[:14000]}"
    # Pre-filter headlines older than 48 hours before Claude sees them
    from datetime import timezone as _tz
    _now_utc = datetime.now(_tz.utc)
    def _is_stale(h):
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(h.get("published","")).astimezone(_tz.utc)
            age_hrs = (_now_utc - dt).total_seconds() / 3600
            return age_hrs > category_max_age_hours(category_key)
        except Exception:
            return False
    if category_label == "Politics":
        print(f"  Politics pre-filter: {len(headlines)} headlines incoming")
        for h in headlines[:8]:
            stale = _is_stale(h)
            print(f"    [stale={stale}] [{h.get('published','NO DATE')}] {h.get('title','')[:55]}")
    fresh = [h for h in headlines if not _is_stale(h)]
    # Do not shrink a section to 1-3 stories just because only a few are inside
    # the freshness window. If there are not enough fresh stories, keep the full
    # candidate pool and let ranking/age caps keep older items from leading.
    if len(fresh) >= min(6, len(headlines)):
        headlines = fresh
    else:
        print(f"  Freshness guard: only {len(fresh)} fresh stories; keeping {len(headlines)} candidates")

    headlines_text = "\n".join(hl_line(i, h) for i, h in enumerate(headlines))
    # Final safety pass — remove any remaining characters that break JSON
    headlines_text = headlines_text.replace("\\", " ")
    # Final nuclear sanitization — encode to ASCII and back to strip any remaining bad chars
    headlines_text = headlines_text.encode("ascii", "ignore").decode("ascii")

    # Category-specific hero selection rules
    cat_rules = {
        "world": "CRITICAL for World: pick a story about international geopolitics, foreign government actions, wars, diplomacy, or global crises. A celebrity death or cultural figure dying belongs in Entertainment, not World. Skip any story that is primarily about a single person's death unless they were a head of state or major political figure.",
        "business": "CRITICAL for Business: pick a story about markets, economic policy, major corporate decisions, trade, financial regulation, or industry-wide developments. An accident at a factory or airport (Boeing gear collapse, workplace injury) is NOT a business story — it belongs in U.S. or World. Business heroes should be about economic consequences, not physical accidents.",
        "us": "CRITICAL for U.S.: pick a story about something happening on US soil that affects American life broadly — policy, law, public safety, society. Avoid duplicating the Politics hero.",
        "politics": "CRITICAL for Politics: pick a story where the US government, Congress, White House, or Supreme Court is the PRIMARY actor. Foreign political news without direct US government involvement belongs in World.",
        "tech": "CRITICAL for Tech & Science: pick a story about technology products, companies, research, or scientific discoveries. Avoid general business stories that happen to involve a tech company.",
        "entertainment": "CRITICAL for Entertainment: this is the correct home for celebrity deaths, cultural figures, film, music, television, and arts. A major author or artist dying belongs HERE, not in World.",
        "sports": "CRITICAL for Sports: pick an actual sports result, trade, signing, or athletic achievement. Avoid crime or non-sports stories even if they involve athletes.",
    }
    rule = cat_rules.get(category_key, "")
    rule_line = f"\n\nCATEGORY RULE: {rule}" if rule else ""

    from datetime import timezone as _tz2
    _now2 = datetime.now(_tz2.utc)
    _today_label     = _now2.strftime("%A, %B %-d, %Y")
    _yesterday_label = (_now2 - timedelta(days=1)).strftime("%A, %B %-d")
    _date_context    = f"TODAY IS: {_today_label}. Yesterday was {_yesterday_label}. Use this to judge how recent each story is.\n\n"

    # Category-specific rules
    cat_rules = {
        "local_gov":    "Pick a story about local government decisions, zoning, budgets, elections, or public policy.",
        "crime":        "Pick an actual crime, arrest, or public safety story. Not politics or tax policy.",
        "business":     "Pick a story about local economic development, real estate, business openings/closings, or commercial projects.",
        "sports":       "Pick an actual sports result, game, team, athlete, coach, signing, tournament, championship, or St. Lucie Mets story. Do NOT pick lawsuits, consumer stories, crime, politics, general local news, or county government items as the Sports hero.",
        "things_to_do": "Pick a local event, activity, or attraction within 60 miles. Skip Orlando/Miami/Tampa unless very close.",
        "florida":      "Pick a statewide Florida story with broad impact. Not hyperlocal Treasure Coast.",
        "martin":       "Pick a story specifically about Martin County — Stuart, Jensen Beach, Palm City, Hobe Sound, Port Salerno.",
        "st_lucie":     "Pick a story specifically about St. Lucie County — Port St. Lucie, Fort Pierce.",
        "indian_river": "Pick a story specifically about Indian River County — Vero Beach, Sebastian, Fellsmere.",
    }
    rule = cat_rules.get(category_key, "")
    rule_line = f"\n\nCATEGORY RULE: {rule}" if rule else ""

    is_florida    = (category_key == "florida")
    system_prompt = FLORIDA_SYSTEM_PROMPT if is_florida else LOCAL_SYSTEM_PROMPT

    if category_key in COUNTY_KEYS:
        source_rules = """SOURCE RULES:
- Items marked [hero_eligible:no] must NOT be selected as the hero/section lead, even if they are full-source stories. They may only be used as lower cards if needed.
- Stories marked [source_quality:full] contain full article body text and should be used for the hero and the main full cards.
- Stories marked [source_quality:summary] may be used for normal cards only when the provided source contains enough concrete facts.
- Stories marked [source_quality:brief], [source_quality:thin], or [source_type:discovery_only] must NOT be used at all. Do not turn a blurb into an article.
- The hero must come from [source_quality:full] or [source_quality:summary].
- If there are not enough usable stories for six cards, return fewer cards. The site will backfill from its archive; never invent filler to populate the section.
- Do not write generic context such as "this reflects growth," "officials continue to investigate," or "residents are encouraged" unless those facts are explicitly in the source.

"""
    else:
        source_rules = """SOURCE RULES:
- Items marked [hero_eligible:no] must NOT be selected as the hero/section lead, even if they are full-source stories. They may only be used as lower cards if needed.
- Stories marked [source_quality:full] contain full article body text and may be used for the hero or full cards.
- Stories marked [source_quality:summary] may be used for shorter full cards only if the provided text has enough concrete facts.
- Stories marked [source_quality:brief], [source_quality:thin], or [source_type:discovery_only] must NOT be used for the hero and must not be padded into full articles.
- If there are not enough usable stories for six cards, return fewer cards rather than writing filler.
- Do not write generic context such as "this reflects growth," "officials continue to investigate," or "residents are encouraged" unless those facts are explicitly in the source.

"""

    if is_florida:
        prompt = f"""{_date_context}Florida news headlines:{rule_line}

{source_rules}{headlines_text}

Tasks:
1. Pick the single most important/urgent Florida statewide story. Prioritize broad impact — legislation, court rulings, economic news, environmental decisions, significant crimes or disasters anywhere in the state.
2. Write an accurate Florida-focused headline. Name the specific Florida city, region, or institution when relevant.
3. Write a 380-430 word factual article in FOUR full paragraphs. Cover what happened, who is affected across Florida, and what happens next statewide.
4. For the next {CARDS_PER_CATEGORY} most important Florida stories write a teaser (one to two sentences) and a body of two to three full paragraphs. Ground all specific facts in the source. Always preserve proper nouns. Never write absence language. Include an urgency_score (1-10). Cards MUST be different stories from the hero.

Return ONLY valid JSON:
{{
  "hero": {{"headline": "...", "body": "full article", "urgency_score": <1-10>, "published": "copy [pub:...] exactly", "source_index": <number>}},
  "cards": [{{"headline": "...", "teaser": "...", "body": "two to three paragraphs...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}}, {{"headline": "...", "teaser": "...", "body": "...", "urgency_score": <1-10>, "published": "...", "source_index": <number>}}, {{"headline": "...", "teaser": "...", "body": "...", "urgency_score": <1-10>, "published": "...", "source_index": <number>}}, {{"headline": "...", "teaser": "...", "body": "...", "urgency_score": <1-10>, "published": "...", "source_index": <number>}}, {{"headline": "...", "teaser": "...", "body": "...", "urgency_score": <1-10>, "published": "...", "source_index": <number>}}, {{"headline": "...", "teaser": "...", "body": "...", "urgency_score": <1-10>, "published": "...", "source_index": <number>}}]
}}
"""
    else:
        prompt = f"""{_date_context}Local Treasure Coast news headlines for {category_label}:{rule_line}

{source_rules}{headlines_text}

Tasks:
1. Pick the single most important/urgent story for Treasure Coast Florida residents. LOCAL stories (county commission decisions, local crime, school district news, local business, road/infrastructure, local sports) rank ABOVE national or state stories unless the national story has very direct local impact.
2. Write an accurate, locally-framed headline. Name the specific county, city, or town in the headline when relevant.
3. Write a complete, readable factual article of four full paragraphs covering what happened, who is affected locally, the context, and what happens next. Never write absence language.
4. For the next {CARDS_PER_CATEGORY} most important stories write a teaser (one to two sentences) and a body of two to three full paragraphs. Always preserve proper nouns — school names, road names, business names, people's names. If the source names specific schools, streets, or institutions, those names MUST appear in the card. Never write absence language. Include an urgency_score (1-10). Cards MUST be different stories from the hero.

Return ONLY valid JSON:
{{
  "hero": {{"headline": "...", "body": "full article", "urgency_score": <1-10>, "published": "copy [pub:...] exactly", "source_index": <number>}},
  "cards": [{{"headline": "...", "teaser": "...", "body": "two to three paragraphs...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}}, {{"headline": "...", "teaser": "...", "body": "...", "urgency_score": <1-10>, "published": "...", "source_index": <number>}}, {{"headline": "...", "teaser": "...", "body": "...", "urgency_score": <1-10>, "published": "...", "source_index": <number>}}, {{"headline": "...", "teaser": "...", "body": "...", "urgency_score": <1-10>, "published": "...", "source_index": <number>}}, {{"headline": "...", "teaser": "...", "body": "...", "urgency_score": <1-10>, "published": "...", "source_index": <number>}}, {{"headline": "...", "teaser": "...", "body": "...", "urgency_score": <1-10>, "published": "...", "source_index": <number>}}]
}}
"""


    response = client.messages.create(
        model=MODEL_ARTICLES,
        max_tokens=5600,
        system=[{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"}
        }],
        messages=[{"role": "user", "content": prompt}],
        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        from json_repair import repair_json
        data = json.loads(repair_json(raw))
    except Exception:
        try:
            data = json.loads(raw, strict=False)
        except json.JSONDecodeError:
            import re as _re
            cleaned = raw.encode("ascii", "ignore").decode("ascii")
            try:
                data = json.loads(cleaned, strict=False)
            except json.JSONDecodeError:
                start = cleaned.find("{")
                end   = cleaned.rfind("}") + 1
                if start == -1 or end <= start:
                    # The model returned no JSON object at all (empty string, a refusal,
                    # or prose). Raise a clear error the caller handles gracefully instead
                    # of crashing the whole run with a bare ValueError from .index().
                    raise ValueError(
                        f"Model returned no JSON object (got {len(cleaned)} chars of non-JSON)"
                    )
                data  = json.loads(cleaned[start:end], strict=False)
    # The model must return a JSON object. If it returns a bare array (e.g. a list
    # of story objects, or the object wrapped in a list), normalize it to the dict
    # we expect so we don't crash on data["category_key"] below.
    if isinstance(data, list):
        if len(data) == 1 and isinstance(data[0], dict):
            data = data[0]
        elif data and isinstance(data[0], dict) and "hero" in data[0]:
            data = data[0]
        elif all(isinstance(x, dict) for x in data) and data:
            # A list of story objects — treat first as hero, rest as cards
            data = {"hero": data[0], "cards": data[1:]}
        else:
            data = {"hero": {}, "cards": []}
    if not isinstance(data, dict):
        data = {"hero": {}, "cards": []}

    data["category_key"]   = category_key
    data["category_label"] = category_label

    # Use source_index to attach original RSS link and image directly — no fuzzy matching needed
    def attach_source(item, headlines):
        idx = item.get("source_index")
        if idx is not None:
            try:
                source = headlines[int(idx) - 1]
                item["link"]      = source.get("link", "")
                item["image_url"] = source.get("image_url", "")
                item["source_quality"] = source.get("source_quality", "")
                item["source_type"] = source.get("source_type", "")
                item["article_text"] = source.get("article_text", "")
                item["source_summary"] = source.get("summary", "")
                item["source_word_count"] = _word_count(
                    source.get("article_text", "") or source.get("summary", "")
                )
                # Carry the ORIGINAL RSS title through. The generated headline is a
                # rewrite and will not be found in STORY_CLASSIFICATION (which is keyed
                # on RSS titles), so without this the eligibility guard falls back to
                # keyword logic and rejects stories the classifier already approved —
                # which is what was emptying whole categories of their heroes.
                item["source_title"] = source.get("title", "")
                item["feed_url"] = source.get("feed_url", "")
            except (IndexError, ValueError, TypeError):
                item["link"]      = ""
                item["image_url"] = ""
        else:
            item["link"]      = ""
            item["image_url"] = ""

        # Format published
        raw_pub = item.get("published", "").replace("pub:", "").strip().strip("[]")
        item["published_raw"] = raw_pub
        item["published"] = format_age(raw_pub)
        return item

    data["hero"] = attach_source(data["hero"], headlines)
    data["hero"]["body"] = strip_absence_language(strip_markdown(data["hero"].get("body", ""), data["hero"].get("headline", "")))
    for card in data.get("cards", []):
        attach_source(card, headlines)
        card["body"] = strip_absence_language(strip_markdown(card.get("body", ""), card.get("headline", "")))

    # Enforce category lead eligibility in Python, not just by prompt. Claude can
    # still be tempted by a full-source off-topic item from a broad WPTV feed.
    def _item_hero_eligible(item):
        idx = item.get("source_index")
        try:
            return headlines[int(idx) - 1].get("hero_eligible") == "yes"
        except Exception:
            return False

    # Obituary check on the GENERATED content — catches obituaries whose RSS title
    # was just a person's name (so the ingestion filter missed them) but whose
    # written-up body contains funeral-listing language.
    _OBIT_BODY_SIGNALS = [
        "survived by", "funeral home", "funeral and cremation", "funeral & cremation",
        "cremation service", "services are being handled", "services being handled",
        "in lieu of flowers", "celebration of life", "laid to rest",
        "visitation will", "arrangements by", "arrangements are",
        "passed away peacefully", "entered into rest",
    ]
    def _is_obituary_content(item):
        blob = (item.get("headline", "") + " " + item.get("body", "")).lower()
        return any(sig in blob for sig in _OBIT_BODY_SIGNALS)

    # If the hero is an obituary, swap in the first non-obituary card
    if _is_obituary_content(data.get("hero", {})) and data.get("cards"):
        for ci, card in enumerate(data["cards"]):
            if not _is_obituary_content(card):
                print(f"  Obituary hero swap for {category_label}: '{data['hero'].get('headline','')[:50]}' -> '{card.get('headline','')[:50]}'")
                data["hero"] = card
                data["cards"].pop(ci)
                break

    # Also drop any obituary cards entirely
    if data.get("cards"):
        data["cards"] = [c for c in data["cards"] if not _is_obituary_content(c)]

    if not _item_hero_eligible(data.get("hero", {})) and data.get("cards"):
        for ci, card in enumerate(data["cards"]):
            if _item_hero_eligible(card):
                old_hero = data["hero"]
                print(f"  Hero eligibility swap for {category_label}: '{old_hero.get('headline','')[:55]}' -> '{card.get('headline','')[:55]}'")
                if not old_hero.get("teaser"):
                    _body = old_hero.get("body", "").strip()
                    _first = _body.split(". ")[0].strip()
                    old_hero["teaser"] = (_first[:160] + ".") if _first else ""
                data["hero"] = card
                data["cards"][ci] = old_hero
                break

    # Content-based category guard: the final hero must actually match the category
    # by content (topic terms present, no hard negatives), regardless of what Claude
    # flagged. Catches cases like a house-fire tragedy landing in Sports.
    # Only applies to TOPIC categories — counties are geographic and already filtered
    # upstream by relevance scoring, so re-checking them here wrongly empties sections.
    _topic_guard_cats = {"sports", "business", "crime", "things_to_do", "local_gov", "florida"}
    if category_key in _topic_guard_cats:
        if not _hero_eligible(category_key, data.get("hero", {})):
            swapped = False
            for ci, card in enumerate(data.get("cards", [])):
                if _hero_eligible(category_key, card):
                    print(f"  Category content swap for {category_label}: '{data['hero'].get('headline','')[:50]}' -> '{card.get('headline','')[:50]}'")
                    old_hero = data["hero"]
                    data["hero"] = card
                    data["cards"][ci] = old_hero
                    swapped = True
                    break
            if not swapped:
                # Nothing swapped here, but do NOT drop yet: the final guard below has
                # the full recovery cascade (card swap, county archive fallback, and
                # highest-urgency promotion). Dropping this early was killing sections
                # that the later safety nets would have saved.
                print(f"  Category guard: no eligible swap found for {category_label}; deferring to final guard")

    # Age-based score decay for stale non-breaking stories
    def decay_score(item):
        score = item.get("urgency_score", 5)
        idx = item.get("source_index")
        if idx is None: return item
        try:
            pub_raw = headlines[int(idx) - 1].get("published", "")
            if not pub_raw: return item
            from email.utils import parsedate_to_datetime
            from datetime import timezone
            dt  = parsedate_to_datetime(pub_raw).astimezone(timezone.utc)
            now = datetime.now(timezone.utc)
            hrs = (now - dt).total_seconds() / 3600
            headline = item.get("headline", "").lower()
            fresh_words = ["confirms","confirmed","announces","announced","charges","charged",
                          "arrested","arrest","resigns","resigned","fired","breaks","exclusive",
                          "new details","emerges","emerged","discovered","uncovers","uncovered",
                          "identified","named","ruled","plot","conspiracy","indicted","sentenced",
                          "found guilty","linked","motive","cause of death"]
            is_fresh = any(w in headline for w in fresh_words)
            if not is_fresh:
                if hrs > 48: score = min(score, 4)
                elif hrs > 36: score = min(score, 5)
                elif hrs > 24: score = min(score, 7)
                elif hrs > 12: score = min(score, 8)
        except Exception:
            pass
        item["urgency_score"] = score
        return item

    decay_score(data["hero"])
    for card in data.get("cards", []): decay_score(card)

    # Age cap function — parses RSS timestamps properly
    def apply_age_cap(item):
        from email.utils import parsedate_to_datetime
        from datetime import timezone, timedelta
        import re as _re
        score = item.get("urgency_score", 5)
        # Try to get age from source headline timestamp via source_index
        idx = item.get("source_index")
        pub_raw = ""
        if idx is not None:
            try:
                pub_raw = headlines[int(idx) - 1].get("published", "")
            except Exception:
                pass
        if not pub_raw:
            pub_raw = item.get("published", "")
        if not pub_raw:
            return
        try:
            dt  = parsedate_to_datetime(pub_raw).astimezone(timezone.utc)
            now = datetime.now(timezone.utc)
            hrs = (now - dt).total_seconds() / 3600
        except Exception:
            return

        headline_lower = item.get("headline", "").lower()
        body_lower     = item.get("body", "").lower()[:400]
        one_time_events = ["resigns", "resigned", "steps down", "fired", "dies", "dead at",
                           "killed in", "found dead", "passed away", "obituary"]

        if hrs > 48:
            item["urgency_score"] = min(score, 4)
        elif hrs > 24:
            if any(w in headline_lower for w in one_time_events):
                item["urgency_score"] = min(score, 4)
            else:
                item["urgency_score"] = min(score, 6)
        elif hrs > 12:
            if any(w in headline_lower for w in one_time_events):
                item["urgency_score"] = min(score, 6)
            else:
                # Check for stale body signals
                _now   = datetime.now(timezone.utc)
                _dates = [(_now - timedelta(days=d)).strftime("%B %d").lower().replace(" 0", " ") for d in range(2, 14)]
                _months_gone = [(_now - timedelta(days=d*30)).strftime("%B").lower() for d in range(1, 6)]
                stale_body_signals = ["last week", "last month", "a week ago", "days ago",
                                      "on monday", "on tuesday", "on wednesday", "on thursday",
                                      "on friday", "on saturday", "on sunday"] + _dates + _months_gone
                if any(s in body_lower for s in stale_body_signals):
                    item["urgency_score"] = min(score, 6)

    apply_age_cap(data["hero"])
    if data["hero"].get("published", "") and not any(w in data["hero"]["published"].lower() for w in ["minute", "hour", "a few", ":"]):
        print(f"  Hard age cap applied: hero is from {data['hero']['published']}")
    for card in data.get("cards", []):
        apply_age_cap(card)

    # Stale-hero swap: if the chosen hero describes an OLD event (even with a refreshed
    # timestamp), promote the freshest non-stale card to hero instead. Timestamp filtering
    # alone misses stories that publishers re-touch, so we also scan the body content.
    from email.utils import parsedate_to_datetime as _pdt
    from datetime import timezone as _tzc, timedelta as _tdc
    _now_c = datetime.now(_tzc.utc)
    _yest  = (_now_c - _tdc(days=1)).strftime("%A").lower()
    _2day  = (_now_c - _tdc(days=2)).strftime("%A").lower()
    _3day  = (_now_c - _tdc(days=3)).strftime("%A").lower()
    _4day  = (_now_c - _tdc(days=4)).strftime("%A").lower()
    _stale_days = {_yest, _2day, _3day, _4day}
    _fresh_override = ["today", "this morning", "this afternoon", "this evening",
                       "hours ago", "minutes ago", "just announced", "just released",
                       "breaking", "moments ago", "earlier today", "announced today",
                       "arrested today", "ruled today", "confirmed today"]
    _stale_phrases = ["yesterday", "two days ago", "three days ago", "earlier this week",
                      "last week", "days ago", "happened on", "occurred on", "took place on"]

    _stale_archive = load_archive(OUTPUT_DIR / "archive.json")

    def _story_is_stale(item):
        content = (item.get("teaser", "") + " " + item.get("body", "")[:800]).lower()
        # Fresh-development language always wins (e.g. "suspect arrested today" in an old story)
        if any(p in content for p in _fresh_override):
            return False
        # Do not use archive lastmod as proof of freshness. A canonical merge,
        # presentation repair, or metadata rewrite can advance lastmod without a new
        # editorial development. Genuine updates are already represented by fresh
        # source timestamps and explicit fresh-development language above.
        # Past day-name reference (e.g. "on Thursday" when today is Saturday)
        for day in _stale_days:
            if f" {day} " in content or f" {day}," in content or f" {day}." in content or content.startswith(f"{day} "):
                return True
        # Stale-event phrases
        if any(p in content for p in _stale_phrases):
            return True
        # Timestamp 24+ hours old via original RSS source
        idx = item.get("source_index")
        if idx is not None:
            try:
                pub_raw = headlines[int(idx) - 1].get("published", "")
                if pub_raw:
                    dt  = _pdt(pub_raw).astimezone(_tzc.utc)
                    if (_now_c - dt).total_seconds() / 3600 >= 24:
                        return True
            except Exception:
                pass
        return False

    if _story_is_stale(data["hero"]) and data.get("cards"):
        for ci, card in enumerate(data["cards"]):
            if _story_is_stale(card):
                continue
            # The replacement must also be eligible for this category —
            # _hero_eligible routes to topic-matching for topic categories and
            # geographic-matching for counties, so this is safe for all.
            if not _hero_eligible(category_key, card):
                continue
            old_hero = data["hero"]
            print(f"  Stale hero swapped: '{old_hero.get('headline','')[:50]}' -> '{card.get('headline','')[:50]}'")
            if not old_hero.get("teaser"):
                _body = old_hero.get("body", "").strip()
                _first = _body.split(". ")[0].strip()
                old_hero["teaser"] = (_first[:160] + ".") if _first else ""
            data["hero"] = card
            data["cards"][ci] = old_hero
            break

    # FINAL eligibility guard — runs last, after all other swaps. Applies to ALL
    # categories: topic categories require topic match, counties require geographic
    # match (both handled inside _hero_eligible).
    if True:
        # Keep a copy BEFORE the eligibility filter. If every card gets filtered out
        # and the hero is rejected too, the section would be dropped despite having
        # had real content — so the last-resort promotion below falls back to this.
        _cards_before_filter = list(data.get("cards", []))
        # Drop cards that don't belong in this category
        if data.get("cards"):
            data["cards"] = [c for c in data["cards"] if _hero_eligible(category_key, c)]

        # HARD LOCALITY GATE for county pages. The classifier sometimes places an
        # out-of-area story (a Palm Beach wildfire, a Minneapolis rally) into a county
        # and flags it hero-eligible. If that wrong story sits in the hero slot, the
        # archive fallback below never fires (the code thinks the county already has a
        # valid hero), and the county page leads with non-local news. So: a county hero
        # MUST name one of that county's places. If it does not, clear it here so the
        # eligibility swap / archive fallback replaces it with genuinely local content.
        _county_places = {
            "martin": ["martin county", "stuart", "jensen beach", "palm city",
                       "hobe sound", "port salerno", "jupiter island",
                       "hutchinson island", "indiantown", "palm city"],
            "st_lucie": ["st. lucie", "st lucie", "port st. lucie", "port st lucie",
                         "fort pierce", "st. lucie west", "hutchinson island"],
            "indian_river": ["indian river", "vero beach", "sebastian", "fellsmere",
                             "wabasso", "gifford"],
        }.get(category_key, [])
        if _county_places:
            def _names_local_place(item):
                blob = (item.get("headline", "") + " " + item.get("teaser", "") + " "
                        + item.get("body", "")).lower()
                return any(p in blob for p in _county_places)
            if data.get("hero") and not _names_local_place(data["hero"]):
                print(f"  Non-local hero cleared for {category_label}: "
                      f"'{data['hero'].get('headline','')[:50]}' names no local place")
                # Try a local card first; else leave hero to the archive fallback below.
                _local_card = None
                for _ci, _c in enumerate(data.get("cards", [])):
                    if _names_local_place(_c):
                        _local_card = _ci
                        break
                if _local_card is not None:
                    data["hero"] = data["cards"].pop(_local_card)
                else:
                    data["hero"] = {}
            # Drop non-local cards from county pages too
            if data.get("cards"):
                data["cards"] = [c for c in data["cards"] if _names_local_place(c)]

        if not _hero_eligible(category_key, data.get("hero", {})):
            _fixed = False
            for ci, card in enumerate(data.get("cards", [])):
                if _hero_eligible(category_key, card):
                    old_hero = data["hero"]
                    data["hero"] = card
                    data["cards"][ci] = old_hero
                    print(f"  Final category guard swap for {category_label}: '{old_hero.get('headline','')[:50]}' -> '{card.get('headline','')[:50]}'")
                    _fixed = True
                    break
            if not _fixed:
                # Before dropping a page, try to build its hero from the recent archive.
                # Live feeds are intermittent (WPTV rotates stories, Google News items
                # come in thin), so a category can end up with nothing hero-eligible
                # even though a relevant story was archived in the last few days. This
                # applies to BOTH county pages AND topic categories (crime, business,
                # etc.) — previously only counties were backfilled, so topic categories
                # with good recent archived articles were wrongly dropped.
                _is_county = category_key in COUNTY_KEYS
                _cf = {
                    "martin": ["martin county", "stuart", "jensen beach", "palm city",
                               "hobe sound", "port salerno", "jupiter island",
                               "hutchinson island", "indiantown"],
                    "st_lucie": ["st. lucie", "st lucie", "port st. lucie",
                                 "port st lucie", "fort pierce"],
                    "indian_river": ["indian river", "vero beach", "sebastian", "fellsmere"],
                }.get(category_key, [])
                try:
                    _arch = load_archive(OUTPUT_DIR / "archive.json")
                    from datetime import timezone as _tzf
                    from email.utils import parsedate_to_datetime as _parse_rfc822

                    def _archive_editorial_dt(entry):
                        """Rank by immutable publication plus an active major-update boost."""
                        return _editorial_freshness_dt(entry)

                    # Sort category archive candidates by immutable publication time,
                    # not lastmod. This prevents an old repaired/merged story from
                    # becoming the Crime (or any category) hero over newer coverage.
                    _arch.sort(key=_archive_editorial_dt, reverse=True)
                    _nowf = datetime.now(_tzf.utc)
                    for e in _arch:
                        # County pages match on place names; topic categories match on
                        # the archived story's own category_key.
                        if _is_county:
                            _htext = (e.get("headline","") + " " + e.get("teaser","")).lower()
                            if not any(p in _htext for p in _cf):
                                continue
                        else:
                            if e.get("category_key") != category_key:
                                continue
                        _dt = _archive_editorial_dt(e)
                        # Topic categories may reach a little further back (7 days)
                        # than counties (4) — but age is measured from original
                        # publication, never from lastmod or a repair timestamp.
                        _max_age = 4 if _is_county else 7
                        if (_dt.year == 1900) or ((_nowf - _dt).days > _max_age):
                            continue
                        _archive_candidate = {
                            "headline": e.get("headline",""),
                            "title": e.get("headline",""),
                            "teaser": e.get("teaser",""),
                            "summary": e.get("teaser",""),
                            "body": e.get("teaser",""),
                            "image_url": e.get("image_url",""),
                            "published": e.get("first_published") or e.get("date", ""),
                            "published_raw": e.get("first_published") or e.get("date", ""),
                            "source_quality": "full",
                            "feed_url": e.get("feed_url", ""),
                            "enriched": True,
                            "urgency_score": 4,
                            "link": f"{SITE_URL}/articles/{e['slug']}.html",
                            "_archived_slug": e["slug"],
                        }
                        # Never trust the old archive tag by itself; older runs may have
                        # stored category bleed. Revalidate the archived story now.
                        if not _hero_eligible(category_key, _archive_candidate):
                            continue
                        data["hero"] = _archive_candidate
                        print(f"  Archive-hero fallback for {category_label}: '{e.get('headline','')[:50]}'")
                        _fixed = True
                        break
                except Exception as _ex:
                    print(f"  Archive fallback failed: {_ex}")
                if not _fixed:
                    # LAST RESORT: if this category has ANY cards, one of them becomes
                    # the hero. A section with cards but no hero is never correct — it
                    # is what happens when the guards above reject a hero that the
                    # classifier already approved. Promote the highest-urgency card
                    # rather than dropping a section that plainly has content.
                    _cards = [
                        c for c in (data.get("cards", []) or _cards_before_filter)
                        if _hero_eligible(category_key, c)
                    ]
                    if _cards:
                        _best_i = max(
                            range(len(_cards)),
                            key=lambda i: int(_cards[i].get("urgency_score", 0) or 0),
                        )
                        _best = _cards[_best_i]
                        data["hero"] = _best
                        data["cards"] = _cards[:_best_i] + _cards[_best_i + 1:]
                        print(f"  Promoting highest-urgency card to hero for {category_label}: "
                              f"'{_best.get('headline','')[:50]}'")
                        _fixed = True

                if _fixed:
                    data["_drop_category"] = False  # a hero was recovered; never keep a stale drop flag
                else:
                    print(f"  Dropping {category_label}: no eligible hero available")
                    data["_drop_category"] = True

    return data


# -- HTML GENERATION --

def now_et():
    from datetime import timezone, timedelta
    utc = datetime.now(timezone.utc)
    et  = utc - timedelta(hours=4)
    return et.strftime("%-I:%M %p ET")

def _now_eastern_rfc822():
    """Current time as an RFC-822 string in US Eastern time (EDT/EST aware).
    Used as the first-published timestamp for RSS pubDate so consumers like Nextdoor
    show when a story appeared on OUR site, not when the original source posted it."""
    from datetime import timezone as _tz, timedelta as _td
    # Eastern is UTC-4 (EDT) Mar-Nov, UTC-5 (EST) otherwise. Determine DST roughly by
    # US rules: 2nd Sunday March through 1st Sunday November.
    u = datetime.now(_tz.utc)
    y = u.year
    def _nth_sun(month, nth):
        d = datetime(y, month, 1, tzinfo=_tz.utc)
        first_sun = 1 + (6 - d.weekday()) % 7
        return first_sun + (nth - 1) * 7
    dst_start = datetime(y, 3, _nth_sun(3, 2), 7, tzinfo=_tz.utc)   # 2am EST = 7am UTC
    dst_end   = datetime(y, 11, _nth_sun(11, 1), 6, tzinfo=_tz.utc) # 2am EDT = 6am UTC
    offset = -4 if dst_start <= u < dst_end else -5
    eastern = u + _td(hours=offset)
    tzname = "-0400" if offset == -4 else "-0500"
    return eastern.strftime(f"%a, %d %b %Y %H:%M:%S {tzname}")


def canonical_image_url(url):
    if not url: return ""
    return re.sub(r"[?#].*$", "", url.strip())


def make_paragraphs(text):
    if not text:
        return ""
    # Split on double newlines first, fall back to single newlines
    paragraphs = text.split("\n\n")
    if len(paragraphs) == 1:
        paragraphs = text.split("\n")

    # WALL-OF-TEXT FALLBACK. Some sources (notably Google News summaries) arrive with
    # their paragraph breaks stripped, so the whole article is one or two enormous
    # blocks that render as an unreadable wall. When a "paragraph" is very long and has
    # no internal breaks, regroup it into readable paragraphs of ~3 sentences each.
    # Markdown structure (##, ###, **, links) is preserved: only long plain blocks are
    # regrouped, and blocks that already contain markers are left alone.
    def _regroup_long(block):
        block = block.strip()
        if not block:
            return []
        # Leave structured/short blocks untouched
        if block.startswith(("## ", "### ")) or len(block) < 320:
            return [block]
        # Split into sentences (keep the terminator), then group ~3 per paragraph.
        # Protect common abbreviations so names such as "St. Lucie", "Dr. Smith",
        # and "U.S. 1" are not mistaken for sentence endings.
        import re as _re
        _abbr_token = "__TCT_ABBR_DOT__"
        _protected = block
        _abbreviations = (
            "St.", "Dr.", "Mr.", "Mrs.", "Ms.", "Jr.", "Sr.",
            "U.S.", "U.K.", "Fla.", "Ave.", "Blvd.", "Rd.",
            "Hwy.", "No.", "Inc.", "Co.", "Dept.", "Mt.",
        )
        for _abbr in _abbreviations:
            _protected = _re.sub(
                rf'(?<![A-Za-z]){_re.escape(_abbr)}',
                _abbr.replace(".", _abbr_token),
                _protected,
                flags=_re.IGNORECASE,
            )
        sentences = _re.split(r'(?<=[.!?])\s+(?=[A-Z"])', _protected)
        sentences = [s.replace(_abbr_token, ".").strip() for s in sentences if s.strip()]
        if len(sentences) < 4:
            return [block]  # not actually a wall; leave it
        groups, cur, cur_len = [], [], 0
        for s in sentences:
            cur.append(s)
            cur_len += len(s)
            # New paragraph every ~3 sentences or ~360 chars, whichever comes first
            if len(cur) >= 3 or cur_len >= 360:
                groups.append(" ".join(cur))
                cur, cur_len = [], 0
        if cur:
            # Avoid a lone trailing sentence: fold it into the previous paragraph
            if len(cur) == 1 and groups:
                groups[-1] = groups[-1] + " " + cur[0]
            else:
                groups.append(" ".join(cur))
        return groups

    _expanded = []
    for p in paragraphs:
        _expanded.extend(_regroup_long(p))
    paragraphs = _expanded

    def _inline(s):
        # Links first (before bold), so URLs inside markdown link syntax are handled
        # cleanly. Supports [text](url) markdown links and bare http(s) URLs. Applies
        # to every article rendered through make_paragraphs, custom or generated.
        # 1. Markdown links: [label](https://url) or [label](mailto:addr)
        s = re.sub(
            r'\[([^\]]+)\]\(((?:https?://|mailto:)[^)\s]+)\)',
            r'<a href="\2" rel="noopener">\1</a>',
            s,
        )
        # Add target=_blank to http(s) links only (mailto opens the mail client)
        s = re.sub(
            r'<a href="(https?://[^"]+)" rel="noopener">',
            r'<a href="\1" target="_blank" rel="noopener">',
            s,
        )
        # 2. Bare URLs not already inside an anchor tag
        def _bare(m):
            url = m.group(0)
            return f'<a href="{url}" target="_blank" rel="noopener">{url}</a>'
        s = re.sub(r'(?<!["\'>])(https?://[^\s<]+)', _bare, s)
        # 3. Bold
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        return s

    out = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        # Section header: line starting with "## "
        if p.startswith("## "):
            out.append(f'<h2 class="article-section">{_inline(p[3:].strip())}</h2>')
        # Sub-header: line starting with "### "
        elif p.startswith("### "):
            out.append(f'<h3 class="article-subhead">{_inline(p[4:].strip())}</h3>')
        # Regular paragraph — keep short lines only if they are not stray fragments.
        # A header-like short line (Title Case, no ending period) is rendered as a
        # subhead rather than dropped; genuine short fragments are still skipped.
        elif len(p) > 30:
            out.append(f"<p>{_inline(p)}</p>")
        elif p and not p.endswith((".", "!", "?", ":")) and p[0:1].isupper():
            # Short standalone label line (e.g. a date sub-header) — keep as subhead
            out.append(f'<h3 class="article-subhead">{_inline(p)}</h3>')
    return "".join(out)


def build_content_bank():
    """Build a bank of rich publisher content from direct RSS feeds.
    These have far richer summaries than Google News and no redirect issues.
    """
    bank = []
    seen = set()
    for url in CONTENT_BANK_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:25]:
                title = sanitize_text(entry.get("title", ""))
                if not title or title.lower() in seen:
                    continue
                seen.add(title.lower())
                summary = entry.get("summary", entry.get("description", ""))[:4000]
                if summary and len(summary) > 100:
                    bank.append({
                        "title":   title,
                        "summary": summary,
                        "source":  feed.feed.get("title", url),
                    })
        except Exception as e:
            print(f"  Content bank feed error ({url[:50]}): {e}")
    print(f"  Content bank built: {len(bank)} entries")
    return bank


def find_content(headline, content_bank, max_entries=5):
    """Fuzzy-match a headline against the content bank and return combined rich summaries."""
    stops = {"that","this","with","from","have","been","said","will","more",
             "also","when","were","they","their","about","says","just","after"}
    def tokens(text):
        return set(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split()) - stops
    hero_tokens = tokens(headline)
    matches = []
    for entry in content_bank:
        overlap = len(hero_tokens & tokens(entry["title"]))
        if overlap >= 2:
            matches.append((overlap, entry))
    matches.sort(key=lambda x: x[0], reverse=True)
    if not matches:
        return ""
    parts = []
    for _, entry in matches[:max_entries]:
        src     = entry["source"]
        title   = entry["title"]
        summary = entry["summary"]
        parts.append(f"[{src}] {title}\n{summary}")
    return "\n\n".join(parts)




def fetch_article_text(url, max_words=2500):
    """Fetch readable article body text.

    Uses trafilatura when available, then JSON-LD articleBody, then a paragraph fallback.
    Returns plain text or an empty string on failure.
    """
    if not url:
        return ""
    try:
        resp = requests.get(
            url,
            timeout=8,
            allow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                )
            },
        )
        if resp.status_code != 200:
            return ""

        html = resp.text

        def clean_article_text(raw):
            raw = re.sub(r"<script.*?</script>", " ", raw or "", flags=re.DOTALL | re.IGNORECASE)
            raw = re.sub(r"<style.*?</style>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
            raw = re.sub(r"<[^>]+>", " ", raw)
            raw = re.sub(r"&[a-zA-Z0-9#]+;", " ", raw)
            raw = re.sub(r"\s+", " ", raw).strip()
            junk = [
                "subscribe", "sign up", "cookie", "advertisement", "all rights reserved",
                "terms of service", "privacy policy", "follow us", "newsletter",
                "download our app", "watch live", "copyright"
            ]
            sentences = re.split(r"(?<=[.!?])\s+", raw)
            kept = [s.strip() for s in sentences if len(s.strip()) > 25 and not any(j in s.lower() for j in junk)]
            words = " ".join(kept).split()
            return " ".join(words[:max_words]).strip()

        # 1. Best: trafilatura if installed in the workflow.
        try:
            import trafilatura
            extracted = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=False,
                favor_precision=False,
            )
            cleaned = clean_article_text(extracted or "")
            if len(cleaned.split()) >= 140:
                return cleaned
        except Exception:
            pass

        # 2. JSON-LD articleBody often exists on modern news pages.
        scripts = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        for raw in scripts:
            try:
                data = json.loads(raw.strip())
            except Exception:
                continue
            stack = data if isinstance(data, list) else [data]
            for item in stack:
                if not isinstance(item, dict):
                    continue
                candidates = item.get("@graph") if isinstance(item.get("@graph"), list) else [item]
                for c in candidates:
                    if isinstance(c, dict) and c.get("articleBody"):
                        cleaned = clean_article_text(c.get("articleBody", ""))
                        if len(cleaned.split()) >= 140:
                            return cleaned

        # 3. Fallback: paragraphs within <article>, then all paragraphs.
        article_match = re.search(r"<article[^>]*>(.*?)</article>", html, re.DOTALL | re.IGNORECASE)
        scope = article_match.group(1) if article_match else html
        paras = re.findall(r"<p[^>]*>(.*?)</p>", scope, re.DOTALL | re.IGNORECASE)
        cleaned = clean_article_text(" ".join(paras))
        return cleaned if len(cleaned.split()) >= 80 else ""

    except Exception:
        return ""


def enhance_card(card, content_bank, headlines):
    """Rewrite a card from its exact source article, not fuzzy content-bank matches."""
    headline = card.get("headline", "")
    if not headline:
        return card

    source = None
    idx = card.get("source_index")
    if idx is not None:
        try:
            source = headlines[int(idx) - 1]
        except Exception:
            source = None

    if not source:
        return card

    link = source.get("link", "")
    is_thin = source.get("source_type") == "discovery_only" or any(d in link.lower() for d in THIN_SOURCE_DOMAINS)
    source_text = source.get("article_text", "") or ""

    # If article_text was not stored, try fetching it now — for open full sources
    # AND aggregators (Google News links resolve to real publisher pages). This is
    # what lets crime/things-to-do cards from Google News enrich instead of being dropped.
    if not source_text and link and not is_thin and source.get("source_type") in ("full_source", "aggregator"):
        source_text = fetch_article_text(link, max_words=2500)
        if source_text and len(source_text.split()) >= 140:
            source["article_text"] = source_text
            source["source_quality"] = "full"

    # Fallback only to the exact RSS summary for this same story, never the fuzzy bank.
    if not source_text:
        source_text = source.get("summary", "")

    word_count = len(source_text.split())
    if word_count < 80 or is_thin:
        # Not enough verifiable material for a full rewrite. Keep Claude's original,
        # but do not expand a paywalled/thin blurb into fake detail.
        return card

    try:
        body = card.get("body", "")
        target = "two fully developed paragraphs, about 170-240 words total" if word_count >= 140 else "one concise paragraph"
        prompt = (
            f"Rewrite this local news card using the exact source material below.\n\n"
            f"Card headline: {headline}\n\n"
            f"Current card body:\n{body}\n\n"
            f"Exact source material:\n{source_text[:6000]}\n\n"
            f"Write {target}. Use only confirmed facts from the source. "
            "Include concrete names, places, agencies, dates, numbers, votes, charges, locations, schools, roads, or businesses when present. "
            "Do not write generic background, typical patterns, community-impact filler, or advice unless explicitly stated in the source. "
            "If the source lacks enough facts, write less and stop. No em dashes. Return only the rewritten body."
        )
        resp = client.messages.create(
            model=MODEL_ARTICLES,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        enhanced = resp.content[0].text.strip()
        explanation_signals = ["i cannot rewrite", "source material", "does not match", "cannot proceed"]
        if enhanced and not any(s in enhanced.lower()[:150] for s in explanation_signals):
            # Only accept a short rewrite if the source itself was short. Full sources should
            # produce at least two useful paragraphs.
            if word_count < 140 or len(enhanced.split()) >= 90:
                card["body"] = strip_absence_language(strip_markdown(enhanced, headline))
                card["enriched"] = True
    except Exception:
        pass

    return card


def enhance_hero_article(hero, full_text):
    """Rewrite the hero article using the full source text for accuracy and detail."""
    # A generated hero counts as enriched only when it passes the same publication
    # quality gate used before permalink creation. A 40-60 word blurb is not an article.
    if _publishable_article(hero, hero=True):
        hero["enriched"] = True
    if not full_text or len(full_text.split()) < 100:
        return hero  # Not enough extra text to improve on; keep generated body
    body = hero.get("body", "")
    prompt = (
        f"You wrote this article about: {hero.get('headline', '')}\n\n"
        f"Your original article:\n\n{body}\n\n"
        f"Here is source material:\n\n{full_text}\n\n"
        "If the source material is clearly about a different story, location, or incident than the headline, "
        "return your original article exactly as written above with no changes. "
        "Otherwise, rewrite your article using confirmed facts from the source. "
        "Write in your own words — paraphrase everything except direct quotes from named individuals. "
        "Do not invent details not in the source. Do not comment on absent information. "
        "Do not copy newsletter openers like 'Good morning'. "
        "Keep it 380-480 words in four paragraphs. Include the concrete facts from the source. Plain direct English. No em dashes."
    )
    try:
        resp = client.messages.create(
            model=MODEL_ARTICLES,
            max_tokens=1600,
            messages=[{"role": "user", "content": prompt}]
        )
        enhanced = resp.content[0].text.strip()
        # Detect if Claude returned an explanation instead of an article
        explanation_signals = ["i cannot rewrite", "source material", "does not match", "i must return", "cannot proceed"]
        if enhanced and not any(s in enhanced.lower()[:200] for s in explanation_signals):
            candidate_body = strip_markdown(enhanced, hero.get("headline", ""))
            candidate = dict(hero)
            candidate["body"] = candidate_body
            if _publishable_article(candidate, hero=True):
                hero["body"] = candidate_body
                hero["enriched"] = True
                print(f"  Hero article enhanced with full source text")
            else:
                print(f"  Enhancement rejected: result was still too thin for a hero article")
        else:
            print(f"  Enhancement skipped: Claude returned explanation, keeping original")
    except Exception as e:
        print(f"  Enhancement failed ({e}), keeping original")
    return hero


def format_age(published_str):
    """Format publish time using stdlib only — no pytz needed."""
    if not published_str:
        return ""
    try:
        from email.utils import parsedate_to_datetime
        from datetime import timezone, timedelta
        et      = timezone(timedelta(hours=-4))  # EDT approximation
        dt_utc  = parsedate_to_datetime(published_str).astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)
        mins    = int((now_utc - dt_utc).total_seconds() / 60)
        dt_et   = dt_utc.astimezone(et)
        now_et  = now_utc.astimezone(et)
        hour    = dt_et.hour % 12 or 12
        ampm    = "AM" if dt_et.hour < 12 else "PM"
        time_str = f"{hour}:{dt_et.strftime('%M')} {ampm} ET"
        if mins < 60:
            return "A few minutes ago"
        if dt_et.date() == now_et.date():
            return time_str
        if mins < 2880:
            return f"Yesterday, {time_str}"
        months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        return f"{months[dt_et.month-1]} {dt_et.day}, {time_str}"
    except Exception:
        return ""


def select_front_page_hero(all_categories):
    """Use Claude to pick the most front-page-worthy hero across all categories.
    This is a HYPERLOCAL site — the best hero is the story that matters most to
    Treasure Coast residents right now. Local tragedies, local government, and
    local public-safety stories are all legitimately hero-worthy; scale is measured
    locally, not nationally."""
    if not all_categories:
        return None

    def _is_eligible(cat):
        # County stories CAN be the front-page hero — the biggest local story of the
        # day often comes from a county section. But Florida (statewide) news must
        # NEVER be the front-page hero; the front page is for local Treasure Coast
        # news. Florida still has its own category hero, just never leads the site.
        if cat["category_key"] == "florida":
            return False
        # The front-page hero must have a genuine local (or at least Florida)
        # connection. A national story with no geographic markers — e.g. a national
        # sports league announcement — can live in its section but must never lead
        # a hyperlocal front page. County heroes are inherently local, so they pass.
        if cat["category_key"] in ("martin", "st_lucie", "indian_river"):
            return True
        hero = cat.get("hero", {})
        blob = (hero.get("headline", "") + " " + hero.get("body", "")).lower()
        _fl_markers = [
            "florida", "treasure coast", "martin county", "st. lucie", "st lucie",
            "indian river", "stuart", "jensen beach", "palm city", "hobe sound",
            "port salerno", "port st. lucie", "port st lucie", "fort pierce",
            "vero beach", "sebastian", "fellsmere", "indiantown", "jupiter island",
            "hutchinson island", "mets", "clover park", "roger dean",
        ]
        # Any topic category's front-page hero must have a local or Florida marker.
        # National/global content (e.g. a worldwide survey, a national sports league)
        # can appear in its section but must never lead a hyperlocal front page.
        if not _has_any(blob, _fl_markers):
            return False
        return True

    def _fp_score(cat):
        score = int(cat["hero"].get("urgency_score", 0) or 0)
        cap   = CATEGORIES.get(cat["category_key"], {}).get("front_page_cap", 10)
        return min(score, cap)

    eligible   = [c for c in all_categories if _is_eligible(c)]
    candidates = eligible if eligible else all_categories
    if len(candidates) == 1:
        return candidates[0]

    # Compute age for each candidate so Claude can weight freshness
    from email.utils import parsedate_to_datetime
    from datetime import timezone as _tz, timedelta
    _now = datetime.now(_tz.utc)

    # HARD pre-filter: exclude candidates that are clearly stale events.
    # This runs before Claude sees anything, so Claude cannot pick a known-stale story.
    # A candidate is filtered out if:
    #   (1) its timestamp is more than 18 hours old AND content has no fresh-development language, OR
    #   (2) its content explicitly mentions a past day-name when today is a different day
    _today_name      = _now.strftime("%A").lower()
    _yesterday_name  = (_now - timedelta(days=1)).strftime("%A").lower()
    _two_days_name   = (_now - timedelta(days=2)).strftime("%A").lower()
    _three_days_name = (_now - timedelta(days=3)).strftime("%A").lower()
    _stale_day_names = {_yesterday_name, _two_days_name, _three_days_name}

    _stale_event_phrases = [
        "yesterday", "two days ago", "three days ago", "earlier this week",
        "last week", "days ago", "happened on", "occurred on",
    ]
    _fresh_dev_phrases = [
        "today", "this morning", "this afternoon", "this evening",
        "hours ago", "minutes ago", "just announced", "just released",
        "breaking", "moments ago", "earlier today",
    ]

    def _is_stale(cat):
        hero = cat["hero"]
        content = (hero.get("teaser", "") + " " + hero.get("body", "")[:800]).lower()
        # Fresh-development language wins regardless of timestamp
        if any(p in content for p in _fresh_dev_phrases):
            return False
        # Check for past day-name references (e.g. "Thursday" when today is Saturday)
        for day in _stale_day_names:
            # Check the day appears as a standalone word
            if f" {day} " in content or content.startswith(f"{day} ") or f" {day}." in content or f" {day}," in content:
                return True
        # Check for stale-event phrases
        if any(p in content for p in _stale_event_phrases):
            return True
        # Check timestamp — 18+ hours old with no fresh-development language is stale.
        # published_raw holds the real RFC-822 timestamp; published is a display
        # string ("Jul 2, 3:45 PM ET") so check the raw field first.
        for _datefield in ("published_raw", "date", "published"):
            pub = hero.get(_datefield, "")
            if not pub:
                continue
            try:
                if ("," in pub and ":" in pub) or pub.count(":") >= 1 and any(m in pub for m in ["GMT","+0","-0","Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
                    dt = parsedate_to_datetime(pub).astimezone(_tz.utc)
                elif "-" in pub[:10]:
                    dt = datetime.strptime(pub[:10], "%Y-%m-%d").replace(tzinfo=_tz.utc)
                else:
                    continue  # Display string we can't reliably parse — skip
                hrs = (_now - dt).total_seconds() / 3600
                if hrs >= 18:
                    return True
                return False  # Got a valid parse and it's fresh — done
            except Exception:
                continue
        return False

    fresh_candidates = [c for c in candidates if not _is_stale(c)]
    if fresh_candidates:
        filtered_out = [c["hero"].get("headline", "")[:60] for c in candidates if c not in fresh_candidates]
        if filtered_out:
            print(f"  Hero pre-filter excluded {len(filtered_out)} stale candidate(s): {filtered_out}")
        candidates = fresh_candidates
    else:
        print(f"  Hero pre-filter: no fresh candidates, keeping all for Claude to decide")

    if len(candidates) == 1:
        print(f"  Front page hero: [{candidates[0]['category_label']}] {candidates[0]['hero'].get('headline','')[:60]} (only fresh candidate)")
        return candidates[0]

    def _age_label(cat):
        pub = cat["hero"].get("published", "")
        if not pub:
            return "unknown age"
        try:
            dt  = parsedate_to_datetime(pub).astimezone(_tz.utc)
            hrs = (_now - dt).total_seconds() / 3600
            if hrs < 1:
                mins = max(1, int((_now - dt).total_seconds() / 60))
                return f"{mins} minutes ago"
            if hrs < 24:
                return f"{int(hrs)} hours ago"
            days = int(hrs / 24)
            return f"{days} day{'s' if days != 1 else ''} ago"
        except Exception:
            return "unknown age"

    listing = "\n\n".join(
        f"{i+1}. [{c['category_label']}] (timestamp: {_age_label(c)}) {c['hero'].get('headline','')}\n"
        f"   Content: {(c['hero'].get('teaser','') + ' ' + c['hero'].get('body','')[:500]).strip()}"
        for i, c in enumerate(candidates)
    )
    _today_label = _now.strftime("%A, %B %d, %Y")
    _yesterday   = (_now - timedelta(days=1)).strftime("%A")
    _two_days    = (_now - timedelta(days=2)).strftime("%A")
    _three_days  = (_now - timedelta(days=3)).strftime("%A")
    prompt = (
        f"TODAY IS: {_today_label}\n"
        f"Yesterday was {_yesterday}. Two days ago was {_two_days}. Three days ago was {_three_days}.\n"
        "Use this date context to evaluate when events actually happened.\n\n"
        "You are selecting the SINGLE most front-page-worthy story for Treasure Coast Today, a LOCAL news site covering Martin, St. Lucie, and Indian River counties in Florida.\n\n"
        f"{listing}\n\n"
        "AUDIENCE: Local Treasure Coast residents who want to know what's happening in their community.\n"
        "\n"
        "This is a HYPERLOCAL news site. The best hero is the story that matters MOST to people living in "
        "Martin, St. Lucie, and Indian River counties RIGHT NOW. Local relevance is everything — a story about "
        "a local fire, a county commission decision, a major local business opening, a local crime, a road project, "
        "or a school issue is exactly what belongs on the front page. Do NOT undervalue local tragedies or local "
        "events the way a national outlet would. A deadly house fire in Hobe Sound, a fatal crash on US-1, or a "
        "major arrest in Fort Pierce IS front-page news here — that is the entire point of local journalism.\n"
        "\n"
        "PICK THE HERO BY LOCAL IMPACT AND FRESHNESS:\n"
        "- Prefer the story that affects the most local residents or that the community is most likely talking about today.\n"
        "- Breaking or very recent local news beats older local news.\n"
        "- A significant local tragedy (fatal fire, deadly crash, homicide, major accident) is hero-worthy when it is "
        "recent and local — do not demote it just because it involves few people. Scale is measured locally, not nationally.\n"
        "- Local government decisions, major development/business news, and public-safety stories are all strong heroes.\n"
        "- Sports and routine event listings are weaker heroes and usually belong as cards unless it is genuinely major "
        "local sports news (a local team championship, a local athlete reaching a national stage).\n"
        "- Avoid obituaries and routine announcements as heroes.\n"
        "\n"
        "STATEWIDE AND POLITICAL STORIES: A story in the 'Florida' category can lead ONLY when it "
        "directly and concretely affects Treasure Coast residents' daily lives (for example: a property "
        "insurance change, a hurricane threatening the state, a new law taking effect, a cost-of-living or "
        "utility change). Statewide POLITICAL stories with no direct local impact — campaign fundraising "
        "totals, primary horse-race coverage, party or legislature intrigue, a governor's political "
        "maneuvering — must NEVER be the front-page hero. If the only strong Florida candidate is political "
        "insider news, pick a LOCAL story instead, even a smaller one. A modest Martin, St. Lucie, or Indian "
        "River story always beats statewide political horse-race coverage on this front page.\n"
        "\n"
        "FRESHNESS IS CRITICAL: This is a daily news site. A story from today or last night should almost always beat "
        "a story from two or three days ago. Look at the timestamp on each candidate. If a candidate is 2+ days old "
        "and there is any reasonably significant story from today or yesterday, pick the fresher one. Only pick an "
        "older story if it is dramatically more important than everything fresh available (e.g. a major ongoing local "
        "tragedy with new developments). A 3-day-old story should never lead when fresh local news exists.\n"
        "\n"
        "THINK FIRST, THEN ANSWER. For each candidate, briefly assess in one short line: (a) how recent the event is "
        "(check the timestamp), and (b) how much it matters to local Treasure Coast residents. Then state your pick, "
        "favoring the story that is both recent AND locally significant.\n"
        "\n"
        "Format your response EXACTLY like this:\n"
        "Reasoning: <one line per candidate, very brief>\n"
        "PICK: <number>\n"
    )
    try:
        resp = client.messages.create(
            model=MODEL_SELECTION,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        import re as _re
        # Prefer the explicit PICK: line; fall back to last number in the text
        pick_match = _re.search(r"PICK:\s*(\d+)", raw, _re.IGNORECASE)
        if pick_match:
            idx = int(pick_match.group(1)) - 1
        else:
            nums = _re.findall(r"\d+", raw)
            idx = int(nums[-1]) - 1 if nums else -1
        if 0 <= idx < len(candidates):
            chosen = candidates[idx]
            print(f"  Front page hero: [{chosen['category_label']}] {chosen['hero'].get('headline','')[:60]}")
            return chosen
    except Exception as e:
        print(f"  Front page hero selection failed ({e}), falling back to score-based")

    # Fallback: score-based selection
    top_cat = max(candidates, key=_fp_score)
    if _fp_score(top_cat) < 5:
        top_cat = max(all_categories, key=_fp_score)
    return top_cat


def promote_duplicate_heroes(top_cat, all_categories):
    """Ensure no single story is the hero of more than one category. First removes
    exact/near-exact duplicate heroes deterministically (guaranteed, no LLM needed),
    then uses Claude to catch semantic duplicates of the front-page hero worded
    differently. Mutates all_categories in place."""
    fp_key = top_cat["category_key"]

    def _norm(h):
        return re.sub(r"[^a-z0-9 ]", "", (h or "").lower()).strip()

    def _dupe_of_claimed(headline, claimed_tokens):
        # A hero duplicates a claimed story if it shares 4+ significant tokens with
        # any already-claimed hero. This catches near-identical headlines that are
        # not exact string matches (e.g. three worded variants of the same FIFA
        # teen story) which exact matching would miss.
        htok = _sig_tokens(headline)
        if len(htok) < 3:
            return False
        for ctok in claimed_tokens:
            if _same_story(htok, ctok):
                return True
        return False

    # -- Deterministic pass: no duplicate story across category heroes (token-based) --
    claimed_tokens = [ _sig_tokens(top_cat["hero"].get("headline","")) ]
    for cat in all_categories:
        if cat["category_key"] == fp_key:
            continue
        h = cat["hero"].get("headline","")
        if h and _dupe_of_claimed(h, claimed_tokens):
            # Promote next non-duplicate card
            promoted = None
            for ci, card in enumerate(cat.get("cards", [])):
                if not _dupe_of_claimed(card.get("headline",""), claimed_tokens):
                    promoted = (ci, card); break
            if promoted:
                ci, card = promoted
                cat["hero"] = dict(card)
                cat["cards"] = cat["cards"][:ci] + cat["cards"][ci+1:]
                claimed_tokens.append(_sig_tokens(card.get("headline","")))
                print(f"  Dedup: promoted next card to hero for {cat['category_label']} (duplicate hero)")
            elif cat["category_key"] in COUNTY_KEYS:
                # County pages may share a hero with a topic category: a Hobe Sound
                # business opening legitimately leads BOTH Business and Martin County
                # (the user's stories-can-appear-in-both rule). Keep the shared hero
                # rather than emptying the county page.
                print(f"  Dedup: keeping shared hero for {cat['category_label']} (county may mirror a topic hero)")
                claimed_tokens.append(_sig_tokens(h))
            else:
                # Never remove a category merely because its best available lead also
                # appears elsewhere. A shared hero is preferable to an empty or hidden
                # category, and the archive/card grid still gives the section depth.
                print(f"  Dedup: keeping shared hero for {cat['category_label']} "
                      f"(no non-duplicate alternative available)")
                claimed_tokens.append(_sig_tokens(h))
        else:
            if h:
                claimed_tokens.append(_sig_tokens(h))

    # -- Semantic pass: catch differently-worded duplicates of the front page hero --
    fp_headline = top_cat["hero"].get("headline", "")
    others      = [c for c in all_categories if c["category_key"] != fp_key]
    if not others or not fp_headline:
        return

    listing = "\n".join(f"{i+1}. {c['hero'].get('headline','')}" for i, c in enumerate(others))
    prompt = (
        f"The lead front-page story is:\n\"{fp_headline}\"\n\n"
        f"Here are other section lead headlines:\n{listing}\n\n"
        "Which of these numbered headlines cover the SAME underlying event as the lead story? "
        "Same event means the same action by the same actors at the same time, even if worded "
        "completely differently.\n"
        "Return ONLY a JSON array of the numbers that are duplicates of the lead story. "
        "If none are duplicates, return []."
    )
    try:
        resp = client.messages.create(
            model=MODEL_SELECTION,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        dupes = set(int(x) for x in json.loads(raw))
    except Exception as e:
        print(f"  Hero semantic dedup failed ({e}), deterministic pass already applied")
        return

    for i, cat in enumerate(others):
        if (i + 1) in dupes:
            cards = cat.get("cards", [])
            if cards:
                promoted = cards[0]
                cat["hero"] = dict(promoted)
                cat["cards"] = cards[1:]
                print(f"  Promoted next card to hero for {cat['category_label']} (semantic duplicate of front page hero)")


def global_rank(all_cards, dedupe_against=None):
    """Final global ranking — sends all headlines to Claude for true cross-category
    ordering AND semantic deduplication. Claude identifies stories that cover the same
    underlying event and keeps only the most important version.

    dedupe_against: optional headline string (e.g. the front page hero) that stories
    should also be deduplicated against — any story covering that same event is dropped.
    """
    if not all_cards:
        return all_cards

    ranked_input = all_cards
    stories = []
    for i, c in enumerate(ranked_input):
        cat   = c.get("cat_label", "")
        head  = c.get("headline", "")
        stories.append(f"{i+1}. [{cat}] {head}")
    stories_text = "\n".join(stories)
    n = len(ranked_input)

    dedupe_clause = ""
    if dedupe_against:
        dedupe_clause = (
            f"\nThe lead story already shown is: \"{dedupe_against}\"\n"
            "EXCLUDE any story from your list that covers this same underlying event, "
            "even if worded very differently or framed from a different angle.\n"
        )

    prompt = (
        f"Rank these {n} Treasure Coast local news stories by importance and relevance to LOCAL residents of Martin, St. Lucie, and Indian River counties.\n"
        "\n"
        "CRITICAL DEDUPLICATION RULE: Many of these stories cover the SAME underlying event "
        "from different angles or with different wording (e.g. 'Stuart commission approves dock project' and "
        "'Stuart City Commission votes to fund downtown dock renovation' are the SAME event). "
        "Identify every cluster of stories about the same event and keep ONLY the single "
        "best version of each. Drop all the others entirely. Two stories are the same event "
        "if they describe the same action, by the same actors, at the same time — regardless "
        "of how differently they are phrased.\n"
        + dedupe_clause +
        "\n"
        "PRIMARY signal: local relevance and impact on Treasure Coast residents.\n"
        "SECONDARY signal: recency — fresher local news ranks above older local news; edited timestamps do not make old stories new.\n"
        "Apply this weighting:\n"
        "1. Major local breaking news and public safety (local fires, fatal crashes, homicides, storms, evacuations affecting Martin, St. Lucie, or Indian River counties): TOP TIER\n"
        "2. Local government decisions that affect residents (county commission votes, city council actions, school board decisions, zoning, budgets, tax changes): very high\n"
        "3. Major local development and business news (large projects, major employers, notable openings/closings, road and infrastructure projects): high\n"
        "4. Local crime and courts (arrests, charges, investigations, sentencing) in the three counties: high\n"
        "5. Community news, events, and things to do that many residents care about: medium\n"
        "6. Statewide Florida news with clear local relevance (insurance, hurricanes, state laws affecting residents): medium\n"
        "7. Follow-up stories: rank below genuinely new stories\n"
        "8. Sports and entertainment: rank below breaking news and government/public-safety unless a genuinely major local sports story\n"
        "Stories about places OUTSIDE the three-county Treasure Coast area should rank low unless they directly affect local residents.\n"
        "When two stories seem equally important, use recency as a tiebreaker (fresher wins).\n\n"
        f"{stories_text}\n\n"
        "Return ONLY a JSON array of the original numbers, in ranked order, most important first, "
        "with all duplicates removed (only the best version of each distinct event included).\n"
        "Example: [4, 1, 12, 7]"
    )
    try:
        resp = client.messages.create(
            model=MODEL_SELECTION,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        indices = json.loads(raw)
        seen, ranked = set(), []
        for idx in indices:
            i = int(idx) - 1
            if 0 <= i < n and i not in seen:
                seen.add(i)
                ranked.append(ranked_input[i])
        # NOTE: stories Claude omitted are treated as duplicates and intentionally dropped.
        # Only append back un-ranked stories if Claude returned suspiciously few (failure guard).
        if len(ranked) < max(3, n // 3):
            for i, card in enumerate(ranked_input):
                if i not in seen:
                    ranked.append(card)
        print(f"  Global ranking: {len(ranked)} stories after dedup (from {n})")
        return ranked
    except Exception as e:
        print(f"  Global ranking failed ({e}), using urgency_score fallback")
        return all_cards



def render_index(all_categories, top_cat):
    COUNTY_KEYS = {"martin", "st_lucie", "indian_river"}
    SECTION_LABELS = {
        "martin":       "Martin County News",
        "st_lucie":     "St. Lucie County News",
        "indian_river": "Indian River County News",
        "local_gov":    "Treasure Coast Local Government News",
        "crime":        "Treasure Coast Crime & Safety News",
        "business":     "Treasure Coast Business News",
        "sports":       "Treasure Coast Sports News",
        "things_to_do": "Things To Do on the Treasure Coast",
        "florida":      "Florida News",
    }

    def hero_section(cat_key, cat_label, hero, visible=False):
        archive = load_archive(OUTPUT_DIR / "archive.json")
        canonical = find_presentation_canonical(hero, archive)
        if canonical:
            _hydrate_presentation_item(hero, canonical)
        preview    = (hero.get("teaser") or hero.get("body", ""))[:380].rstrip()
        paragraphs = make_paragraphs(hero.get("body", ""))
        img_url    = hero.get("image_url", "")
        img_credit = hero.get("image_credit", "")
        credit_html = f'<figcaption class="img-credit">Photo: {img_credit}</figcaption>' if img_url and img_credit else ""
        img_html    = f'<figure class="hero-image-wrap"><img class="hero-image" src="{img_url}" alt="" loading="lazy">{credit_html}</figure>' if img_url else ""
        pub_time    = hero.get("published", "")
        display     = "" if visible else ' style="display:none"'
        fade        = " fade-in" if visible else ""
        if hero.get("_section_placeholder"):
            article_url = f"{SITE_URL}/archive.html"
        elif hero.get("_archived_slug"):
            article_url = f"{SITE_URL}/articles/{hero['_archived_slug']}.html"
        else:
            matched = canonical or find_presentation_canonical(hero, archive)
            if matched:
                slug = matched["slug"]
            else:
                today = datetime.utcnow().strftime("%Y-%m-%d")
                slug = f"{today}-{slugify(hero.get('headline', ''))}"
            article_url = f"{SITE_URL}/articles/{slug}.html"
        section_label = ""
        if cat_key in SECTION_LABELS:
            seo_text  = SECTION_LABELS[cat_key]
            label_cls = "county-section-label" if cat_key in COUNTY_KEYS else "topic-section-label"
            section_label = f'<div class="{label_cls}"><h2 class="county-label-text">{seo_text}</h2></div>'
        headline_text = hero.get("headline", "")
        hl_escaped = headline_text.replace('"', "&quot;")
        # Responsive hero typography: preserve the full editorial headline while
        # scaling only unusually long headlines. Word count is included because
        # many short words can wrap more aggressively than character count alone.
        _headline_len = len(headline_text.strip())
        _headline_words = len(headline_text.split())
        if _headline_len > 145 or _headline_words > 22:
            _headline_size_class = " hero-v3-headline--ultra"
            _content_size_class = " hero-v3-content--ultra"
        elif _headline_len > 112 or _headline_words > 17:
            _headline_size_class = " hero-v3-headline--very-long"
            _content_size_class = " hero-v3-content--very-long"
        elif _headline_len > 82 or _headline_words > 13:
            _headline_size_class = " hero-v3-headline--long"
            _content_size_class = " hero-v3-content--long"
        else:
            _headline_size_class = ""
            _content_size_class = ""
        _urgency_text = f"{cat_label} {headline_text}".strip().lower()
        urgency_cls = " live" if _urgency_text.startswith("live") else (" developing" if _urgency_text.startswith("developing") else (" breaking" if hero.get("is_breaking") or _urgency_text.startswith("breaking") else ""))
        return f"""
    <section class="hero hero-v3{fade}" data-cat-hero="{cat_key}"{display}>
      {section_label}
      <a class="hero-v3-link" href="{article_url}" aria-label="Read: {hero['headline']}">
        <div class="hero-v3-media">{img_html}</div>
        <div class="hero-v3-content{_content_size_class}">
          <span class="tag hero-v3-tag{urgency_cls}">{cat_label}</span>
          <h1 class="hero-v3-headline{_headline_size_class}">{headline_text}</h1>
          <p class="hero-summary hero-v3-summary">{preview}...</p>
          <div class="hero-foot hero-v3-foot">
            <span class="meta">{pub_time}</span>
            <span class="hero-readmore">Read full story &rarr;</span>
          </div>
        </div>
      </a>
    </section>"""

    heroes_html = hero_section("all", top_cat["category_label"], top_cat["hero"], visible=True)
    for cat in all_categories:
        heroes_html += hero_section(cat["category_key"], cat["category_label"], cat["hero"], visible=False)

    all_cards_pool = []
    for cat in all_categories:
        for card in cat.get("cards", []):
            card["cat_label"] = cat["category_label"]
            card["cat_key"]   = cat["category_key"]
            all_cards_pool.append(card)

    # Only enriched cards appear on the homepage. Unenriched cards are dropped.
    enriched_pool = [c for c in all_cards_pool if c.get("enriched")]

    # Backfill from the archive: recent enriched stories (last 3 days) that aren't in
    # this run's fresh cards. Feeds rotate stories off quickly, so a story from
    # yesterday may not be re-fetched today — but it's still recent and relevant and
    # should keep filling out the grid rather than dropping to "older" immediately.
    from datetime import timezone as _tzbf
    _now_bf = datetime.now(_tzbf.utc)
    _current_hls = {c.get("headline", "").strip().lower() for c in enriched_pool}
    _current_hls.add(top_cat["hero"].get("headline", "").strip().lower())
    for cat in all_categories:
        _current_hls.add(cat["hero"].get("headline", "").strip().lower())

    _bf_archive = load_archive(OUTPUT_DIR / "archive.json")
    _bf_archive.sort(key=_editorial_freshness_dt, reverse=True)
    for e in _bf_archive:
        hl = (e.get("headline", "") or "").strip()
        if not hl or hl.lower() in _current_hls:
            continue
        date_str = _story_display_timestamp(e)
        try:
            edt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=_tzbf.utc)
            if (_now_bf - edt).days > 3:
                continue  # Older than 3 days — leave for the Older section
        except Exception:
            continue
        # Reconstruct a card from the archive entry
        backfill_card = {
            "headline":   hl,
            "teaser":     e.get("teaser", ""),
            "body":       e.get("teaser", ""),
            "cat_label":  e.get("category_label", ""),
            "cat_key":    e.get("category_key", ""),
            "image_url":  e.get("image_url", ""),
            "published":  _story_display_timestamp(e),
            "published_raw": _story_display_timestamp(e),
            "enriched":   True,
            "urgency_score": 4,  # Backfill ranks below fresh cards
            "link":       f"{SITE_URL}/articles/{e['slug']}.html",
            "_archived_slug": e["slug"],
        }
        # Validate against category — the archive may contain stories that were
        # mis-categorized in earlier runs (before category fixes). For TOPIC categories,
        # re-check topic match. For COUNTY categories, trust the archived tag since it
        # passed the geographic filter when first archived (and feed_url may be absent
        # on older entries, which would cause false rejections).
        _bf_ckey = e.get("category_key", "")
        if _bf_ckey in {"sports", "business", "crime", "things_to_do", "local_gov", "florida"}:
            _check = {"headline": hl, "body": e.get("teaser", ""),
                      "title": hl, "summary": e.get("teaser", ""),
                      "feed_url": e.get("feed_url", ""),
                      "source_quality": "full"}
            if not _hero_eligible(_bf_ckey, _check):
                continue  # Skip mis-categorized archived story
        enriched_pool.append(backfill_card)
        _current_hls.add(hl.lower())

        # Cross-post to county pages: a story archived under a topic category (e.g.
        # a Hobe Sound business opening under Business) also belongs on its county
        # page. If the story names a county's places and it isn't already a county
        # story, add a second backfill card tagged for that county so it shows in
        # both places rather than vanishing from the county page.
        if _bf_ckey not in COUNTY_KEYS:
            _htext = (hl + " " + e.get("teaser", "")).lower()
            _county_places = {
                "martin": ["martin county", "stuart", "jensen beach", "palm city",
                           "hobe sound", "port salerno", "jupiter island",
                           "hutchinson island", "indiantown", "rio", "sewall"],
                "st_lucie": ["st. lucie", "st lucie", "port st. lucie", "port st lucie",
                             "fort pierce", "st. lucie west"],
                "indian_river": ["indian river", "vero beach", "sebastian", "fellsmere"],
            }
            for _ckey, _places in _county_places.items():
                if any(p in _htext for p in _places):
                    _county_card = dict(backfill_card)
                    _county_card["cat_key"]   = _ckey
                    _county_card["cat_label"] = CATEGORIES[_ckey]["label"]
                    enriched_pool.append(_county_card)

    enriched_pool.sort(key=lambda c: int(c.get("urgency_score", 0) or 0), reverse=True)
    topnews     = global_rank(enriched_pool, dedupe_against=top_cat["hero"].get("headline", ""))
    topnews_ids = {id(c) for c in topnews}
    remaining   = [c for c in enriched_pool if id(c) not in topnews_ids]
    all_cards_display = topnews + remaining

    # Apply pin_position overrides — pinned custom articles lock to specific slots
    pinned = [(c.get("pin_position"), c) for c in all_cards_display if c.get("pin_position")]
    if pinned:
        unpinned = [c for c in all_cards_display if not c.get("pin_position")]
        result = list(unpinned)
        for pos, card in sorted(pinned, key=lambda x: x[0]):
            idx = max(0, min(pos - 1, len(result)))
            if card in result:
                result.remove(card)
            result.insert(idx, card)
        all_cards_display = result

    archive_for_links = load_archive(OUTPUT_DIR / "archive.json")

    def card_permalink(card):
        # Backfill cards already carry their archived slug
        if card.get("_archived_slug"):
            return f"{SITE_URL}/articles/{card['_archived_slug']}.html"
        matched = find_presentation_canonical(card, archive_for_links)
        if matched:
            _hydrate_presentation_item(card, matched)
            return f"{SITE_URL}/articles/{matched['slug']}.html"
        # No archive entry means no article page exists — skip this card
        return None

    support_card = """
      <a href="/advertise.html" class="grid-card tct-advertise-card" data-cat="all" data-support-card="true" aria-label="Advertise with Treasure Coast Today">
        <div class="tct-advertise-card-inner">
          <span class="tct-advertise-kicker">Grow your local business</span>
          <h2 class="tct-advertise-headline">Reach readers across the Treasure Coast.</h2>
          <p class="tct-advertise-copy">Connect with customers in Martin, St. Lucie and Indian River counties through banner ads, sponsored articles, business spotlights and social media promotion.</p>
          <span class="tct-advertise-options" aria-hidden="true">
            <span>Banner ads</span><span>Featured articles</span><span>Social promotion</span>
          </span>
          <span class="tct-advertise-cta">Explore advertising options <b>&rarr;</b></span>
        </div>
      </a>"""

    def card_display_date(card):
        # Cards show when the canonical article was actually changed. A routine
        # workflow/build never advances editorial_updated_at. Stories that have never
        # evolved continue to show their original TCT publication timestamp.
        matched = find_presentation_canonical(card, archive_for_links)
        raw = _story_display_timestamp(matched) if matched else card.get("published_raw") or card.get("published", "")
        dt = _parse_editorial_datetime(raw)
        if dt:
            try:
                from zoneinfo import ZoneInfo
                dt = dt.astimezone(ZoneInfo("America/New_York"))
            except Exception:
                pass
            months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
            hour = dt.hour % 12 or 12
            ampm = "AM" if dt.hour < 12 else "PM"
            return f"{months[dt.month-1]} {dt.day}, {dt.year} · {hour}:{dt.strftime('%M')} {ampm}"
        return str(raw or "")

    cards_html = ""
    for i, card in enumerate(all_cards_display):
        permalink = card_permalink(card)
        if not permalink:
            continue  # No article page exists for this card — skip it
        if i == 4:
            cards_html += support_card
        ck        = card.get("cat_key", "all")
        cl        = card.get("cat_label", "")
        card_time = card_display_date(card)
        img_url   = card.get("image_url", "")
        if not img_url:
            fb_img, _ = get_fallback_image(ck, card.get("headline", ""), sequential=True)
            # Never fall back to the og social-share image on-page. If the category
            # fallback is somehow unavailable, use the generic top_news fallback, then
            # a guaranteed local image — the og-*.png files are for social cards only.
            if not fb_img:
                fb_img, _ = get_fallback_image("top_news", card.get("headline", ""), sequential=True)
            img_url = fb_img or f"{SITE_URL}/images/fallback/local_gov-1.jpg"
        topnews_attr = ' data-topnews="true"' if id(card) in topnews_ids else ""
        _urgency_text = f"{cl} {card.get('headline','')}".strip().lower()
        urgency_cls = " live" if _urgency_text.startswith("live") else (" developing" if _urgency_text.startswith("developing") else (" breaking" if card.get("is_breaking") or _urgency_text.startswith("breaking") else ""))
        cards_html += f"""
      <a href="{permalink}" class="grid-card fade-in" data-cat="{ck}"{topnews_attr}>
        <div class="grid-card-image-wrap">
          <img class="grid-card-image" src="{img_url}" alt="" loading="lazy">
        </div>
        <div class="grid-card-body">
          <span class="grid-card-tag{urgency_cls}">{cl}</span>
          <h2 class="grid-card-headline">{card["headline"]}</h2>
          <span class="grid-card-time">{card_time}</span>
        </div>
      </a>"""

    # -- OLDER: per-category archived stories no longer shown as current cards --
    # Top News ("all") gets no Older section. Each category gets up to 10 of its
    # own older stories that aren't currently displayed.
    current_headlines = {top_cat["hero"].get("headline", "").strip().lower()}
    for cat in all_categories:
        current_headlines.add(cat["hero"].get("headline", "").strip().lower())
    for card in all_cards_display:
        current_headlines.add(card.get("headline", "").strip().lower())

    older_archive = load_archive(OUTPUT_DIR / "archive.json")
    older_archive.sort(key=_effective_story_datetime, reverse=True)

    # Group older stories by category, up to 10 each, excluding current headlines
    older_by_cat = {}
    for e in older_archive:
        hl = (e.get("headline", "") or "").strip()
        ckey = e.get("category_key", "")
        if not hl or not ckey or hl.lower() in current_headlines:
            continue
        if not _archive_entry_publishable(e):
            continue
        older_by_cat.setdefault(ckey, [])
        if len(older_by_cat[ckey]) < 10:
            older_by_cat[ckey].append(e)

    older_sections_html = ""
    # Build an "More Stories" section for every category that has archived stories,
    # NOT just categories that survived this run. A category with no fresh hero this
    # run should still show its older archived stories. Use the master CATEGORIES
    # config for labels so the section renders regardless of current-run state.
    for ckey in CATEGORIES:
        items = older_by_cat.get(ckey, [])
        if not items:
            continue
        cat_label = CATEGORIES[ckey]["label"]
        items_html = ""
        for e in items:
            items_html += f"""
        <li class="older-item">
          <a href="/articles/{e['slug']}.html" class="older-link">
            <span class="older-headline">{e['headline']}</span>
            <span class="older-date">{e.get('date','')}</span>
          </a>
        </li>"""
        # Hidden by default; shown only when its category is active
        older_sections_html += f"""
    <section class="older-section" data-older-cat="{ckey}" style="display:none">
      <h2 class="older-title">More {cat_label} Stories</h2>
      <ul class="older-list">{items_html}
      </ul>
      <a href="/archive.html" class="older-more">View full archive &rarr;</a>
    </section>"""

    older_section = older_sections_html

    # Category navigation is permanent. A weak/failed live run is recovered from the
    # archive before rendering, so there is never a reason to hide a category button.
    nav_buttons = "\n        ".join(
        ['<button class="cat-btn active" data-cat="all">Top News</button>'] +
        [
            f'<button class="cat-btn" data-cat="{cat_key}">{cat_config["label"]}</button>'
            for cat_key, cat_config in CATEGORIES.items()
        ]
    )

    # Editorial redesign modules: a compact latest-news rail and county panels.
    # "Latest News" is chronological, not urgency-ranked. It uses the canonical
    # article's true editorial timestamp and excludes stale stories rather than
    # filling the rail with old high-urgency items. Routine workflow runs never
    # affect this ordering because _effective_story_datetime ignores build time.
    latest_items_html = ""
    _latest_cutoff = datetime.now(EASTERN) - timedelta(days=5)  # rolling 5 days, Eastern Time
    _latest_candidates = []
    _latest_seen_urls = set()

    for _latest_card in all_cards_display:
        _url = card_permalink(_latest_card)
        if not _url or _url in _latest_seen_urls:
            continue
        _matched = find_presentation_canonical(_latest_card, archive_for_links)
        _effective_dt = _effective_story_datetime(_matched or _latest_card)
        if _effective_dt < _latest_cutoff:
            continue
        _latest_seen_urls.add(_url)
        _latest_candidates.append((_effective_dt, _latest_card, _matched, _url))

    _latest_candidates.sort(key=lambda item: item[0], reverse=True)

    for _effective_dt, _latest, _matched, _url in _latest_candidates[:5]:
        _ltime = card_display_date(_latest)
        _lcat = (_matched or {}).get("category_label") or _latest.get("cat_label", "")
        _display_headline = (_matched or {}).get("headline") or _latest.get("headline", "")
        _lurgency_text = f"{_lcat} {_display_headline}".strip().lower()
        _lbadge = ""
        if _latest.get("is_breaking") or _lurgency_text.startswith("breaking"):
            _lbadge = '<span class="latest-status breaking">Breaking</span>'
        elif _lurgency_text.startswith("developing"):
            _lbadge = '<span class="latest-status developing">Developing</span>'
        latest_items_html += f'''
          <a class="latest-item" href="{_url}">
            <div class="latest-item-top"><span class="latest-time">{_ltime}</span>{_lbadge}</div>
            <h3>{_display_headline}</h3>
            <span class="latest-county">{_lcat}</span>
          </a>'''

    county_panels_html = ""
    for _county_key, _county_title, _county_sub in [
        ("martin", "Martin County", "Stuart · Jensen Beach · Palm City · Hobe Sound"),
        ("st_lucie", "St. Lucie County", "Port St. Lucie · Fort Pierce"),
        ("indian_river", "Indian River County", "Vero Beach · Sebastian · Fellsmere"),
    ]:
        _county_cards = [c for c in all_cards_display if c.get("cat_key") == _county_key][:3]
        if not _county_cards:
            continue
        _county_items = ""
        for _cc in _county_cards:
            _curl = card_permalink(_cc)
            if not _curl:
                continue
            _cimg = _cc.get("image_url", "")
            if not _cimg:
                _cimg, _ = get_fallback_image(_county_key, _cc.get("headline", ""), sequential=True)
            _county_items += f'''
              <a class="county-panel-story" href="{_curl}">
                <img src="{_cimg}" alt="" loading="lazy">
                <span>{_cc.get("headline", "")}</span>
              </a>'''
        county_panels_html += f'''
          <section class="county-panel county-{_county_key}">
            <div class="county-panel-head">
              <div><h2>{_county_title}</h2><p>{_county_sub}</p></div>
              <a href="/?cat={_county_key}">View all →</a>
            </div>
            <div class="county-panel-list">{_county_items}</div>
          </section>'''

    _head   = _page_head(
        "Treasure Coast Today | Local News for Martin, St. Lucie & Indian River County",
        "Local news for Florida's Treasure Coast. Breaking news, crime, government, "
        "business, sports and weather for Stuart, Port St. Lucie, Fort Pierce and Vero Beach.",
    )
    _footer = _page_footer()

    _live_masthead_script = r'''
  <script>
  (() => {
    const timeEl = document.getElementById('tct-live-time');
    const weatherEl = document.getElementById('tct-live-weather');
    const iconEl = document.getElementById('tct-weather-icon');
    const tempEl = document.getElementById('tct-weather-temp');
    const conditionEl = document.getElementById('tct-weather-condition');

    function updateTreasureCoastClock() {
      if (!timeEl) return;
      const now = new Date();
      const datePart = new Intl.DateTimeFormat('en-US', {
        timeZone: 'America/New_York',
        weekday: 'short', month: 'short', day: 'numeric'
      }).format(now);
      const timePart = new Intl.DateTimeFormat('en-US', {
        timeZone: 'America/New_York',
        hour: 'numeric', minute: '2-digit', hour12: true,
        timeZoneName: 'short'
      }).format(now);
      timeEl.textContent = `${datePart} · ${timePart}`;
      timeEl.dateTime = now.toISOString();
    }

    const weatherCodes = {
      0: ['☀', 'Clear'],
      1: ['🌤', 'Mostly clear'],
      2: ['⛅', 'Partly cloudy'],
      3: ['☁', 'Cloudy'],
      45: ['🌫', 'Fog'], 48: ['🌫', 'Fog'],
      51: ['🌦', 'Light drizzle'], 53: ['🌦', 'Drizzle'], 55: ['🌧', 'Heavy drizzle'],
      56: ['🌧', 'Freezing drizzle'], 57: ['🌧', 'Freezing drizzle'],
      61: ['🌦', 'Light rain'], 63: ['🌧', 'Rain'], 65: ['🌧', 'Heavy rain'],
      66: ['🌧', 'Freezing rain'], 67: ['🌧', 'Freezing rain'],
      71: ['🌨', 'Light snow'], 73: ['🌨', 'Snow'], 75: ['❄', 'Heavy snow'], 77: ['🌨', 'Snow grains'],
      80: ['🌦', 'Rain showers'], 81: ['🌧', 'Rain showers'], 82: ['⛈', 'Heavy showers'],
      85: ['🌨', 'Snow showers'], 86: ['🌨', 'Snow showers'],
      95: ['⛈', 'Thunderstorms'], 96: ['⛈', 'Storms with hail'], 99: ['⛈', 'Storms with hail']
    };

    function paintWeather(data) {
      if (!data || typeof data.temperature !== 'number') return;
      const [icon, label] = weatherCodes[data.code] || ['◌', 'Local weather'];
      iconEl.textContent = icon;
      tempEl.textContent = `${Math.round(data.temperature)}°`;
      conditionEl.textContent = label;
      weatherEl.title = `Treasure Coast: ${Math.round(data.temperature)}°F, ${label}`;
    }

    async function updateTreasureCoastWeather() {
      if (!weatherEl) return;
      const cacheKey = 'tct-weather-v1';
      const maxAge = 20 * 60 * 1000;
      try {
        const cached = JSON.parse(localStorage.getItem(cacheKey) || 'null');
        if (cached && Date.now() - cached.savedAt < maxAge) {
          paintWeather(cached);
          return;
        }
      } catch (_) {}

      try {
        const url = 'https://api.open-meteo.com/v1/forecast?latitude=27.1975&longitude=-80.2528&current=temperature_2m,weather_code&temperature_unit=fahrenheit&timezone=America%2FNew_York';
        const response = await fetch(url, { cache: 'no-store' });
        if (!response.ok) throw new Error(`Weather request failed: ${response.status}`);
        const result = await response.json();
        const data = {
          temperature: result.current && result.current.temperature_2m,
          code: result.current && result.current.weather_code,
          savedAt: Date.now()
        };
        paintWeather(data);
        try { localStorage.setItem(cacheKey, JSON.stringify(data)); } catch (_) {}
      } catch (_) {
        conditionEl.textContent = 'Local weather';
      }
    }

    updateTreasureCoastClock();
    window.setInterval(updateTreasureCoastClock, 30000);
    updateTreasureCoastWeather();
    window.setInterval(updateTreasureCoastWeather, 20 * 60 * 1000);
  })();
  </script>
    '''

    _hero_typography_css = r"""
  <style id="tct-responsive-hero-typography">
    /* The full hero headline is always retained. Longer headlines scale down
       and receive more of the content column; the teaser yields space first. */
    .hero-v3-link {
      min-height: 0;
    }
    .hero-v3-content {
      display: flex;
      flex-direction: column;
      min-width: 0;
      min-height: 0;
      overflow: hidden;
    }
    .hero-v3-headline {
      margin-bottom: clamp(0.65rem, 1.15vw, 1rem);
      font-size: clamp(2.55rem, 3.35vw, 4.05rem);
      line-height: 0.98;
      letter-spacing: -0.035em;
      overflow: visible;
      max-height: none;
    }
    .hero-v3-headline--long {
      font-size: clamp(2.2rem, 2.85vw, 3.45rem);
      line-height: 0.99;
      letter-spacing: -0.032em;
    }
    .hero-v3-headline--very-long {
      font-size: clamp(1.92rem, 2.42vw, 2.95rem);
      line-height: 1.01;
      letter-spacing: -0.028em;
    }
    .hero-v3-headline--ultra {
      font-size: clamp(1.68rem, 2.08vw, 2.5rem);
      line-height: 1.03;
      letter-spacing: -0.022em;
    }
    .hero-v3-summary {
      display: -webkit-box;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 3;
      line-clamp: 3;
      overflow: hidden;
      margin-bottom: 0;
    }
    .hero-v3-content--long .hero-v3-summary {
      -webkit-line-clamp: 2;
      line-clamp: 2;
    }
    .hero-v3-content--very-long .hero-v3-summary,
    .hero-v3-content--ultra .hero-v3-summary {
      -webkit-line-clamp: 1;
      line-clamp: 1;
    }
    .hero-v3-foot {
      margin-top: auto;
      flex: 0 0 auto;
    }
    @media (max-width: 1100px) {
      .hero-v3-headline { font-size: clamp(2.15rem, 4vw, 3.35rem); }
      .hero-v3-headline--long { font-size: clamp(1.95rem, 3.5vw, 2.85rem); }
      .hero-v3-headline--very-long { font-size: clamp(1.72rem, 3.05vw, 2.45rem); }
      .hero-v3-headline--ultra { font-size: clamp(1.52rem, 2.7vw, 2.12rem); }
    }
    @media (max-width: 760px) {
      .hero-v3-content { overflow: visible; }
      .hero-v3-headline,
      .hero-v3-headline--long,
      .hero-v3-headline--very-long,
      .hero-v3-headline--ultra {
        font-size: clamp(2rem, 9vw, 3rem);
        line-height: 1;
      }
      .hero-v3-summary,
      .hero-v3-content--long .hero-v3-summary,
      .hero-v3-content--very-long .hero-v3-summary,
      .hero-v3-content--ultra .hero-v3-summary {
        -webkit-line-clamp: 3;
        line-clamp: 3;
      }
    }
  </style>
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{_head}
{_hero_typography_css}
</head>
<body>
  <header>
    <div class="header-inner">
      <div class="header-top">
        <a href="/" class="wordmark" aria-label="Treasure Coast Today"><span class="wordmark-tct">TCT</span><span class="wordmark-divider"></span><span class="wordmark-full">TREASURE<br>COAST<br>TODAY</span></a>
      </div>
      <nav class="category-nav">
        {nav_buttons}
        <a href="/weather.html" class="cat-btn" style="text-decoration:none">Weather</a>
        <a href="/archive.html" class="cat-btn" style="text-decoration:none">Archive</a>
      </nav>
      <div class="header-actions">
        <a href="/advertise.html" class="support-btn" style="text-decoration:none">Advertise</a>
      </div>
    </div>
  </header>
  <div class="newsroom-strip">
    <div class="newsroom-strip-inner">
      <span class="newsroom-local-label">Local news for Martin, St. Lucie &amp; Indian River counties</span>
      <div class="newsroom-live-tools" aria-label="Current Treasure Coast time and weather">
        <time id="tct-live-time" class="newsroom-live-time" datetime=""></time>
        <a id="tct-live-weather" class="newsroom-live-weather" href="/weather.html" aria-label="View local weather">
          <span id="tct-weather-icon" class="newsroom-weather-icon" aria-hidden="true">◌</span>
          <span id="tct-weather-temp">--°</span>
          <span id="tct-weather-condition">Local weather</span>
        </a>
      </div>
    </div>
  </div>
  <main class="homepage-v2">
    <div class="lead-layout">
      <div class="lead-primary">{heroes_html}</div>
      <aside class="latest-rail">
        <div class="latest-rail-title"><span>◷</span><h2>Latest News</h2></div>
        <div class="latest-list">{latest_items_html}</div>
        <a class="latest-more" href="/archive.html">View all latest news →</a>
      </aside>
    </div>
    <section class="top-stories-v2">
      <div class="section-kicker"><span>☆</span><h2>Top Stories</h2></div>
      <div class="articles-grid" id="articlesGrid">{cards_html}</div>
    </section>
    <div class="county-panels-grid">{county_panels_html}</div>
    {older_section}
  </main>
{_footer}
{_live_masthead_script}
</body>
</html>"""


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:80].strip("-")


def _weather_phenomenon(event):
    """Group NWS event names into a stable phenomenon key so a Watch and the
    later Warning for the SAME hazard share one article (updated, not duplicated)."""
    e = (event or "").lower()
    if "hurricane" in e:            return "hurricane"
    if "tropical storm" in e:       return "tropical-storm"
    if "storm surge" in e:          return "storm-surge"
    if "tornado" in e:              return "tornado"
    if "flash flood" in e:          return "flash-flood"
    if "flood" in e:                return "flood"
    if "severe thunderstorm" in e:  return "severe-thunderstorm"
    if "extreme wind" in e:         return "extreme-wind"
    if "high wind" in e or "wind" in e: return "wind"
    if "fire" in e or "red flag" in e:  return "fire"
    # Fallback: slugify the event name
    return re.sub(r"[^a-z0-9]+", "-", e).strip("-") or "weather"


def _rewrite_alert_to_article(event, area, severity, headline_txt, desc, instr):
    """Rewrite an NWS alert into a short article in the site's voice. Falls back
    to the official NWS text if the rewrite fails — safety info must never be lost."""
    source = "\n\n".join(filter(None, [
        f"Alert: {event}",
        f"Area: {area}" if area else "",
        f"NWS headline: {headline_txt}" if headline_txt else "",
        f"Details: {desc}" if desc else "",
        f"Safety instructions: {instr}" if instr else "",
    ]))
    prompt = (
        "You are writing a brief, factual local news article about an active National Weather "
        "Service alert for the Treasure Coast of Florida (Martin, St. Lucie, Indian River counties).\n\n"
        f"Official NWS alert information:\n\n{source}\n\n"
        "Write a clear, calm, factual news article of 3-5 short paragraphs. Lead with what the alert "
        "is, who it affects, and when it is in effect. Include the concrete details (timing, locations, "
        "expected conditions, hazards). Preserve all safety instructions accurately in your own words — "
        "do not omit or soften them. Do not invent details not in the source. Do not use alarmist "
        "language, but convey appropriate seriousness. Plain, direct English. No em dashes. "
        "Write only the article body, no headline."
    )
    try:
        resp = client.messages.create(
            model=MODEL_ARTICLES,
            max_tokens=900,
            messages=[{"role": "user", "content": prompt}],
        )
        out = resp.content[0].text.strip()
        if out and len(out.split()) >= 40:
            return strip_markdown(out, "")
    except Exception as e:
        print(f"  Alert rewrite failed ({e}); using official NWS text")
    # Fallback: official text, never lose safety info
    parts = []
    if headline_txt: parts.append(headline_txt.strip())
    if desc: parts.append(desc)
    if instr: parts.append("What to do: " + instr)
    return "\n\n".join(parts)


def load_weather_alerts():
    """Fetch active Extreme/Severe NWS alerts for the three Treasure Coast counties
    and rewrite them into articles. As an event evolves (e.g. Hurricane Watch then
    Hurricane Warning for the same county), the SAME article updates in place rather
    than creating duplicates, via a stable phenomenon+county event key.

    County SAME codes: Martin FLC085, St. Lucie FLC111, Indian River FLC061.
    """
    from datetime import timezone as _tz
    import urllib.request

    ZONE_TO_COUNTY = {
        "FLC085": ("martin", "Martin County"),
        "FLC111": ("st_lucie", "St. Lucie County"),
        "FLC061": ("indian_river", "Indian River County"),
    }
    zones = ",".join(ZONE_TO_COUNTY.keys())
    url = f"https://api.weather.gov/alerts/active?zone={zones}"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "(treasurecoast.today, weather@treasurecoast.today)",
            "Accept": "application/geo+json",
        })
        raw = urllib.request.urlopen(req, timeout=12).read()
        data = json.loads(raw)
    except Exception as e:
        print(f"  NWS alert fetch failed: {e}")
        return []

    now = datetime.now(_tz.utc)
    features = data.get("features", [])

    # Group alerts by stable event key (phenomenon + affected counties). When both
    # a Watch and a Warning are active for the same hazard+area, keep the most
    # severe / most recent so we publish ONE current article for the event.
    events = {}
    for f in features:
        p = f.get("properties", {})
        severity = (p.get("severity", "") or "").lower()
        if severity not in ("extreme", "severe"):
            continue

        event = p.get("event", "Weather Alert")

        # Which of our counties this alert affects
        affected_zones = []
        for geo in p.get("geocode", {}).get("SAME", []):
            for zc in ZONE_TO_COUNTY:
                if geo.endswith(zc[3:]):
                    affected_zones.append(zc)
        if not affected_zones:
            for ugc in p.get("geocode", {}).get("UGC", []):
                if ugc in ZONE_TO_COUNTY:
                    affected_zones.append(ugc)
        affected_zones = list(dict.fromkeys(affected_zones))
        if not affected_zones:
            continue

        county_keys = tuple(sorted(ZONE_TO_COUNTY[z][0] for z in affected_zones))
        phenom = _weather_phenomenon(event)
        event_key = f"{phenom}:{'-'.join(county_keys)}"

        # Sort key: severity rank, then most recent sent time
        sev_rank = 0 if severity == "extreme" else 1
        sent = p.get("sent", "") or ""
        cand = (sev_rank, p, severity, affected_zones)

        prev = events.get(event_key)
        if prev is None:
            events[event_key] = cand
        else:
            # Prefer extreme over severe; among equal severity, prefer the newer sent
            if sev_rank < prev[0]:
                events[event_key] = cand
            elif sev_rank == prev[0] and sent > (prev[1].get("sent", "") or ""):
                events[event_key] = cand

    articles = []
    for event_key, (sev_rank, p, severity, affected_zones) in events.items():
        event = p.get("event", "Weather Alert")
        area  = p.get("areaDesc", "")
        desc  = (p.get("description", "") or "").strip()
        instr = (p.get("instruction", "") or "").strip()
        headline_txt = p.get("headline", "")

        # Route: single county -> that county; multiple -> front-page via florida
        if len(affected_zones) == 1:
            ckey, clabel = ZONE_TO_COUNTY[affected_zones[0]]
        else:
            ckey, clabel = ("florida", "Florida")

        # Urgency: full strength through the active window, then decay over the
        # two hours after expiry, then drop out.
        ends    = p.get("ends") or p.get("expires")
        base    = 10 if severity == "extreme" else 8
        urgency = base
        exp_date = None
        try:
            end_dt = datetime.fromisoformat(ends.replace("Z", "+00:00")).astimezone(_tz.utc)
            exp_date = (end_dt + timedelta(hours=2)).strftime("%Y-%m-%d")
            mins_past_end = (now - end_dt).total_seconds() / 60
            if mins_past_end <= 0:
                urgency = base
            elif mins_past_end <= 60:
                urgency = base - 1
            elif mins_past_end <= 120:
                urgency = base - 3
            else:
                continue  # More than 2h past expiry — no longer news
        except Exception:
            pass
        urgency = max(4, urgency)

        # Rewrite into article voice (falls back to official text on failure)
        body = _rewrite_alert_to_article(event, area, severity, headline_txt, desc, instr)

        area_short = area.split(";")[0].strip() if area else clabel
        headline = f"{event} issued for {area_short}"

        # STABLE link keyed on the event, NOT the volatile NWS alert id. This is
        # what makes an upgrade (Watch -> Warning) update the same article in place.
        stable_link = f"{SITE_URL}/weather-alert/{event_key}"

        articles.append({
            "headline":       headline,
            "body":           body,
            "teaser":         (headline_txt or desc[:180]).strip(),
            "category":       ckey,
            "category_key":   ckey,
            "category_label": clabel,
            "image_url":      "",
            "published":      now.strftime("%a, %d %b %Y %H:%M:%S +0000"),
            "published_raw":  now.strftime("%a, %d %b %Y %H:%M:%S +0000"),
            "expires":        exp_date or now.strftime("%Y-%m-%d"),
            "urgency_score":  urgency,
            "enriched":       True,
            "is_weather_alert": True,
            "weather_event_key": event_key,
            "force_hero":     severity == "extreme",
            "link":           stable_link,
        })
        print(f"  Weather alert [{severity}]: '{headline[:55]}' -> {ckey} (urgency {urgency}, key {event_key})")

    return articles


def load_custom_articles():
    """Load manually-submitted custom articles from custom_articles.json.

    Each article supports the same treatment as news articles: scored, ranked,
    archived, and expired. Override flags:
      - force_hero: true    -> pin as that category's hero
      - pin_position: N     -> lock to grid slot N (1-indexed) regardless of score
      - unique_slug: true   -> always get a fresh permalink; never overwrite a prior
                               article. Use for recurring series (weekly traffic
                               reports, roundups) whose editions share a title prefix
                               and would otherwise overwrite each other.
      - slug: "custom-slug" -> use this exact permalink (also implies unique_slug)

    Expected schema per entry:
      {
        "headline": "...",
        "body": "full article text",
        "category": "local_gov",
        "image_url": "https://... (optional)",
        "published": "Wed, 02 Jul 2026 14:00:00 +0000",
        "expires": "2026-07-10",
        "force_hero": false,
        "pin_position": null,
        "urgency_score": 7
      }
    """
    path = OUTPUT_DIR / "custom_articles.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  custom_articles.json parse error: {e}")
        return []

    from datetime import timezone as _tz
    now = datetime.now(_tz.utc)
    live = []
    for art in data:
        # Skip expired
        expires = art.get("expires", "")
        if expires:
            try:
                exp_dt = datetime.strptime(expires, "%Y-%m-%d").replace(tzinfo=_tz.utc)
                if now > exp_dt + timedelta(days=1):
                    continue
            except Exception:
                pass
        if not art.get("headline") or not art.get("body") or not art.get("category"):
            continue
        # Normalize into the same shape as generated articles
        art["is_custom"]       = True
        art["enriched"]        = True
        art["link"]            = art.get("link", f"{SITE_URL}/")
        art["source_quality"]  = "full"
        art["source_type"]     = "custom"
        art.setdefault("urgency_score", 6)
        art.setdefault("teaser", art["body"][:180].rstrip())
        art.setdefault("published", now.strftime("%a, %d %b %Y %H:%M:%S %z"))
        art["published_raw"]   = art.get("published_raw", art["published"])
        # Display-format the timestamp like every other article ("A few minutes ago",
        # "3:45 PM ET", "Jul 15, 3:45 PM ET"). Without this, the raw RFC-822 string
        # (e.g. "Fri, 17 Jul 2026 21:57:35 -0400") leaked onto the card, exposing the
        # -0400 offset. Keep the raw value in published_raw for sorting and RSS.
        art["published"] = format_age(art["published_raw"]) or art["published_raw"]
        live.append(art)
    if live:
        print(f"  Custom articles loaded: {len(live)}")
    return live


def load_archive(archive_path):
    try:
        if archive_path.exists():
            return json.loads(archive_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def render_article_page(hero, category_label, category_key, pub_date, slug, related=None):
    """Render a permanent article page for a single TCT story."""
    # Published + updated timestamps for the byline area. Prefer the article's real
    # first-published time; fall back to the pub_date passed in. "Updated" only shows
    # when it differs from published (a genuinely revised story).
    def _fmt_full(raw):
        # "July 18, 2026 at 3:45 PM ET" from an RFC-822 string; falls back to raw.
        try:
            from email.utils import parsedate_to_datetime
            from datetime import timezone as _tz, timedelta as _td
            et = _tz(_td(hours=-4))
            dt = parsedate_to_datetime(raw).astimezone(et)
            hour = dt.hour % 12 or 12
            ampm = "AM" if dt.hour < 12 else "PM"
            months = ["January","February","March","April","May","June","July",
                      "August","September","October","November","December"]
            return f"{months[dt.month-1]} {dt.day}, {dt.year} at {hour}:{dt.strftime('%M')} {ampm} ET"
        except Exception:
            return raw or ""
    # Published time is OURS: when the article first appeared on this site, never the
    # source/RSS publish time. Use first_published (full Eastern timestamp set when the
    # article is first archived); fall back only to the archive date, never to
    # published_raw (which for feed articles is the original source's timestamp).
    _pub_raw = hero.get("first_published") or hero.get("date", "") or pub_date
    _pub_display = _fmt_full(_pub_raw) if _pub_raw else pub_date
    # editorial_updated_at advances only when the reader-visible canonical payload
    # changes. Routine workflow runs, HTML regeneration, sitemap maintenance, and
    # duplicate checks never touch it.
    _modified_raw = hero.get("editorial_updated_at") or _pub_raw or pub_date
    _updated_display = _fmt_full(hero.get("editorial_updated_at")) if hero.get("editorial_updated_at") else ""

    description = (hero.get("teaser") or hero.get("body", "")[:155]).replace('"', '')
    # Only use images from reliable/stable sources for og:image
    # Hotlinked CDN images from Google News or unknown sources may break on social sharing
    _reliable_domains = ["wptv.com", "wpbf.com", "cbs12.com", "treasurecoast.today", "wflx.com"]
    _hero_img = hero.get("image_url", "")
    _cat_og   = f"{SITE_URL}/og-{category_key}.png"
    image_url = _hero_img if (_hero_img and any(d in _hero_img for d in _reliable_domains)) else _cat_og
    structured_data = {
        "@context": "https://schema.org",
        "@type":    "NewsArticle",
        "headline": hero.get("headline", "")[:110],
        "description": description,
        "image":    [image_url] if image_url else [],
        "datePublished": _pub_raw or pub_date,
        "dateModified":  _modified_raw,
        "author":    {
            "@type": "Person",
            "name":  "Andrew Dobrow",
            "url":   f"{SITE_URL}/author/andrew-dobrow.html",
        },
        "publisher": {
            "@type": "Organization",
            "name":  SITE_NAME,
            "url":   SITE_URL,
            "logo":  {
                "@type": "ImageObject",
                "url":    f"{SITE_URL}/logo.png",
                "width":  1200,
                "height": 120,
            },
        },
        "articleSection": category_label,
        "url":            f"{SITE_URL}/articles/{slug}.html",
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id":   f"{SITE_URL}/articles/{slug}.html",
        },
        "isAccessibleForFree": True,
    }
    import json as _json
    schema_tag = f'  <script type="application/ld+json">{_json.dumps(structured_data)}</script>'
    body       = make_paragraphs(hero.get("body", ""))

    # Optional user-service link for Things To Do coverage. This is an official event,
    # venue, ticket, or registration page extracted from a real href in the source page,
    # not a link back to the reporting outlet. No confident link means no box.
    event_link_html = ""
    if (category_key == "things_to_do"
            and str(hero.get("event_url", "")).startswith(("https://", "http://"))):
        import html as _html_escape
        _event_url = _html_escape.escape(str(hero.get("event_url", "")), quote=True)
        _event_label = _html_escape.escape(
            str(hero.get("event_link_text") or "Visit the official event page")
        )
        event_link_html = f'''
      <aside class="event-link-box">
        <span class="event-link-kicker">Planning to go?</span>
        <a href="{_event_url}" target="_blank" rel="noopener noreferrer external">{_event_label} &rarr;</a>
        <small>Event details, schedules and ticket availability may change.</small>
      </aside>'''

    img_html   = ""
    _art_img   = hero.get("image_url", "")
    if not _art_img:
        # No real image — use the category fallback so the page isn't text-only.
        # Never use the og-*.png social-share image here; those are for social cards.
        _fb, _ = get_fallback_image(category_key, hero.get("headline", ""))
        if not _fb:
            _fb, _ = get_fallback_image("top_news", hero.get("headline", ""))
        _art_img = _fb or f"{SITE_URL}/images/fallback/local_gov-1.jpg"
    if _art_img:
        credit   = f'<figcaption class="img-credit">Photo: {hero["image_credit"]}</figcaption>' if hero.get("image_credit") else ""
        img_html = f'<figure class="article-hero-image"><img src="{_art_img}" alt="{hero["headline"]}" loading="eager">{credit}</figure>'

    head   = _page_head(
        f"{hero['headline']} | Treasure Coast Today",
        description,
        f"/articles/{slug}.html",
        structured_data=structured_data,
        image_url=image_url,
        article_meta={
            "published": _pub_raw or pub_date,
            "modified":  _modified_raw,
            "section":   category_label,
        },
    )
    header = _page_header(active=category_key)
    footer = _page_footer()

    # Share button variables
    import urllib.parse as _urlparse
    article_url  = f"{SITE_URL}/articles/{slug}.html"
    headline_enc = _urlparse.quote(hero.get("headline", ""))
    headline_js  = _json.dumps(hero.get("headline", ""))

    # Every article uses the same top banner slot. Ordinary stories show the paid
    # advertising creative. Sensitive stories use a restrained editorial notice or
    # an appropriate national support resource, preserving identical page geometry.
    _sensitive_terms = [
        "murder", "murdered", "homicide", "killed", "killing", "shooting", "shot dead",
        "stabbing", "stabbed", "rape", "raped", "sexual assault", "sexual battery",
        "molest", "molestation", "molested", "child abuse", "child porn", "child sex",
        "csam", "sex abuse", "sexual abuse", "abducted", "abduction", "kidnap",
        "human trafficking", "sex trafficking", "manslaughter", "fatal shooting",
        "domestic violence", "assault", "overdose death", "suicide", "dead body",
        "body found", "remains found", "fatal crash", "deadly crash",
    ]
    _sexual_terms = [
        "rape", "raped", "sexual assault", "sexual battery", "molest", "molestation",
        "molested", "child porn", "child sex", "csam", "sex abuse", "sexual abuse",
        "sex trafficking",
    ]
    _domestic_terms = ["domestic violence", "domestic abuse", "intimate partner violence"]
    _crisis_terms = ["suicide", "suicidal", "self-harm", "mental health crisis"]

    _hl_body = (hero.get("headline", "") + " " + hero.get("body", "")[:500]).lower()
    _is_sensitive = any(t in _hl_body for t in _sensitive_terms) or bool(hero.get("is_weather_alert"))

    def _editorial_notice(label, headline, copy, resource_html=""):
        return f'''
      <section class="article-banner-slot article-house-banner" aria-label="{label}">
        <div class="article-house-mark" aria-hidden="true">TCT</div>
        <div class="article-house-copy">
          <span class="article-house-label">{label}</span>
          <strong class="article-house-headline">{headline}</strong>
          <span class="article-house-text">{copy}</span>
        </div>
        {resource_html}
      </section>'''

    if any(t in _hl_body for t in _sexual_terms):
        _resource = '<a class="article-house-resource" href="https://rainn.org/" target="_blank" rel="noopener noreferrer external"><span>Confidential support</span><strong>RAINN: 800-656-HOPE (4673)</strong></a>'
        banner_slot = _editorial_notice(
            "Community Resource",
            "Support is available.",
            "Free, confidential help is available 24 hours a day.",
            _resource,
        )
    elif any(t in _hl_body for t in _domestic_terms):
        _resource = '<a class="article-house-resource" href="https://www.thehotline.org/" target="_blank" rel="noopener noreferrer external"><span>Confidential support</span><strong>Call 800-799-SAFE or text START to 88788</strong></a>'
        banner_slot = _editorial_notice(
            "Community Resource",
            "You are not alone.",
            "Confidential domestic violence support is available 24 hours a day.",
            _resource,
        )
    elif any(t in _hl_body for t in _crisis_terms):
        _resource = '<a class="article-house-resource" href="https://988lifeline.org/" target="_blank" rel="noopener noreferrer external"><span>Free and confidential</span><strong>Call or text 988</strong></a>'
        banner_slot = _editorial_notice(
            "Community Resource",
            "Help is available now.",
            "The 988 Lifeline provides free, confidential crisis support.",
            _resource,
        )
    elif _is_sensitive:
        banner_slot = _editorial_notice(
            "Editorial Notice",
            "Some stories are too important for commercial sponsorship.",
            "To maintain appropriate context, Treasure Coast Today does not display paid advertising alongside certain sensitive news coverage.",
        )
    else:
        banner_slot = (
            '      <a href="/advertise.html" class="article-banner-slot article-ad-banner" '
            'aria-label="Advertise with Treasure Coast Today">\n'
            '        <img src="/images/advertise-banner.png" '
            'alt="Advertise with Treasure Coast Today. Reach Martin, St. Lucie and Indian River readers every day">\n'
            '      </a>'
        )

    # Related stories — same category, most recent, excluding this article
    items = ""
    for r in (related or [])[:5]:
        items += f"""
        <li class="related-item">
          <a href="/articles/{r['slug']}.html" class="related-link">
            <span class="related-headline">{r['headline']}</span>
            <span class="related-date">{r.get('date','')}</span>
          </a>
        </li>"""
    if items:
        related_html = f"""
      <section class="related-section">
        <h2 class="related-title">Related {category_label} Stories</h2>
        <ul class="related-list">{items}
        </ul>
      </section>"""
    else:
        related_html = f"""
      <section class="related-section related-section-fallback">
        <h2 class="related-title">More Local News</h2>
        <p class="related-empty">Browse the latest reporting from across the Treasure Coast.</p>
        <a class="related-more-link" href="/?cat={category_key}">View {category_label} stories &rarr;</a>
      </section>"""

    _urgency_text = f"{category_label} {hero.get('headline','')}".strip().lower()
    urgency_cls = " live" if _urgency_text.startswith("live") else (" developing" if _urgency_text.startswith("developing") else (" breaking" if hero.get("is_breaking") or _urgency_text.startswith("breaking") else ""))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
  <style>
    .article-wrap {{ max-width: 1180px; margin: 0 auto; padding: 52px 28px 96px; position: relative; }}
    .article-banner-slot {{ width: min(100%, 970px); margin: 0 auto 30px; }}
    .article-ad-banner {{ display: block; height: auto; max-height: none; aspect-ratio: auto; background: transparent; border: 0; border-radius: 0; overflow: visible; box-shadow: none; }}
    .article-ad-banner img {{ width: 100%; height: auto; max-height: none; display: block; object-fit: contain; border-radius: 10px; }}
    .article-house-banner {{ min-height: 0; aspect-ratio: 970 / 250; max-height: 250px; overflow: hidden; border-radius: 12px; }}
    .article-house-banner {{ position: relative; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: clamp(16px, 3vw, 32px); padding: clamp(20px, 3vw, 34px); background: linear-gradient(115deg, #f8fbfa 0%, #ffffff 68%); border: 1px solid var(--border); border-top: 4px solid var(--accent); box-shadow: 0 8px 26px rgba(9, 15, 15, .05); }}
    .article-house-banner::after {{ content: ""; position: absolute; right: -48px; bottom: -76px; width: 220px; height: 220px; border: 1px solid rgba(10, 112, 117, .10); border-radius: 50%; pointer-events: none; }}
    .article-house-mark {{ width: clamp(54px, 7vw, 78px); aspect-ratio: 1; display: grid; place-items: center; border-radius: 50%; background: var(--accent); color: white; font-family: "Fraunces", serif; font-size: clamp(18px, 2.4vw, 25px); font-weight: 700; letter-spacing: -.04em; }}
    .article-house-copy {{ min-width: 0; display: grid; gap: 5px; position: relative; z-index: 1; }}
    .article-house-label {{ width: fit-content; padding: 3px 8px; border-radius: 999px; background: rgba(10, 112, 117, .10); color: var(--accent); font-size: 9px; font-weight: 800; letter-spacing: .11em; line-height: 1.4; text-transform: uppercase; }}
    .article-house-headline {{ color: var(--text); font-family: "Fraunces", serif; font-size: clamp(19px, 2.4vw, 29px); line-height: 1.12; letter-spacing: -.025em; text-wrap: balance; }}
    .article-house-text {{ max-width: 650px; color: var(--text-secondary); font-size: clamp(11px, 1.3vw, 14px); line-height: 1.45; }}
    .article-house-resource {{ position: relative; z-index: 1; min-width: 205px; max-width: 260px; padding: 13px 15px; border: 1px solid rgba(10, 112, 117, .22); border-radius: 10px; background: rgba(255,255,255,.82); color: var(--text); text-decoration: none; display: grid; gap: 3px; }}
    .article-house-resource span {{ color: var(--text-muted); font-size: 9px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }}
    .article-house-resource strong {{ color: var(--accent); font-size: 12px; line-height: 1.35; }}
    .article-house-resource:hover {{ border-color: var(--accent); }}
    .article-meta {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; flex-wrap: wrap; }}
    .article-category {{ font-size: 10px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--accent); }}
    .article-date {{ font-size: 11px; color: var(--text-muted); }}
    .article-byline {{ font-size: 13px; color: var(--text-secondary); }}
    .article-byline a {{ color: var(--text); font-weight: 600; text-decoration: none; }}
    .article-byline a:hover {{ text-decoration: underline; }}
    .article-times {{ display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 22px; }}
    .article-published {{ font-size: 12px; color: var(--text-muted); }}
    .article-headline {{ max-width: 920px; font-family: "Fraunces", serif; font-size: clamp(38px, 5vw, 68px); font-weight: 600; line-height: 1.02; letter-spacing: -.045em; color: var(--text); margin: 0 0 38px; text-wrap: balance; overflow-wrap: anywhere; }}
    .article-editorial-grid {{ display: grid; grid-template-columns: minmax(0, 760px) minmax(260px, 320px); gap: clamp(42px, 6vw, 82px); align-items: start; }}
    .article-main-column {{ min-width: 0; }}
    .article-side-rail {{ min-width: 0; position: sticky; top: 118px; display: grid; gap: 24px; }}
    .article-side-rail .related-section {{ margin: 0; padding: 24px; border: 1px solid var(--border); border-top: 4px solid var(--accent); border-radius: 10px; background: var(--surface); }}
    .article-side-rail .related-title {{ margin: 0 0 16px; font-family: "Fraunces", serif; font-size: 22px; line-height: 1.15; }}
    .article-side-rail .related-list {{ list-style: none; padding: 0; margin: 0; }}
    .article-side-rail .related-item {{ padding: 14px 0; border-top: 1px solid var(--border); }}
    .article-side-rail .related-item:first-child {{ border-top: 0; padding-top: 0; }}
    .article-side-rail .related-link {{ display: grid; gap: 6px; color: inherit; text-decoration: none; }}
    .article-side-rail .related-headline {{ font-weight: 700; line-height: 1.28; }}
    .article-side-rail .related-date {{ font-size: 11px; color: var(--text-muted); }}
    .article-side-rail .related-empty {{ margin: 0 0 14px; color: var(--text-secondary); font-size: 14px; line-height: 1.55; }}
    .article-side-rail .related-more-link {{ color: var(--accent); font-size: 13px; font-weight: 700; text-decoration: none; }}
    .article-side-rail .related-more-link:hover {{ text-decoration: underline; }}
    .article-hero-image {{ margin: 0 0 34px; width: 100%; }}
    .article-hero-image img {{ width: 100%; aspect-ratio: 16 / 9; max-height: 560px; object-fit: cover; border-radius: 12px; display: block; }}
    .article-body p {{ font-size: 17px; line-height: 1.86; color: var(--text-secondary); margin-bottom: 22px; text-wrap: pretty; }}
    .article-body blockquote {{ margin: 34px 0; padding: 4px 0 4px 24px; border-left: 4px solid var(--accent); font-family: "Fraunces", serif; font-size: 22px; line-height: 1.5; color: var(--text); }}
    .article-reading-progress {{ position: fixed; top: 0; left: 0; z-index: 10000; width: 0; height: 3px; background: var(--accent); pointer-events: none; transition: width 70ms linear; }}
    .article-body .article-section {{ font-family: "Fraunces", serif; font-size: 24px; font-weight: 600; color: var(--text); margin: 36px 0 14px; padding-bottom: 8px; border-bottom: 2px solid var(--border); }}
    .article-body .article-subhead {{ font-size: 18px; font-weight: 700; color: var(--text); margin: 26px 0 8px; }}
    .article-body strong {{ color: var(--text); font-weight: 700; }}
    .article-body a {{ color: var(--accent); text-decoration: underline; text-underline-offset: 2px; }}
    .article-body a:hover {{ text-decoration: none; }}
    .event-link-box {{ margin: 30px 0 8px; padding: 18px 20px; border: 1px solid var(--border); border-left: 4px solid var(--accent); border-radius: 10px; background: var(--surface); }}
    .event-link-kicker {{ display: block; margin-bottom: 7px; color: var(--text-muted); font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }}
    .event-link-box a {{ color: var(--accent); font-size: 16px; font-weight: 700; text-decoration: none; }}
    .event-link-box a:hover {{ text-decoration: underline; }}
    .event-link-box small {{ display: block; margin-top: 8px; color: var(--text-muted); font-size: 11px; line-height: 1.5; }}
    .article-share {{ margin: 36px 0 8px; padding: 20px 0; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }}
    .article-share-label {{ display: block; font-size: 13px; font-weight: 600; color: var(--text); margin-bottom: 12px; text-transform: uppercase; letter-spacing: .05em; }}
    .article-share-btns {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .article-share-btns button, .article-share-btns a {{
      display: inline-flex; align-items: center; gap: 7px; padding: 9px 15px;
      font-size: 14px; font-weight: 500; font-family: inherit; border-radius: 8px;
      cursor: pointer; text-decoration: none; border: 1px solid var(--border);
      background: var(--bg); color: var(--text); transition: all .15s;
    }}
    .article-share-btns button:hover, .article-share-btns a:hover {{ border-color: var(--accent); color: var(--accent); }}
    .article-share-btns .share-fb:hover {{ background: #1877F2; border-color: #1877F2; color: #fff; }}
    .article-share-btns .share-x:hover {{ background: #000; border-color: #000; color: #fff; }}
    .article-share-btns .share-native {{ background: var(--accent); border-color: var(--accent); color: #fff; }}
    .article-share-btns .share-native:hover {{ background: #08595d; border-color: #08595d; color: #fff; }}
    .article-back {{ display: inline-block; font-size: 13px; color: var(--accent); text-decoration: none; margin-bottom: 32px; font-weight: 500; }}
    .article-back:hover {{ opacity: .7; }}
    .article-divider {{ border: none; border-top: 1px solid var(--border); margin: 40px 0; }}
    .article-more {{ font-family: "Fraunces", serif; font-size: 20px; font-weight: 500; color: var(--text); margin-bottom: 16px; }}
    .article-more-link {{ display: inline-block; color: var(--accent); font-size: 14px; font-weight: 500; text-decoration: none; }}
    .article-more-link:hover {{ opacity: .7; }}

    @media (max-width: 900px) {{
      .article-wrap {{ padding: 34px 20px 72px; }}
      .article-banner-slot {{ width: 100%; height: auto; min-height: 0; max-height: none; margin-bottom: 22px; }}
      .article-ad-banner {{ aspect-ratio: auto; overflow: visible; border-radius: 0; }}
      .article-house-banner {{ aspect-ratio: auto; max-height: none; border-radius: 10px; overflow: visible; }}
      .article-house-banner {{ display: block; grid-template-columns: none; min-height: 0; padding: 16px 17px 17px; }}
      .article-house-mark {{ display: none; }}
      .article-house-copy {{ display: block; width: 100%; gap: 0; }}
      .article-house-label {{ display: inline-block; margin: 0 0 8px; font-size: 8px; padding: 2px 7px; }}
      .article-house-headline {{ display: block; margin: 0 0 7px; overflow: visible; -webkit-box-orient: initial; -webkit-line-clamp: unset; line-clamp: unset; font-size: clamp(17px, 4.8vw, 21px); line-height: 1.1; text-wrap: wrap; white-space: normal; text-overflow: clip; }}
      .article-house-text {{ display: block; margin: 0; max-width: none; font-size: clamp(11px, 3.1vw, 13px); line-height: 1.4; }}
      .article-house-resource {{ display: block; margin: 11px 0 0; min-width: 0; max-width: none; padding: 9px 10px; }}
      .article-house-resource span {{ display: block; }}
      .article-house-resource strong {{ display: block; font-size: 10px; line-height: 1.3; }}
      .article-editorial-grid {{ grid-template-columns: 1fr; gap: 40px; }}
      .article-side-rail {{ position: static; display: grid; }}
      .article-headline {{ font-size: clamp(34px, 9vw, 54px); margin-bottom: 28px; }}
      .article-hero-image img {{ max-height: none; }}
    }}
  </style>
</head>
<body>
  <div class="article-reading-progress" aria-hidden="true"></div>
{header}
  <div class="newsroom-strip">
    <div class="newsroom-strip-inner">
      <span class="newsroom-local-label">Local news for Martin, St. Lucie &amp; Indian River counties</span>
      <div class="newsroom-live-tools" aria-label="Current Treasure Coast time and weather">
        <time id="tct-live-time" class="newsroom-live-time" datetime=""></time>
        <a id="tct-live-weather" class="newsroom-live-weather" href="/weather.html" aria-label="View local weather">
          <span id="tct-weather-icon" class="newsroom-weather-icon" aria-hidden="true">◌</span>
          <span id="tct-weather-temp">--°</span>
          <span id="tct-weather-condition">Local weather</span>
        </a>
      </div>
    </div>
  </div>
  <main>
    <div class="article-wrap">
{banner_slot}
      <div class="article-meta">
        <span class="article-category{urgency_cls}">{category_label}</span>
        <span class="article-byline">By <a href="/author/andrew-dobrow.html" rel="author">Andrew Dobrow</a></span>
      </div>
      <div class="article-times">
        <span class="article-published">Published {_pub_display}</span>
        {f'<span class="article-published">Updated {_updated_display}</span>' if _updated_display else ''}
      </div>
      <h1 class="article-headline">{hero["headline"]}</h1>
      <div class="article-editorial-grid">
        <div class="article-main-column">
          {img_html}
          <div class="article-body">{body}</div>
          {event_link_html}
          <div class="article-share">
            <span class="article-share-label">Share this story</span>
            <div class="article-share-btns">
              <button class="share-native" onclick="tctShare()" aria-label="Share">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
                Share
              </button>
              <a class="share-fb" href="https://www.facebook.com/sharer/sharer.php?u={article_url}" target="_blank" rel="noopener" aria-label="Share on Facebook">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.07C24 5.4 18.63 0 12 0S0 5.4 0 12.07C0 18.1 4.39 23.1 10.13 24v-8.44H7.08v-3.49h3.05V9.41c0-3.02 1.79-4.69 4.53-4.69 1.31 0 2.69.24 2.69.24v2.97h-1.51c-1.49 0-1.96.93-1.96 1.89v2.25h3.33l-.53 3.49h-2.8V24C19.61 23.1 24 18.1 24 12.07z"/></svg>
                Facebook
              </a>
              <a class="share-x" href="https://twitter.com/intent/tweet?url={article_url}&text={headline_enc}" target="_blank" rel="noopener" aria-label="Share on X">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M18.9 1.15h3.68l-8.04 9.19L24 22.85h-7.41l-5.8-7.58-6.64 7.58H.47l8.6-9.83L0 1.15h7.6l5.24 6.93zM17.6 20.64h2.04L6.49 3.24H4.3z"/></svg>
                X
              </a>
              <button class="share-copy" onclick="tctCopyLink(this)" aria-label="Copy link">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
                Copy link
              </button>
            </div>
          </div>
          <hr class="article-divider">
          <p class="article-more">More local news</p>
          <a href="/?cat={category_key}" class="article-more-link">More {category_label} &rarr;</a>
        </div>
        <aside class="article-side-rail">{related_html}</aside>
      </div>
    </div>
  </main>
{footer}
<script>
function tctUpdateReadingProgress() {{
  const bar = document.querySelector('.article-reading-progress');
  if (!bar) return;
  const root = document.documentElement;
  const max = root.scrollHeight - root.clientHeight;
  const pct = max > 0 ? Math.min(100, Math.max(0, (root.scrollTop / max) * 100)) : 0;
  bar.style.width = pct + '%';
}}
window.addEventListener('scroll', tctUpdateReadingProgress, {{ passive: true }});
window.addEventListener('resize', tctUpdateReadingProgress);
tctUpdateReadingProgress();

function tctShare() {{
  const data = {{ title: document.title, text: {headline_js}, url: window.location.href }};
  if (navigator.share) {{ navigator.share(data).catch(function(){{}}); }}
  else {{ tctCopyLink(document.querySelector('.share-copy')); }}
}}
function tctCopyLink(btn) {{
  navigator.clipboard.writeText(window.location.href).then(function() {{
    if (!btn) return;
    const orig = btn.innerHTML;
    btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Copied';
    setTimeout(function() {{ btn.innerHTML = orig; }}, 1500);
  }}).catch(function(){{}});
}}
</script>

<script>
(() => {{
  const timeEl = document.getElementById('tct-live-time');
  const weatherEl = document.getElementById('tct-live-weather');
  const iconEl = document.getElementById('tct-weather-icon');
  const tempEl = document.getElementById('tct-weather-temp');
  const conditionEl = document.getElementById('tct-weather-condition');
  function updateClock() {{
    if (!timeEl) return;
    const now = new Date();
    const datePart = new Intl.DateTimeFormat('en-US', {{timeZone:'America/New_York',weekday:'short',month:'short',day:'numeric'}}).format(now);
    const timePart = new Intl.DateTimeFormat('en-US', {{timeZone:'America/New_York',hour:'numeric',minute:'2-digit',hour12:true,timeZoneName:'short'}}).format(now);
    timeEl.textContent = `${{datePart}} · ${{timePart}}`;
    timeEl.dateTime = now.toISOString();
  }}
  const codes={{0:['☀','Clear'],1:['🌤','Mostly clear'],2:['⛅','Partly cloudy'],3:['☁','Cloudy'],45:['🌫','Fog'],48:['🌫','Fog'],51:['🌦','Light drizzle'],53:['🌦','Drizzle'],55:['🌧','Heavy drizzle'],61:['🌦','Light rain'],63:['🌧','Rain'],65:['🌧','Heavy rain'],80:['🌦','Rain showers'],81:['🌧','Rain showers'],82:['⛈','Heavy showers'],95:['⛈','Thunderstorms'],96:['⛈','Storms with hail'],99:['⛈','Storms with hail']}};
  function paint(d){{if(!d||typeof d.temperature!=='number')return;const [i,l]=codes[d.code]||['◌','Local weather'];iconEl.textContent=i;tempEl.textContent=`${{Math.round(d.temperature)}}°`;conditionEl.textContent=l;weatherEl.title=`Treasure Coast: ${{Math.round(d.temperature)}}°F, ${{l}}`;}}
  async function updateWeather(){{if(!weatherEl)return;const key='tct-weather-v1',age=20*60*1000;try{{const c=JSON.parse(localStorage.getItem(key)||'null');if(c&&Date.now()-c.savedAt<age){{paint(c);return;}}}}catch(_){{}}try{{const r=await fetch('https://api.open-meteo.com/v1/forecast?latitude=27.1975&longitude=-80.2528&current=temperature_2m,weather_code&temperature_unit=fahrenheit&timezone=America%2FNew_York',{{cache:'no-store'}});if(!r.ok)throw new Error();const j=await r.json();const d={{temperature:j.current&&j.current.temperature_2m,code:j.current&&j.current.weather_code,savedAt:Date.now()}};paint(d);try{{localStorage.setItem(key,JSON.stringify(d));}}catch(_){{}}}}catch(_){{if(conditionEl)conditionEl.textContent='Local weather';}}}}
  updateClock();setInterval(updateClock,30000);updateWeather();setInterval(updateWeather,20*60*1000);
}})();
</script>
</body>
</html>"""


def render_archive_page(archive_entries):
    by_month = defaultdict(list)
    for e in sorted(archive_entries, key=lambda x: x.get("date",""), reverse=True):
        try:
            month = e["date"][:7]
            label = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
        except Exception:
            label = "Recent"; month = "recent"
        by_month[(month, label)].append(e)

    months_html = ""
    for (month_key, month_label), entries in sorted(by_month.items(), reverse=True):
        items = ""
        for e in entries:
            items += f"""
        <li class="archive-item">
          <a href="/articles/{e['slug']}.html" class="archive-link">
            <span class="archive-cat">{e['category_label']}</span>
            <span class="archive-headline">{e['headline']}</span>
            <span class="archive-date">{e['date']}</span>
          </a>
        </li>"""
        months_html += f"""
      <div class="archive-month">
        <h2 class="archive-month-label">{month_label}</h2>
        <ul class="archive-list">{items}
        </ul>
      </div>"""

    head   = _page_head(
        "Article Archive — Treasure Coast Today",
        "Browse all local news articles from Treasure Coast Today covering Martin, St. Lucie, and Indian River counties.",
        "/archive.html"
    )
    header = _page_header(active="archive")
    footer = _page_footer()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
  <style>
    .archive-wrap {{ max-width: 860px; margin: 0 auto; padding: 40px 24px 80px; }}
    .archive-eyebrow {{ font-size: 11px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: var(--accent); display: block; margin-bottom: 14px; }}
    .archive-headline {{ font-family: "Fraunces", serif; font-size: clamp(28px,4vw,40px); font-weight: 600; color: var(--text); margin-bottom: 8px; letter-spacing: -.02em; }}
    .archive-sub {{ font-size: 15px; color: var(--text-secondary); margin-bottom: 48px; }}
    .archive-month {{ margin-bottom: 40px; }}
    .archive-month-label {{ font-family: "Fraunces", serif; font-size: 20px; font-weight: 500; color: var(--text); margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid var(--border); }}
    .archive-list {{ list-style: none; }}
    .archive-item {{ border-bottom: 1px solid var(--border); }}
    .archive-link {{ display: flex; align-items: baseline; gap: 10px; padding: 12px 0; text-decoration: none; color: inherit; flex-wrap: wrap; }}
    .archive-link:hover .archive-headline {{ color: var(--accent); }}
    .archive-cat {{ font-size: 10px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--accent); flex-shrink: 0; }}
    .archive-headline {{ font-size: 15px; font-weight: 500; color: var(--text); flex: 1; line-height: 1.4; }}
    .archive-date {{ font-size: 11px; color: var(--text-muted); flex-shrink: 0; margin-left: auto; }}
    @media(max-width:580px) {{ .archive-date {{ display: none; }} }}
  </style>
</head>
<body>
{header}
  <main>
    <div class="archive-wrap">
      <span class="archive-eyebrow">Archive</span>
      <h1 class="archive-headline">All Articles</h1>
      <p class="archive-sub">Every story published on Treasure Coast Today, organized by month.</p>
      {months_html}
    </div>
  </main>
{footer}
</body>
</html>"""


def render_rss_feed(all_categories, top_cat):
    """Generate an RSS feed featuring all articles (heroes and cards) from the run."""
    from email.utils import formatdate, parsedate_to_datetime

    now_rfc = formatdate(usegmt=True)
    archive = load_archive(OUTPUT_DIR / "archive.json")

    def make_item(article, cat_label):
        incoming_headline = article.get("headline", "")
        if not incoming_headline:
            return None, None
        matched = find_presentation_canonical(article, archive)
        if not matched:
            return None, None  # No canonical article page exists — skip

        # RSS must be serialized from the evolved canonical record, not from whichever
        # live card happened to match it during this run. Otherwise an older card can
        # point at the updated permalink while carrying the pre-update title/teaser,
        # which causes downstream automations such as Nextdoor to repost stale copy.
        headline = matched.get("headline") or incoming_headline
        teaser = (
            matched.get("teaser")
            or matched.get("body", "")[:300]
            or article.get("teaser")
            or article.get("body", "")[:300]
        )
        article_url = f"{SITE_URL}/articles/{matched['slug']}.html"
        rss_category = matched.get("category_label") or cat_label

        # A genuinely evolved canonical is re-emitted at its editorial update time.
        # Routine workflow runs never advance editorial_updated_at, so they cannot
        # manufacture a fresh RSS item. Unmodified stories retain first_published.
        from email.utils import parsedate_to_datetime as _pdt
        pub_raw = matched.get("editorial_updated_at") or matched.get("first_published")
        if not pub_raw:
            _d = matched.get("date", "")
            if _d:
                pub_raw = f"{_d} 09:00:00 -0400"  # legacy date-only rows
        try:
            pub = formatdate(_pdt(pub_raw).timestamp(), usegmt=True)
        except Exception:
            pub = now_rfc

        item = f"""  <item>
    <title><![CDATA[{headline}]]></title>
    <link>{article_url}</link>
    <guid isPermaLink="true">{article_url}</guid>
    <description><![CDATA[{teaser}]]></description>
    <pubDate>{pub}</pubDate>
    <category><![CDATA[{rss_category}]]></category>
  </item>"""
        return item, matched.get("slug") or article_url

    items = []
    seen  = set()

    # Front page hero first
    item, hl = make_item(top_cat["hero"], top_cat["category_label"])
    if item:
        items.append(item)
        seen.add(hl)

    # Every category hero + all cards
    for cat in all_categories:
        cat_label = cat["category_label"]
        articles  = [cat["hero"]] + cat.get("cards", [])
        for art in articles:
            item, hl = make_item(art, cat_label)
            if item and hl not in seen:
                items.append(item)
                seen.add(hl)

    items_xml = "\n".join(items)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Treasure Coast Today</title>
    <link>{SITE_URL}</link>
    <description>Local news for Martin, St. Lucie and Indian River counties, Florida.</description>
    <language>en-us</language>
    <lastBuildDate>{now_rfc}</lastBuildDate>
    <atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml" />
{items_xml}
  </channel>
</rss>"""


def update_sitemap(archive_entries):
    """Regenerate sitemap.xml with all static and article pages."""
    now_str = datetime.utcnow().strftime("%Y-%m-%d")
    static_urls = f"""  <url>
    <loc>{SITE_URL}/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
    <lastmod>{now_str}</lastmod>
  </url>
  <url>
    <loc>{SITE_URL}/archive.html</loc>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
    <lastmod>{now_str}</lastmod>
  </url>
  <url>
    <loc>{SITE_URL}/about.html</loc>
    <priority>0.5</priority>
  </url>
  <url>
    <loc>{SITE_URL}/advertise.html</loc>
    <priority>0.5</priority>
  </url>
  <url>
    <loc>{SITE_URL}/contact.html</loc>
    <priority>0.5</priority>
  </url>
  <url>
    <loc>{SITE_URL}/author/andrew-dobrow.html</loc>
    <priority>0.6</priority>
  </url>
  <url>
    <loc>{SITE_URL}/editorial-standards.html</loc>
    <priority>0.5</priority>
  </url>
  <url>
    <loc>{SITE_URL}/corrections-policy.html</loc>
    <priority>0.5</priority>
  </url>
  <url>
    <loc>{SITE_URL}/ownership.html</loc>
    <priority>0.5</priority>
  </url>
  <url>
    <loc>{SITE_URL}/privacy.html</loc>
    <priority>0.3</priority>
  </url>"""

    article_urls = ""
    for e in archive_entries:
        lastmod = e.get("lastmod") or e.get("date", "")
        article_urls += f"""
  <url>
    <loc>{SITE_URL}/articles/{e['slug']}.html</loc>
    <priority>0.7</priority>
    <lastmod>{lastmod}</lastmod>
  </url>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{static_urls}
{article_urls}
</urlset>"""


def update_news_sitemap(archive_entries):
    """Google News sitemap. Google News only accepts articles published in the last
    48 hours, ordered by publication time. Uses each article's real first-published
    Eastern timestamp (not a date-only midnight-UTC value, which mis-orders everything
    and puts articles in the wrong timezone)."""
    from datetime import timedelta, timezone as _tz
    from email.utils import parsedate_to_datetime, format_datetime
    now = datetime.now(_tz.utc)
    cutoff = now - timedelta(hours=48)

    def _iso(entry):
        # Prefer the real first-published timestamp; fall back to date at 9am ET.
        raw = entry.get("first_published") or ""
        try:
            dt = parsedate_to_datetime(raw)
        except Exception:
            dt = None
        if dt is None:
            d = entry.get("date", "")
            if not d:
                return None
            try:
                # date-only -> 9am Eastern (rough but valid), then to aware UTC
                et = _tz(timedelta(hours=-4))
                dt = datetime.strptime(d, "%Y-%m-%d").replace(hour=9, tzinfo=et)
            except Exception:
                return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_tz.utc)
        return dt

    # Build (datetime, entry) pairs within the 48h window, newest first
    recent = []
    for e in archive_entries:
        dt = _iso(e)
        if dt is not None and dt >= cutoff:
            recent.append((dt, e))
    recent.sort(key=lambda p: p[0], reverse=True)

    news_urls = ""
    for dt, e in recent:
        pub_date = dt.isoformat()  # W3C datetime with offset, e.g. 2026-07-18T15:30:25-04:00
        headline = e['headline'].replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')
        news_urls += f"""
  <url>
    <loc>{SITE_URL}/articles/{e['slug']}.html</loc>
    <news:news>
      <news:publication>
        <news:name>Treasure Coast Today</news:name>
        <news:language>en</news:language>
      </news:publication>
      <news:publication_date>{pub_date}</news:publication_date>
      <news:title>{headline}</news:title>
    </news:news>
  </url>"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
{news_urls}
</urlset>"""


ARCHIVE_STOPS = {"the","a","an","in","of","for","to","and","or","on","at","is","was","are",
                 "were","that","this","with","from","have","been","after","over","into","says",
                 "said","will","than","more","also","when","s","county","florida","treasure",
                 "coast","martin","lucie","indian","river","beach","port","city","news",
                 # Town-name tokens are geography, not story identity. Without these,
                 # any two Hobe Sound stories share 2 free tokens and need only 2
                 # generic words ("rising costs") to falsely merge — which is how an
                 # Aldi story overwrote a food-pantry story's URL. The location-
                 # conflict guard still uses full place phrases and is unaffected.
                 "hobe","sound","stuart","vero","pierce","jensen","sebastian",
                 "salerno","fellsmere","indiantown","tradition","jupiter","hutchinson"}

def _sig_tokens(text):
    return frozenset(w.lower().strip(".,;:()") for w in text.split()
                     if len(w) > 3 and w.lower() not in ARCHIVE_STOPS)


def _stem(w):
    """Light stemming so common variants collapse: hits/hitting/hit, seizes/seized,
    spreading/spread, prices/price. Not linguistically perfect, just enough to stop
    the same story being split into duplicate articles by a reworded headline."""
    for suf in ("ings", "ing", "ies", "ied", "ers", "er", "eds", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


# Words that describe PEOPLE or generic framing rather than the EVENT itself.
# Two stories sharing only these ("teen", "youth", "year", "southeast") are not the
# same story — a June award and a July World Cup trip about the same kid share all
# this boilerplate and none of the substance. A match must rest on distinctive words.
GENERIC_TOKENS = {
    "teen", "youth", "year", "years", "resident", "residents", "local", "woman",
    "man", "girl", "boy", "student", "students", "first", "named", "becomes",
    "become", "region", "people", "family", "home", "community", "area", "time",
    "week", "days", "gets", "sets", "takes", "make", "makes", "could", "would",
}


def _token_overlap(tok_a, tok_b):
    """Count shared tokens, treating word variants as matches. Handles:
      - stem equality (hits/hitting, seizes/seized)
      - prefix abbreviation (meth/methamphetamine)
    Without this, 'Methamphetamine surge hits...' and 'DEA... meth... spreading...'
    look like different stories and a duplicate article is created at a new URL,
    orphaning any link already published to RSS/social."""
    count = 0
    used = set()
    for a in tok_a:
        sa = _stem(a)
        for b in tok_b:
            if b in used:
                continue
            sb = _stem(b)
            if sa == sb:
                count += 1
                used.add(b)
                break
            # Prefix abbreviation: one is a leading substring of the other and the
            # shorter is at least 4 chars (meth -> methamphetamine)
            short, long_ = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
            if len(short) >= 4 and long_.startswith(short):
                count += 1
                used.add(b)
                break
    return count


def _shared_tokens(tok_a, tok_b):
    """The actual shared tokens (variant-aware), not just the count."""
    shared = []
    used = set()
    for a in tok_a:
        sa = _stem(a)
        for b in tok_b:
            if b in used:
                continue
            sb = _stem(b)
            short, long_ = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
            if sa == sb or (len(short) >= 4 and long_.startswith(short)):
                shared.append(a)
                used.add(b)
                break
    return shared


def _known_event_key(text):
    """Return a stable key for high-risk stories that repeatedly arrive with
    materially different syndicated headlines. These keys are intentionally narrow:
    they identify one specific event, not a broad topic.

    This prevents an already-published authoritative story from re-entering through
    another feed, becoming a hero, and only being noticed at permalink-write time.
    """
    t = re.sub(r"[^a-z0-9]+", " ", (text or "").lower())
    words = set(t.split())

    # July 2026 Stuart/Martin County animal-hoarding case involving about 80 cats.
    # Headline variants have used "80", "about 80", "rescued", "removed",
    # "arrested", and "worst hoarding case". Require several independent signals
    # so unrelated cat or animal-control stories never collide with it.
    has_place = ("stuart" in words or ("martin" in words and "county" in words))
    has_animals = bool(words & {"animal", "animals", "cat", "cats"})
    has_case = any(w in words for w in ("hoarding", "hoarder", "hoard"))
    has_action = any(w in words for w in ("rescue", "rescued", "remove", "removed",
                                            "deputies", "arrested", "arrest", "found",
                                            "response", "seized"))
    # Early official coverage said more than 70 animals; later reporting specified
    # about 80 cats. Those are count refinements, not separate events.
    has_scale = bool(words & {"70", "seventy", "80", "eighty"})
    if has_place and has_animals and has_case and has_action and has_scale:
        return "2026-07-stuart-martin-animal-hoarding"

    # July 2026 St. Lucie County Fire District firefighter discipline / hazing saga.
    # Different outlets have framed the same continuing case as terminations, union
    # objections, a contradictory police report, and a workplace-culture assessment.
    # Those are developments within one event and must update one canonical article.
    has_st_lucie = (("st" in words and "lucie" in words) or "fort" in words and "pierce" in words)
    has_fire_org = bool(words & {"firefighter", "firefighters", "fire", "district"})
    has_discipline = bool(words & {"fired", "terminated", "termination", "terminations",
                                   "suspended", "suspension", "discipline", "disciplinary"})
    has_case_signal = bool(words & {"hazing", "haze", "union", "police", "report",
                                    "contradicts", "contradict", "assessment", "culture",
                                    "zapper", "investigation", "findings"})
    if has_st_lucie and has_fire_org and has_discipline and has_case_signal:
        return "2026-07-st-lucie-firefighter-hazing-discipline"

    return ""


def _same_event_text(a, b):
    """Exact known-event match first, then the normal headline-token heuristic."""
    ka, kb = _known_event_key(a), _known_event_key(b)
    if ka and kb:
        return ka == kb
    return _same_story(_sig_tokens(a), _sig_tokens(b))




def _custom_story_fingerprint(headline, teaser=""):
    """Durable fingerprint stored with every custom article.

    This is not the only duplicate test (headlines can be rewritten), but it gives
    custom stories a permanent identity after custom_articles.json is cleared.
    """
    normalized = " ".join(sorted(_sig_tokens(f"{headline} {teaser}")))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24] if normalized else ""


def _material_update_stages(text):
    """Return major editorial milestones explicitly present in a story.

    These are deliberately conservative. A new article may bypass custom-story
    suppression only when it reports a genuinely new status-changing development,
    not merely added quotes, a rewritten headline, a corrected count, or routine
    follow-up details.
    """
    t = re.sub(r"[^a-z0-9]+", " ", (text or "").lower())
    stages = set()

    patterns = {
        "victim_identified": (
            r"\b(victim|decedent|person killed|man killed|woman killed) (?:has been |was )?identified\b",
            r"\bidentified (?:the )?(?:victim|decedent|person killed)\b",
        ),
        "suspect_identified": (
            r"\b(?:police|deputies|authorities) (?:have )?identified (?:a |the )?suspect\b",
            r"\bsuspect (?:has been |was )?identified\b",
        ),
        "arrest": (
            r"\b(?:arrested|taken into custody|booked into|apprehended)\b",
            r"\barrest (?:made|announced)\b",
        ),
        "criminal_charge": (
            r"\b(?:charged with|faces? charges?|criminal charges? filed|indicted|indictment)\b",
        ),
        "death": (
            r"\b(?:died|has died|pronounced dead|death confirmed|dead after|fatality confirmed)\b",
        ),
        "missing_found": (
            r"\b(?:found safe|located safe|missing person found|has been located)\b",
        ),
        "court_ruling": (
            r"\b(?:convicted|found guilty|acquitted|pleaded guilty|pleads guilty|sentenced|sentence imposed)\b",
        ),
        "official_resolution": (
            r"\b(?:reopened|closure lifted|evacuation order lifted|boil water notice lifted|all clear issued)\b",
        ),
        "hospital_release": (
            r"\b(?:released|discharged) from (?:the )?hospital\b",
            r"\b(?:recovering|recovers) at home\b",
        ),
        "official_cause": (
            r"\b(?:cause|manner) (?:of death|of the fire|of the crash) (?:was|has been) (?:determined|released|confirmed)\b",
            r"\b(?:investigators|officials|fhp|police) (?:determined|confirmed|said) (?:the )?cause\b",
        ),
        "major_escalation": (
            r"\b(?:state of emergency|mandatory evacuation|evacuation ordered|declared a disaster)\b",
        ),
    }
    for stage, regs in patterns.items():
        if any(re.search(rx, t) for rx in regs):
            stages.add(stage)
    return stages


def _material_case_counts(text):
    """Extract explicitly reported outbreak/case totals for significance checks.

    Counts are considered only when they appear near case/outbreak/infection language,
    avoiding unrelated numbers such as road addresses, ages, dates, or dollar amounts.
    """
    t = re.sub(r"\s+", " ", (text or "").lower())
    counts = set()
    patterns = (
        r"\b(\d{1,6})\s+(?:confirmed\s+)?(?:cases?|infections?|illnesses?)\b",
        r"\b(?:cases?|infections?|illnesses?)\s+(?:rose|rise|increased|climbed|grew|total(?:ed|ing)?|reached|now stand(?:s)? at|to)\s+(?:to\s+)?(\d{1,6})\b",
        r"\b(?:outbreak|statewide total|case count)\D{0,35}(\d{1,6})\b",
    )
    for rx in patterns:
        for m in re.finditer(rx, t):
            try:
                counts.add(int(m.group(1)))
            except Exception:
                pass
    return counts


def _significant_count_change(new_text, old_text):
    """Return True for a clearly changed reported case/outbreak total."""
    new_counts = _material_case_counts(new_text)
    old_counts = _material_case_counts(old_text)
    if not new_counts or not old_counts:
        return False
    # A newly reported maximum total is a material public-health development.
    return max(new_counts) != max(old_counts)


def _is_significant_story_update(item, prior):
    """True only when a matching event advances to a new major milestone.

    Example: an initial homicide report followed the next day by an arrest. Routine
    rewrites, extra quotes, and repeated reports remain blocked. A clearly changed
    outbreak/case total is treated as a material public-health update.
    """
    if not item or not prior:
        return False
    new_text = " ".join([
        item.get("headline", ""), item.get("teaser", ""), item.get("body", "")[:1200]
    ])
    old_text = " ".join([
        prior.get("headline", ""), prior.get("teaser", ""), prior.get("body", "")[:1200]
    ])
    new_stages = _material_update_stages(new_text)
    old_stages = _material_update_stages(old_text)
    added = new_stages - old_stages
    count_changed = _significant_count_change(new_text, old_text)
    if not added and not count_changed:
        return False

    # An arrest/charge is not a new milestone if the prior story already clearly
    # described custody or charges using different wording.
    custody_family = {"arrest", "criminal_charge"}
    if added and added <= custody_family and old_stages & custody_family and not count_changed:
        return False

    return True


def _same_published_milestone(item, prior):
    """Return True when an incoming feed item merely republishes an existing milestone.

    This is intentionally stricter than broad story clustering. It requires the normal
    deterministic archive matcher to have selected the prior article, the normalized
    editorial stage to be unchanged, and no material milestone to have been added.
    Such an item must not refresh lastmod, rewrite the canonical page, or re-enter the
    live hero/card pool merely because a source changed its headline or RSS timestamp.
    """
    if not item or not prior:
        return False
    new_stage = _story_stage(_story_text(_event_audit_item(item, "live")))
    old_stage = _story_stage(_story_text(_event_audit_item(prior, "archive")))
    if new_stage == "general" or new_stage != old_stage:
        return False
    if _is_significant_story_update(item, prior):
        return False
    return bool(find_matching_entry(
        item.get("headline", ""), [prior],
        item.get("link") or item.get("source_url") or "",
        is_weather_alert=bool(item.get("is_weather_alert")),
    ))


def _matches_archived_custom(item, entry):
    """Conservatively determine whether a feed item duplicates an archived custom story.

    Custom articles are authoritative forever. Matching uses, in order: a narrow
    known-event key, an exact durable fingerprint, the normal archive matcher (which
    includes locality conflict checks), and a stronger combined headline+teaser test.
    """
    if not item or not entry or not (entry.get("is_custom") or entry.get("authoritative_custom")):
        return False

    item_head = item.get("headline", "")
    item_text = " ".join([item_head, item.get("teaser", ""), item.get("body", "")[:500]])
    entry_head = entry.get("headline", "")
    entry_text = " ".join([entry_head, entry.get("teaser", ""), entry.get("body", "")[:1200]])

    # Custom coverage remains the canonical page. Any status-changing development
    # is merged into that page rather than published at a parallel permalink.

    item_key = _known_event_key(item_text)
    entry_key = entry.get("custom_event_key") or _known_event_key(entry_text)
    if item_key and entry_key and item_key == entry_key:
        return True

    item_fp = _custom_story_fingerprint(item_head, item.get("teaser", ""))
    entry_fp = entry.get("custom_fingerprint")
    if item_fp and entry_fp and item_fp == entry_fp:
        return True

    if find_matching_entry(item_head, [entry], item.get("link", "")):
        return True

    # Reworded syndication can move important details from headline to teaser. Use a
    # stricter combined-text match here to catch that without collapsing broad topics.
    a = _sig_tokens(item_text)
    b = _sig_tokens(entry_text)
    shared = _shared_tokens(a, b)
    distinctive = [t for t in shared if t not in GENERIC_TOKENS]
    return len(shared) >= 6 and len(distinctive) >= 3



def _sanitize_authoritative_custom_archive(archive, articles_dir=None):
    """Remove archived feed copies of authoritative custom stories before recovery.

    This runs before category fallback/hero selection, not only during final archive
    writing. It also backfills the canonical July 2026 Stuart hoarding custom story
    when it predates durable custom metadata.
    """
    archive = list(archive or [])

    # Backfill the canonical custom story for the July 2026 Stuart hoarding case.
    event_entries = []
    for e in archive:
        text = " ".join([e.get("headline", ""), e.get("teaser", ""), e.get("body", "")[:1200]])
        if _known_event_key(text) == "2026-07-stuart-martin-animal-hoarding":
            event_entries.append(e)

    if event_entries:
        # Exact production migration: this is Andrew's custom July 20 article and
        # must win over every generated/syndicated version of the same incident.
        canonical = next((e for e in event_entries if e.get("slug") ==
                          "2026-07-20-more-than-70-animals-found-in-stuart-home-during-large-scale-hoarding-response"), None)
        if canonical is None:
            canonical = next((e for e in event_entries if e.get("is_custom") or e.get("authoritative_custom")), None)
        if canonical is None:
            # Last-resort preservation: keep the oldest substantial entry rather than
            # allowing multiple copies to survive.
            canonical = sorted(event_entries, key=lambda e: (e.get("date") or e.get("lastmod") or "9999",
                                                               -len(e.get("body", "") or "")))[0]

        canonical["is_custom"] = True
        canonical["authoritative_custom"] = True
        canonical["custom_event_key"] = "2026-07-stuart-martin-80-cats-hoarding"
        canonical["custom_fingerprint"] = _custom_story_fingerprint(
            canonical.get("headline", ""), canonical.get("teaser", "")
        )

        remove_slugs = {e.get("slug") for e in event_entries if e is not canonical and e.get("slug")}
        if remove_slugs:
            archive = [e for e in archive if e.get("slug") not in remove_slugs]
            if articles_dir is not None:
                for slug in remove_slugs:
                    try:
                        p = Path(articles_dir) / f"{slug}.html"
                        if p.exists():
                            p.unlink()
                    except Exception:
                        pass
            print(f"  Custom-authority archive cleanup removed {len(remove_slugs)} duplicate event article(s)")

    return archive



def _story_text(item):
    if not item:
        return ""
    return " ".join([
        item.get("headline", ""), item.get("teaser", ""),
        (item.get("body", "") or "")[:1400],
    ]).strip()


def _same_event_items(a, b):
    """One shared event matcher for custom, feed, archive, hero and card stories."""
    if not a or not b:
        return False
    ta, tb = _story_text(a), _story_text(b)
    ka, kb = _known_event_key(ta), _known_event_key(tb)
    if ka and kb:
        return ka == kb
    # Reuse the archive matcher because it includes URL and locality safeguards.
    probe = dict(b)
    probe.setdefault("slug", "__candidate__")
    if find_matching_entry(a.get("headline", ""), [probe], a.get("link", "")):
        return True
    aa, bb = _sig_tokens(ta), _sig_tokens(tb)
    shared = _shared_tokens(aa, bb)
    distinctive = [t for t in shared if t not in GENERIC_TOKENS]
    return len(shared) >= 6 and len(distinctive) >= 3


def _story_priority(item):
    """Winner order inside one event group; custom is a priority, not a separate system."""
    if item.get("is_custom") or item.get("authoritative_custom"):
        return (500, int(item.get("article_word_count", 0) or len((item.get("body") or "").split())))
    if item.get("source_quality") == "full":
        return (300, int(item.get("article_word_count", 0) or len((item.get("body") or "").split())))
    if item.get("_archive_only"):
        return (200, int(item.get("article_word_count", 0) or len((item.get("body") or "").split())))
    return (100, int(item.get("article_word_count", 0) or len((item.get("body") or "").split())))


def _unified_archive_event_dedupe(archive, current_customs=None, articles_dir=None):
    """Deduplicate archive stories with the same engine used for live stories.

    Custom articles win their event group permanently. A later story survives only
    when it contains a verified major milestone not present in the custom article.
    """
    archive = list(archive or [])
    current_customs = list(current_customs or [])
    authorities = [e for e in archive if e.get("is_custom") or e.get("authoritative_custom")] + current_customs
    removed = []
    kept = []
    for entry in archive:
        if entry.get("is_custom") or entry.get("authoritative_custom"):
            kept.append(entry)
            continue
        duplicate_of = None
        for custom in authorities:
            if _same_event_items(entry, custom):
                duplicate_of = custom
                break
        if duplicate_of:
            removed.append(entry)
        else:
            kept.append(entry)

    if removed and articles_dir is not None:
        for entry in removed:
            slug = entry.get("slug")
            if not slug:
                continue
            try:
                path = Path(articles_dir) / f"{slug}.html"
                if path.exists():
                    path.unlink()
            except Exception:
                pass
    if removed:
        print(f"  Unified event dedupe removed {len(removed)} archived duplicate article(s)")
    return kept


def _unified_live_event_dedupe(all_categories, archived_customs=None, current_customs=None):
    """Run one event-level dedupe pass over every hero and card before ranking."""
    authorities = list(archived_customs or []) + list(current_customs or [])
    seen = []
    removed = 0

    # Process custom stories first so they become the event winner everywhere.
    ordered = []
    for cat in all_categories:
        for role, item in [("hero", cat.get("hero"))] + [("card", c) for c in cat.get("cards", [])]:
            if item:
                ordered.append((cat, role, item))
    ordered.sort(key=lambda x: _story_priority(x[2]), reverse=True)

    winners = []
    loser_ids = set()
    for cat, role, item in ordered:
        matched = None
        for winner in winners:
            if not _same_event_items(item, winner):
                continue
            # Every development in the same underlying event belongs to one canonical
            # article. Milestones update that article; they never create a parallel URL.
            matched = winner
            break
        if matched is None:
            winners.append(item)
        elif item is not matched:
            loser_ids.add(id(item))

    # Also suppress any live/archive-recovered copy of an authoritative custom story.
    for cat, role, item in ordered:
        if item.get("is_custom") or item.get("authoritative_custom"):
            continue
        if any(_same_event_items(item, custom) for custom in authorities):
            loser_ids.add(id(item))

    for cat in all_categories:
        old_cards = list(cat.get("cards", []))
        cat["cards"] = [c for c in old_cards if id(c) not in loser_ids]
        removed += len(old_cards) - len(cat["cards"])
        if cat.get("hero") is not None and id(cat["hero"]) in loser_ids:
            cat["hero"] = cat["cards"].pop(0) if cat["cards"] else None
            removed += 1
    if removed:
        print(f"  Unified event dedupe removed {removed} duplicate hero/card placement(s)")
    return removed


# -- STORY ENGINE PHASE 2: NON-DESTRUCTIVE SHADOW MODE ----------------------
# This phase models persistent stories and editorial stages, but it never changes
# publication decisions, archive entries, article HTML, heroes, cards, redirects,
# sitemaps, or Claude generation. It records what the engine WOULD do.
EVENT_PIPELINE_MODE = os.environ.get("TCT_EVENT_PIPELINE_MODE", "guarded").strip().lower()


def _event_audit_item(item, origin="archive"):
    """Normalize an existing or custom article for the shadow story registry."""
    item = dict(item or {})
    headline = (item.get("headline") or item.get("title") or "").strip()
    body = item.get("body") or item.get("article") or item.get("content") or ""
    teaser = item.get("teaser") or item.get("summary") or ""
    slug = item.get("slug") or ""
    return {
        "headline": headline,
        "teaser": teaser,
        "body": body,
        "slug": slug,
        "link": item.get("link") or (f"{SITE_URL}/articles/{slug}.html" if slug else ""),
        "date": item.get("date") or item.get("lastmod") or item.get("published") or "",
        "lastmod": item.get("lastmod") or item.get("date") or "",
        "category_key": item.get("category_key") or item.get("category") or "",
        "category_label": item.get("category_label") or "",
        "source_url": item.get("source_url") or item.get("original_url") or item.get("feed_url") or "",
        "is_custom": bool(item.get("is_custom") or item.get("authoritative_custom") or origin == "custom"),
        "authoritative_custom": bool(item.get("authoritative_custom") or origin == "custom"),
        "origin": origin,
        "article_word_count": int(item.get("article_word_count", 0) or len(str(body).split())),
    }


def _audit_date_value(item):
    raw = str(item.get("date") or item.get("lastmod") or item.get("published") or "")[:10]
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except Exception:
        return None


def _audit_headline_tokens(item):
    return _sig_tokens(item.get("headline", ""))


def _audit_locations(text):
    """Extract concrete locality anchors; broad Florida terms are excluded."""
    t = re.sub(r"[^a-z0-9]+", " ", (text or "").lower())
    places = {
        "port st lucie": "port-st-lucie", "st lucie": "st-lucie",
        "fort pierce": "fort-pierce", "stuart": "stuart",
        "hobe sound": "hobe-sound", "jensen beach": "jensen-beach",
        "palm city": "palm-city", "vero beach": "vero-beach",
        "sebastian": "sebastian", "fellsmere": "fellsmere",
        "indian river": "indian-river", "martin county": "martin-county",
        "st lucie county": "st-lucie-county", "indian river county": "indian-river-county",
        "jupiter island": "jupiter-island", "lake worth": "lake-worth",
        "north palm beach": "north-palm-beach", "boca raton": "boca-raton",
        "palm beach county": "palm-beach-county", "miami dade": "miami-dade",
        "ocala": "ocala", "marion county": "marion-county",
        "kennedy space center": "kennedy-space-center", "clover park": "clover-park",
        "i 95": "i-95", "interstate 95": "i-95",
    }
    return {value for phrase, value in places.items() if re.search(r"\b" + re.escape(phrase) + r"\b", t)}


def _audit_action_families(text):
    t = re.sub(r"[^a-z0-9]+", " ", (text or "").lower())
    families = {
        "crime-case": r"\b(arrest|arrested|charged|indicted|trial|verdict|sentenced|homicide|murder|shooting|kidnapping|theft|hazing)\b",
        "crash": r"\b(crash|collision|wreck|vehicle fire|airlifted|hospitalized)\b",
        "fire": r"\b(fire|burned|burning|arson|contained|extinguished)\b",
        "government-law": r"\b(vote|ballot|amendment|legislature|bill|signed|veto|lawsuit|court ruling|budget|ordinance)\b",
        "development": r"\b(development|redevelopment|demolition|construction|annexation|permit|groundbreaking|opening)\b",
        "event-celebration": r"\b(festival|celebration|fireworks|parade|anniversary|event|schedule)\b",
        "sports": r"\b(win|loss|defeat|victory|game|series|homestand|sweep|score|trade|signing)\b",
        "closure-traffic": r"\b(closure|closed|traffic|roadwork|parking|enforcement|citation)\b",
        "animal-case": r"\b(rescue|rescued|animal|animals|cat|cats|dog|dogs|hoarding)\b",
        "health-outbreak": r"\b(outbreak|cases|bacteria|e coli|cyclospora|health warning)\b",
        "business-route": r"\b(route|flight|airline|business|store|restaurant|closure|expansion)\b",
    }
    return {name for name, rx in families.items() if re.search(rx, t)}


def _story_stage(text):
    """Return an editorial lifecycle stage, ordered from specific to broad."""
    t = re.sub(r"[^a-z0-9]+", " ", (text or "").lower())

    if re.search(r"\b(host|hosts|hosting|homestand|preview|upcoming|will face|set to play|schedule)\b", t) and re.search(r"\b(mets|baseball|football|basketball|soccer|game|series|threshers|tarpons|cardinals)\b", t):
        return "sports-preview"
    if re.search(r"\b(win|wins|won|loss|lose|loses|lost|defeat|defeats|victory|sweep|sweeps|score|rally|comeback)\b", t) and re.search(r"\b(mets|baseball|football|basketball|soccer|game|series|threshers|tarpons|cardinals)\b", t):
        return "sports-result"

    if re.search(r"\b(arbitration|grievance|union disputes|union challenges|demands arbitration)\b", t):
        return "arbitration-or-grievance"
    if re.search(r"\b(appeal|appeals|appealed)\b", t):
        return "appeal"
    if re.search(r"\b(lawsuit|sues|sued|legal challenge|court challenge|injunction)\b", t):
        return "lawsuit-or-legal-challenge"
    if re.search(r"\b(sentenced|sentencing|prison term|probation)\b", t):
        return "sentencing"
    if re.search(r"\b(convicted|conviction|found guilty|acquitted|not guilty|verdict)\b", t):
        return "verdict"
    if re.search(r"\b(trial begins|trial starts|goes on trial|jury selection)\b", t):
        return "trial"
    if re.search(r"\b(bond hearing|arraignment|court appearance|first appearance)\b", t):
        return "court-appearance"
    if re.search(r"\b(arrest|arrested|charged|indicted|custody|booked)\b", t):
        return "arrest-or-charges"
    if re.search(r"\b(firings|fired|suspended|terminated|terminations|discipline|disciplined)\b", t):
        return "discipline"
    if re.search(r"\b(investigation|investigating|probe|under review)\b", t):
        return "investigation"

    if re.search(r"\b(body found|body recovered|remains found|remains recovered)\b", t):
        return "body-recovery"
    if re.search(r"\b(rescue|rescued|evacuated|saved)\b", t):
        return "rescue"
    if re.search(r"\b(fully contained|100 contained|extinguished|reopened|all clear|cleanup complete)\b", t):
        return "incident-resolved"
    if re.search(r"\b(contained|grows|spreads|burning|active fire|ongoing|closure|closed|shuts down)\b", t):
        return "incident-active"
    if re.search(r"\b(raises funds|fundraiser|gofundme|vigil|memorial|community support)\b", t):
        return "community-response"

    if re.search(r"\b(veto|vetoes|vetoed|rejects|rejected)\b", t):
        return "veto-or-rejection"
    if re.search(r"\b(approves|approved|passes|passed|adopts|adopted|signs|signed|enacts|enacted|implements|implemented|takes effect)\b", t):
        return "approved-or-enacted"
    if re.search(r"\b(expected to|set to|scheduled to|plans to|will sign|could sign|proposal|proposed|considering|seeks|would)\b", t):
        return "proposal-or-expected"
    if re.search(r"\b(public meeting|workshop|hearing|open house)\b", t):
        return "public-meeting"

    if re.search(r"\b(listed|listing|for sale|on the market)\b", t):
        return "property-listing"
    if re.search(r"\b(demolition underway|construction begins|breaks ground|groundbreaking)\b", t):
        return "construction-or-demolition"
    if re.search(r"\b(grand opening|opens|opening day|now open)\b", t):
        return "opening"
    if re.search(r"\b(closes|closing|shuts down permanently|ending route|ending flights)\b", t):
        return "closure"
    if re.search(r"\b(announces|announced|unveils|launches|to gain)\b", t):
        return "announcement"
    return "general"


def _audit_numbers(text):
    return {n for n in re.findall(r"\b\d{2,}\b", text or "") if not re.fullmatch(r"20\d{2}", n)}


def _same_story_topic(a, b):
    """Conservative topic matcher that deliberately ignores lifecycle stage.

    Same topic + same stage becomes a duplicate candidate. Same topic + a new
    stage becomes a publishable major update in the shadow decision log.
    """
    if not a or not b:
        return False
    ta, tb = _story_text(a), _story_text(b)
    ka, kb = _known_event_key(ta), _known_event_key(tb)
    if ka or kb:
        return bool(ka and kb and ka == kb)

    da, db = _audit_date_value(a), _audit_date_value(b)
    day_gap = abs((da - db).days) if da and db else None
    if day_gap is not None and day_gap > 120:
        return False

    ha, hb = _audit_headline_tokens(a), _audit_headline_tokens(b)
    shared_h = _shared_tokens(ha, hb)
    distinctive_h = [t for t in shared_h if t not in GENERIC_TOKENS]
    denom = max(1, min(len(ha), len(hb)))
    title_overlap = len(shared_h) / denom

    la, lb = _audit_locations(ta), _audit_locations(tb)
    if la and lb and not (la & lb):
        return False

    aa, ab = _audit_action_families(ta), _audit_action_families(tb)
    if aa and ab and not (aa & ab):
        return False

    na, nb = _audit_numbers(a.get("headline", "")), _audit_numbers(b.get("headline", ""))
    if na and nb and not (na & nb) and title_overlap < 0.72:
        return False

    if len(distinctive_h) >= 4 and title_overlap >= 0.58:
        return True
    if la & lb and aa & ab and len(distinctive_h) >= 3 and title_overlap >= 0.42:
        return True

    full_a, full_b = _sig_tokens(ta), _sig_tokens(tb)
    shared_full = _shared_tokens(full_a, full_b)
    distinctive_full = [t for t in shared_full if t not in GENERIC_TOKENS]
    if (day_gap is None or day_gap <= 30) and len(distinctive_h) >= 3 and len(distinctive_full) >= 7:
        return bool((la & lb) or (aa & ab))
    return False


def _story_match_confidence(a, b):
    """Explainable heuristic confidence used for shadow review only."""
    ta, tb = _story_text(a), _story_text(b)
    ha, hb = _audit_headline_tokens(a), _audit_headline_tokens(b)
    shared = _shared_tokens(ha, hb)
    denom = max(1, min(len(ha), len(hb)))
    overlap = len(shared) / denom
    score = 45 + min(35, int(overlap * 45))
    if _audit_locations(ta) & _audit_locations(tb):
        score += 10
    if _audit_action_families(ta) & _audit_action_families(tb):
        score += 8
    if _known_event_key(ta) and _known_event_key(ta) == _known_event_key(tb):
        score = 99
    return max(0, min(99, score))




def _story_entities(item):
    """Extract conservative entities for internal clustering and timelines.

    V6.1 deliberately avoids treating title-cased headline fragments as people.
    Person names are captured only in strong name contexts; known places and
    agencies remain deterministic and explainable.
    """
    text = _story_text(item)
    headline = item.get("headline", "") or ""
    lower = text.lower()
    known = {
        "locations": {
            "Martin County": r"\bmartin county\b", "St. Lucie County": r"\bst[.]? lucie county\b",
            "Indian River County": r"\bindian river county\b", "Stuart": r"\bstuart\b",
            "Port St. Lucie": r"\bport st[.]? lucie\b", "Fort Pierce": r"\bfort pierce\b",
            "Vero Beach": r"\bvero beach\b", "Sebastian": r"\bsebastian\b",
            "Hobe Sound": r"\bhobe sound\b", "Jensen Beach": r"\bjensen beach\b",
            "Palm City": r"\bpalm city\b", "Fellsmere": r"\bfellsmere\b",
        },
        "organizations": {
            "Martin County Sheriff's Office": r"\bmartin county sheriff(?:'s office)?\b",
            "St. Lucie County Sheriff's Office": r"\bst[.]? lucie county sheriff(?:'s office)?\b",
            "Indian River County Sheriff's Office": r"\bindian river county sheriff(?:'s office)?\b",
            "Port St. Lucie Police": r"\bport st[.]? lucie police\b",
            "Fort Pierce Police": r"\bfort pierce police\b",
            "Florida Legislature": r"\bflorida legislature\b",
            "FDOT": r"\b(?:fdot|florida department of transportation)\b",
            "St. Lucie Mets": r"\bst[.]? lucie mets\b",
        },
    }
    result = {"people": [], "organizations": [], "locations": [], "numbers": []}
    for group, mapping in known.items():
        result[group] = [name for name, rx in mapping.items() if re.search(rx, lower, re.I)]

    # Only accept names in explicit contexts, avoiding phrases such as
    # “Downtown Fort Pierce” or “Animals Found Stuart Home.”
    person_patterns = [
        r"\b(?:Sheriff|Chief|Mayor|Commissioner|Judge|Dr[.]?|Officer|Deputy)\s+([A-Z][a-z'’-]+\s+[A-Z][a-z'’-]+)\b",
        r"\b(?:identified as|named|according to)\s+([A-Z][a-z'’-]+\s+[A-Z][a-z'’-]+)\b",
    ]
    for rx in person_patterns:
        for name in re.findall(rx, text):
            if name not in result["locations"] and name not in result["organizations"]:
                result["people"].append(name)
    for key in ("people", "organizations", "locations"):
        result[key] = list(dict.fromkeys(result[key]))[:10]
    result["numbers"] = sorted(_audit_numbers(headline))[:10]
    return result


def _merge_story_entities(members):
    merged = {"people": [], "organizations": [], "locations": [], "numbers": []}
    for member in members:
        entities = _story_entities(member)
        for key in merged:
            merged[key].extend(entities.get(key, []))
    for key in merged:
        merged[key] = list(dict.fromkeys(merged[key]))[:25]
    return merged


def _story_timeline(members):
    timeline = []
    for article in sorted(members, key=lambda x: (_audit_date_value(x) or datetime.min.date(), x.get("headline", ""))):
        timeline.append({
            "date": article.get("date", ""),
            "stage": _story_stage(_story_text(article)),
            "headline": article.get("headline", ""),
            "slug": article.get("slug", ""),
            "is_custom": bool(article.get("is_custom") or article.get("authoritative_custom")),
        })
    return timeline

def _story_base_id(item):
    text = _story_text(item)
    known = _known_event_key(text)
    if known:
        base = re.sub(r"[^a-z0-9]+", "-", str(known).lower()).strip("-")
    else:
        toks = [t for t in sorted(_sig_tokens(text)) if t not in GENERIC_TOKENS][:7]
        base = "-".join(toks[:5]) or "story"
    digest = hashlib.sha1((base + "|" + (item.get("headline") or "").lower()).encode("utf-8")).hexdigest()[:8]
    return f"story-{re.sub(r'[^a-z0-9]+', '-', base).strip('-')[:55]}-{digest}"[:80]


def _load_previous_story_membership(out_dir):
    path = Path(out_dir) / "data" / "stories.json"
    if not path.exists():
        return {}, {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}, {}
    by_slug, titles = {}, {}
    for story in payload.get("stories", []):
        sid = story.get("story_id")
        if not sid:
            continue
        titles[sid] = story.get("title", "")
        for article in story.get("articles", []):
            if article.get("slug"):
                by_slug[article["slug"]] = sid
    return by_slug, titles



SAFE_AUTO_SUPPRESSION_STAGES = {
    "announcement", "arrest-or-charges", "approved-or-enacted",
    "construction-or-demolition", "sports-preview", "sports-result",
    "sentencing", "opening", "closure", "property-listing",
    "discipline", "investigation", "body-recovery", "rescue",
    "incident-active", "incident-resolved", "community-response",
    "lawsuit-or-legal-challenge", "arbitration-or-grievance",
    "court-appearance", "trial", "verdict", "appeal",
    "veto-or-rejection", "proposal-or-expected", "public-meeting",
}
STORY_CLUSTERING_CONFIDENCE = 85
STORY_OBSERVATION_CONFIDENCE = 90
AUTO_SUPPRESSION_CONFIDENCE = 95
HISTORY_MAX_PROCESSED = 20000
SUPPRESSION_REPORT_LIMIT = 250


def _read_json_file(path, default):
    try:
        if Path(path).exists():
            return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  Story engine warning: could not read {path}: {exc}")
    return default


def _article_log_key(item):
    """Return a stable key without letting diagnostics hide real actions.

    A shadow recommendation and an enforcement action may concern the same slug,
    but they are different audit events and must both remain observable.
    """
    base = (item.get("slug") or item.get("link") or item.get("source_url") or
            hashlib.sha1(((item.get("headline") or "") + "|" + (item.get("date") or "")).encode("utf-8")).hexdigest())
    scope = "action" if item.get("action_taken") is True or item.get("decision") == "SUPPRESSED_DUPLICATE" else "diagnostic"
    return f"{scope}:{base}" if base else ""


def _persist_story_decision_logs(data_dir, decisions, run_id):
    """Keep a current snapshot plus append-only history for newly seen articles."""
    processed_path = data_dir / "story-processed-articles.json"
    history_path = data_dir / "story-decision-history.jsonl"
    report_path = data_dir / "story-suppression-report.json"
    processed_payload = _read_json_file(processed_path, {"schema_version": 5, "processed": {}})
    processed = processed_payload.get("processed", {}) if isinstance(processed_payload, dict) else {}
    new_records = []
    for decision in decisions:
        key = _article_log_key(decision)
        if not key or key in processed:
            continue
        record = dict(decision)
        record.update({"run_id": run_id, "engine_version": "story-centric-newsroom-v6.5.14"})
        new_records.append(record)
        processed[key] = {"run_id": run_id, "decision": decision.get("decision", ""), "slug": decision.get("slug", "")}
    if new_records:
        with history_path.open("a", encoding="utf-8") as fh:
            for record in new_records:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    # Bound the ledger while preserving the newest insertions.
    if len(processed) > HISTORY_MAX_PROCESSED:
        processed = dict(list(processed.items())[-HISTORY_MAX_PROCESSED:])
    processed_path.write_text(json.dumps({"schema_version": 5, "updated_at": run_id, "processed": processed}, indent=2, ensure_ascii=False), encoding="utf-8")

    prior_report = _read_json_file(report_path, {"schema_version": 5, "suppressions": []})
    prior_suppressions = list(prior_report.get("suppressions", [])) if isinstance(prior_report, dict) else []
    # v5.1 migration: remove legacy shadow recommendations from this action-only report.
    suppressions = [r for r in prior_suppressions
                    if r.get("decision") == "SUPPRESSED_DUPLICATE"
                    and r.get("action_taken") is True
                    and int(r.get("match_confidence", 0) or 0) >= AUTO_SUPPRESSION_CONFIDENCE]
    actual_new_suppressions = [r for r in new_records
                               if r.get("decision") == "SUPPRESSED_DUPLICATE"
                               and r.get("action_taken") is True
                               and int(r.get("match_confidence", 0) or 0) >= AUTO_SUPPRESSION_CONFIDENCE]
    suppressions.extend(actual_new_suppressions)
    suppressions = suppressions[-SUPPRESSION_REPORT_LIMIT:]
    report_path.write_text(json.dumps({
        "schema_version": 5,
        "updated_at": run_id,
        "report_type": "actual_guarded_suppressions_only",
        "minimum_confidence": AUTO_SUPPRESSION_CONFIDENCE,
        "suppressions_this_run": len(actual_new_suppressions),
        "retained_suppressions": len(suppressions),
        "suppressions": suppressions,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(new_records)


def apply_guarded_story_suppression(all_categories, archive, current_customs=None):
    """Remove only extremely safe duplicate feed versions from live output.

    Custom articles are never suppressed. General-stage and sub-95% matches are
    never suppressed. Different stages remain publishable major updates.
    """
    if EVENT_PIPELINE_MODE != "guarded":
        return []
    archive_items = [_event_audit_item(e, "archive") for e in (archive or []) if e.get("headline")]
    accepted_live = []
    suppressions = []

    def evaluate(item):
        if not item or item.get("is_custom") or item.get("authoritative_custom"):
            return None
        normalized = _event_audit_item(item, "live")
        stage = _story_stage(_story_text(normalized))
        if stage == "general" or stage not in SAFE_AUTO_SUPPRESSION_STAGES:
            return None
        candidates = archive_items + accepted_live

        # First use the same deterministic matcher that the archive writer uses. If it
        # resolves to an existing article at the same editorial milestone, this is a
        # republication—not a fresh story—even when wording changes lower the generic
        # confidence score below 95.
        deterministic = next((prior for prior in candidates
                              if _same_published_milestone(item, prior)), None)
        if deterministic:
            best = deterministic
            confidence = 100
        else:
            matches = [prior for prior in candidates
                       if _story_stage(_story_text(prior)) == stage and _same_story_topic(normalized, prior)]
            if not matches:
                accepted_live.append(normalized)
                return None
            best = max(matches, key=lambda prior: _story_match_confidence(normalized, prior))
            confidence = _story_match_confidence(normalized, best)
            if confidence < AUTO_SUPPRESSION_CONFIDENCE:
                accepted_live.append(normalized)
                return None
        record = {
            "story_id": prior_membership_id(best, archive_items),
            "slug": normalized.get("slug", ""),
            "headline": normalized.get("headline", ""),
            "date": normalized.get("date", ""),
            "category_key": normalized.get("category_key", ""),
            "is_custom": False,
            "story_stage": stage,
            "decision": "SUPPRESSED_DUPLICATE",
            "action_taken": True,
            "reason": f"Same story and safe normalized stage '{stage}' at {confidence}% confidence.",
            "match_confidence": confidence,
            "matched_prior_slug": best.get("slug", ""),
            "matched_prior_headline": best.get("headline", ""),
        }
        suppressions.append(record)
        return record

    # Resolve a best-effort story ID without making it a correctness dependency.
    def _filter_category(cat):
        hero = cat.get("hero")
        if hero and evaluate(hero):
            cat["hero"] = None
        kept = []
        for card in cat.get("cards", []) or []:
            if not evaluate(card):
                kept.append(card)
        cat["cards"] = kept

    for cat in all_categories or []:
        _filter_category(cat)
    return suppressions


def prior_membership_id(item, archive_items):
    return _story_base_id(item) if item else ""

def build_story_shadow(archive, current_customs=None, live_categories=None, output_dir=None):
    """Build persistent story records with clustering separated from live action.

    V6 groups credible 85%+ matches into the same story, while guarded publication
    still suppresses only safe same-stage duplicates at 95%+. The 85-94 band is
    observational: it enriches the story graph but never removes or redirects content.
    """
    if EVENT_PIPELINE_MODE not in {"audit", "shadow", "guarded"}:
        print(f"  Story engine disabled (mode={EVENT_PIPELINE_MODE})")
        return None

    items = [_event_audit_item(e, "archive") for e in (archive or []) if e.get("headline")]
    for c in (current_customs or []):
        normalized = _event_audit_item(c, "custom")
        existing = None
        if normalized.get("slug"):
            existing = next((i for i in items if i.get("slug") == normalized.get("slug")), None)
        if not existing:
            existing = next((i for i in items if i.get("headline", "").lower() == normalized.get("headline", "").lower()), None)
        if existing:
            existing["is_custom"] = True
            existing["authoritative_custom"] = True
            existing["origin"] = "archive+custom"
            if normalized.get("body") and not existing.get("body"):
                existing["body"] = normalized["body"]
        else:
            items.append(normalized)

    ordered = sorted(items, key=lambda x: (_audit_date_value(x) or datetime.min.date(), x.get("headline", "")))
    topic_groups = []
    clustering_links = []
    for item in ordered:
        eligible = []
        for idx, members in enumerate(topic_groups):
            matches = [(m, _story_match_confidence(item, m)) for m in members if _same_story_topic(item, m)]
            if not matches:
                continue
            best_member, confidence = max(matches, key=lambda pair: pair[1])
            if confidence >= STORY_CLUSTERING_CONFIDENCE:
                eligible.append((idx, confidence, _story_priority(best_member), best_member))
        if eligible:
            idx, confidence, _, best_member = max(eligible, key=lambda x: (x[1], x[2]))
            topic_groups[idx].append(item)
            clustering_links.append({
                "slug": item.get("slug", ""), "headline": item.get("headline", ""),
                "matched_slug": best_member.get("slug", ""), "matched_headline": best_member.get("headline", ""),
                "confidence": confidence,
                "band": "85-89" if confidence < 90 else "90-94" if confidence < 95 else "95-100",
                "action": "GROUP_ONLY" if confidence < AUTO_SUPPRESSION_CONFIDENCE else "ELIGIBLE_FOR_SEPARATE_LIVE_EVALUATION",
            })
        else:
            topic_groups.append([item])

    out_root = Path(output_dir or OUTPUT_DIR)
    prior_membership, prior_titles = _load_previous_story_membership(out_root)
    used_ids, stories, decisions = set(), [], []

    for members in topic_groups:
        previous_ids = [prior_membership.get(m.get("slug")) for m in members if prior_membership.get(m.get("slug"))]
        story_id = max(set(previous_ids), key=previous_ids.count) if previous_ids else _story_base_id(max(members, key=_story_priority))
        base_id, suffix = story_id, 2
        while story_id in used_ids:
            story_id = f"{base_id}-{suffix}"; suffix += 1
        used_ids.add(story_id)

        stage_buckets = defaultdict(list)
        for m in members:
            stage_buckets[_story_stage(_story_text(m))].append(m)

        chronological = sorted(members, key=lambda x: (_audit_date_value(x) or datetime.min.date(), x.get("headline", "")))
        seen_stages = set()
        first_article = chronological[0]
        for article in chronological:
            stage = _story_stage(_story_text(article))
            prior_candidates = [x for x in chronological if x is not article and (_audit_date_value(x) or datetime.min.date()) <= (_audit_date_value(article) or datetime.min.date())]
            matches = [x for x in prior_candidates if _same_story_topic(article, x)]
            best_prior = max(matches, key=lambda x: _story_match_confidence(article, x)) if matches else None
            confidence = _story_match_confidence(article, best_prior) if best_prior else 100

            if article is first_article:
                decision, reason = "WOULD_PUBLISH_NEW_STORY", "No earlier matching story was found."
            elif stage in seen_stages and bool(article.get("is_custom") or article.get("authoritative_custom")):
                decision, reason = "WOULD_PUBLISH_CUSTOM_OVERRIDE", f"Authoritative custom coverage replaces feed coverage at the '{stage}' stage."
            elif stage in seen_stages and confidence >= AUTO_SUPPRESSION_CONFIDENCE:
                decision, reason = "WOULD_SUPPRESS_DUPLICATE", f"Same story and stage at {confidence}% confidence; eligible for guarded evaluation."
            elif stage in seen_stages:
                decision, reason = "GROUPED_NO_ACTION", f"Grouped into this story at {confidence}% confidence, but below the 95% live-action threshold."
            else:
                decision, reason = "WOULD_PUBLISH_MAJOR_UPDATE", f"The story advanced to a new '{stage}' stage."

            decisions.append({
                "story_id": story_id, "slug": article.get("slug", ""), "headline": article.get("headline", ""),
                "date": article.get("date", ""), "category_key": article.get("category_key", ""),
                "is_custom": bool(article.get("is_custom") or article.get("authoritative_custom")),
                "story_stage": stage, "decision": decision, "reason": reason,
                "match_confidence": confidence,
                "confidence_band": "new" if not best_prior else "85-89" if confidence < 90 else "90-94" if confidence < 95 else "95-100",
                "matched_prior_slug": best_prior.get("slug", "") if best_prior else "",
                "matched_prior_headline": best_prior.get("headline", "") if best_prior else "",
            })
            seen_stages.add(stage)

        stage_records = []
        for stage, stage_members in sorted(stage_buckets.items()):
            canonical = max(stage_members, key=_story_priority)
            stage_records.append({"stage": stage, "canonical_slug": canonical.get("slug", ""),
                "canonical_headline": canonical.get("headline", ""),
                "canonical_is_custom": bool(canonical.get("is_custom") or canonical.get("authoritative_custom")),
                "article_count": len(stage_members)})

        story_canonical = max(members, key=_story_priority)
        latest = max(chronological, key=lambda x: (_audit_date_value(x) or datetime.min.date(), _story_priority(x)))
        stories.append({
            "story_id": story_id, "title": prior_titles.get(story_id) or story_canonical.get("headline", ""),
            "status": "active" if ((_audit_date_value(latest) and (datetime.utcnow().date() - _audit_date_value(latest)).days <= 30)) else "archived",
            "latest_stage": _story_stage(_story_text(latest)), "latest_date": latest.get("date", ""),
            "canonical_slug": story_canonical.get("slug", ""), "canonical_headline": story_canonical.get("headline", ""),
            "canonical_is_custom": bool(story_canonical.get("is_custom") or story_canonical.get("authoritative_custom")),
            "article_count": len(members), "entities": _merge_story_entities(members),
            "timeline": _story_timeline(members), "stages": stage_records,
            "articles": [{"slug": m.get("slug", ""), "headline": m.get("headline", ""), "date": m.get("date", ""),
                "category_key": m.get("category_key", ""), "is_custom": bool(m.get("is_custom") or m.get("authoritative_custom")),
                "origin": m.get("origin", "archive"), "story_stage": _story_stage(_story_text(m)),
                "entities": _story_entities(m)} for m in chronological],
        })

    summary_counts = defaultdict(int)
    bands = defaultdict(int)
    for d in decisions:
        summary_counts[d["decision"]] += 1
        bands[d.get("confidence_band", "unknown")] += 1

    data_dir = out_root / "data"; data_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    registry = {"schema_version": 6.1, "mode": EVENT_PIPELINE_MODE, "generated_at": run_id,
        "non_destructive": True, "engine": "story-centric-newsroom-v6.5.14", "article_count": len(items),
        "story_count": len(stories), "clustering_threshold": STORY_CLUSTERING_CONFIDENCE,
        "live_action_threshold": AUTO_SUPPRESSION_CONFIDENCE, "stories": stories}
    shadow = {"schema_version": 6.1, "mode": EVENT_PIPELINE_MODE, "non_destructive": True,
        "engine": "story-centric-newsroom-v6.5.14", "generated_at": run_id,
        "summary": {"articles_analyzed": len(items), "stories_identified": len(stories),
            "would_publish_new_story": summary_counts["WOULD_PUBLISH_NEW_STORY"],
            "would_publish_major_update": summary_counts["WOULD_PUBLISH_MAJOR_UPDATE"],
            "would_publish_custom_override": summary_counts["WOULD_PUBLISH_CUSTOM_OVERRIDE"],
            "would_suppress_duplicate": summary_counts["WOULD_SUPPRESS_DUPLICATE"],
            "grouped_no_action": summary_counts["GROUPED_NO_ACTION"],
            "clustered_85_89": bands["85-89"], "clustered_90_94": bands["90-94"],
            "eligible_95_plus": bands["95-100"]},
        "clustering_links": clustering_links, "decisions": decisions,
        "notice": "V6.1 groups same-story matches at 85%+, but guarded live suppression remains limited to safe same-stage non-custom matches at 95%+. GROUPED_NO_ACTION requires no human review."}
    (data_dir / "stories.json").write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    (data_dir / "story-shadow-log.json").write_text(json.dumps(shadow, indent=2, ensure_ascii=False), encoding="utf-8")
    appended = _persist_story_decision_logs(data_dir, decisions, run_id)
    (data_dir / "event-audit.json").write_text(json.dumps(shadow, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Story-centric newsroom v6.5.13: {len(items)} articles -> {len(stories)} persistent stories; {appended} new history records")
    print(f"  Group-only: {summary_counts['GROUPED_NO_ACTION']}; eligible suppressions: {summary_counts['WOULD_SUPPRESS_DUPLICATE']}; major updates: {summary_counts['WOULD_PUBLISH_MAJOR_UPDATE']}")
    return shadow

def _same_story(tok_a, tok_b, threshold=4):
    """Two stories are the same only if they share enough tokens AND at least two of
    those are DISTINCTIVE (not generic people/boilerplate words). Counting alone lets
    'teen'+'youth'+'year'+'southeast' merge a June award story with a July World Cup
    trip about the same kid, absorbing genuinely new news into a stale article."""
    shared = _shared_tokens(tok_a, tok_b)
    if len(shared) < threshold:
        return False
    distinctive = [t for t in shared if t not in GENERIC_TOKENS]
    return len(distinctive) >= 2

def _is_duplicate_headline(headline, existing_token_sets):
    new_tok = _sig_tokens(headline)
    if len(new_tok) < 3:
        return False
    for ex_tok in existing_token_sets:
        if _same_story(new_tok, ex_tok):
            return True
    return False



def find_presentation_canonical(item, archive):
    """Resolve the exact canonical record used for reader-facing presentation.

    Presentation must never use fuzzy story matching because that can combine the
    headline/teaser from one live item with the permalink of a related-but-distinct
    article. Only an explicit archived slug, an exact normalized headline, or an exact
    source URL plus exact headline is accepted here. Fuzzy matching remains available
    to the guarded archival/update engine, but not to homepage/card/RSS rendering.
    """
    if not item:
        return None
    slug = item.get("_archived_slug") or item.get("canonical_slug")
    if slug:
        exact = next((e for e in archive if e.get("slug") == slug), None)
        if exact:
            return exact

    def _norm_text(value):
        return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()

    headline_key = _norm_text(item.get("headline", ""))
    if headline_key:
        exact_headline = [e for e in archive if _norm_text(e.get("headline", "")) == headline_key]
        if len(exact_headline) == 1:
            return exact_headline[0]
        if len(exact_headline) > 1:
            source = re.sub(r"[?#].*$", "", str(item.get("link", "")).strip().rstrip("/").lower())
            if source:
                for e in exact_headline:
                    e_source = re.sub(r"[?#].*$", "", str(e.get("source_url", "")).strip().rstrip("/").lower())
                    if e_source and e_source == source:
                        return e
            return max(exact_headline, key=_effective_story_datetime)
    return None


def _hydrate_presentation_item(item, canonical):
    """Bind display copy and URL identity atomically to one canonical record."""
    if not item or not canonical:
        return item
    item["_archived_slug"] = canonical.get("slug", item.get("_archived_slug", ""))
    for key in ("headline", "teaser", "body", "image_url", "category_key", "category_label",
                "first_published", "editorial_updated_at", "lastmod"):
        if canonical.get(key) not in (None, ""):
            item[key] = canonical.get(key)
    item["published_raw"] = _story_display_timestamp(canonical)
    return item

def find_matching_entry(headline, archive, source_url="", is_weather_alert=False):
    """Find an existing archive entry for this story using two-tier matching:
    1. source_url exact match — only when URL has a specific article path
    2. fuzzy headline match — catches rewrites and same story from different feeds
    Returns the matching entry dict or None.

    Weather alerts only match other weather alerts (by their NWS ID), never a
    regular article by fuzzy headline — so a "Tornado Warning" alert and a
    "Tornado damages homes" news story never collide regardless of shared words.
    """
    # Stable event fingerprints are checked before URL and fuzzy-token matching.
    # This catches heavily reworded syndicated versions of an event already in the
    # archive, including old custom articles no longer present in custom_articles.json.
    _event_key = _known_event_key(headline)
    if _event_key:
        for entry in archive:
            _entry_text = " ".join([entry.get("headline", ""), entry.get("teaser", "")])
            if _known_event_key(_entry_text) == _event_key:
                return entry

    if source_url:
        def norm_url(u):
            return re.sub(r"[?#].*$", "", u.strip().rstrip("/").lower())
        norm_src = norm_url(source_url)
        path_part = re.sub(r"^https?://[^/]+", "", norm_src)
        # Aggregator URLs (Google News especially) can collapse different articles to
        # the same normalized URL, so a URL match alone is not enough. Require the
        # headlines to also share at least 2 significant tokens, so two genuinely
        # different stories that happen to share a source URL are not merged.
        _AGG = ("news.google.com", "google.com/rss", "/rss/", "bing.com/news")
        _is_agg = any(a in norm_src for a in _AGG)
        if len(path_part) > 10:
            src_tok = _sig_tokens(headline)
            for entry in archive:
                if entry.get("source_url") and norm_url(entry["source_url"]) == norm_src:
                    # For aggregator URLs, or any URL, sanity-check the headlines are
                    # about the same thing before merging.
                    ent_tok = _sig_tokens(entry.get("headline", ""))
                    if src_tok and ent_tok:
                        overlap = _token_overlap(src_tok, ent_tok)
                        # A URL match must be backed by real headline similarity.
                        # Two shared words (e.g. "immigration" + "enforcement") is far
                        # too weak — many distinct stories share that. Require 3+, or
                        # for a very short headline, most of its tokens.
                        need = 3
                        if overlap < need and not (len(src_tok) <= 4 and overlap >= len(src_tok) - 1):
                            continue  # same URL but clearly different stories — skip
                    return entry

    tok = _sig_tokens(headline)
    if len(tok) < 3:
        return None

    # Location fingerprint: which specific Treasure Coast places a headline names.
    # Two stories that name DIFFERENT specific locations are different stories even
    # when their topical words overlap (e.g. "immigration arrests in Martin County"
    # vs a statewide immigration story, or vs "...in St. Lucie County"). Geographic
    # words are stopwords for token matching, so without this check a local story
    # can wrongly collapse into a differently-located one.
    def _loc_fingerprint(h):
        hl = h.lower()
        locs = set()
        for name, key in [
            ("martin", "martin"), ("st. lucie", "st_lucie"), ("st lucie", "st_lucie"),
            ("port st. lucie", "st_lucie"), ("port st lucie", "st_lucie"),
            ("indian river", "indian_river"), ("stuart", "martin"),
            ("jensen beach", "martin"), ("palm city", "martin"), ("hobe sound", "martin"),
            ("fort pierce", "st_lucie"), ("vero beach", "indian_river"),
            ("sebastian", "indian_river"), ("fellsmere", "indian_river"),
            ("indiantown", "martin"),
        ]:
            if name in hl:
                locs.add(key)
        return locs

    new_loc = _loc_fingerprint(headline)

    for entry in archive:
        # Never fuzzy-match across the weather-alert boundary: an alert matches
        # only alerts, a regular article matches only regular articles.
        if bool(entry.get("is_weather_alert")) != bool(is_weather_alert):
            continue
        if _same_story(tok, _sig_tokens(entry["headline"])):
            # Location-conflict guard. If the new story names a specific county, the
            # matched story must share that county to be considered the same story.
            # This keeps a county-specific story ("immigration arrests in Martin
            # County") from collapsing into a differently-located or statewide story
            # ("immigration arrests across Florida") that shares only topical words.
            entry_loc = _loc_fingerprint(entry["headline"])
            if new_loc:
                if not (new_loc & entry_loc):
                    continue  # entry names a different county, or none — not the same story
            elif entry_loc:
                # New story has no location but entry is county-specific — also a mismatch
                continue
            return entry
    return None



def find_canonical_event_entry(item, archive):
    """Find the single canonical archive article for an incoming development.

    Tier 1 uses deterministic URL, stable-event and headline matching. Tier 2 asks
    the model to compare the incoming item with a tightly filtered recent shortlist.
    A high-similarity candidate is never allowed to become a second URL merely
    because the model call fails; the existing canonical is retained.
    """
    item = item or {}
    headline = (item.get("headline") or "").strip()
    source_url = item.get("link") or item.get("source_url") or ""
    direct = find_matching_entry(
        headline, archive, source_url,
        is_weather_alert=bool(item.get("is_weather_alert")),
    )
    if direct:
        if _hard_canonical_identity_gate(item, direct):
            return direct
        print(f"    CANONICAL IDENTITY BLOCKED: '{headline[:55]}' cannot overwrite '{direct.get('slug','')}'")
        return None

    if item.get("is_weather_alert") or not headline:
        return None

    incoming_text = _story_text(item)
    incoming_tokens = _sig_tokens(incoming_text)
    incoming_locations = _audit_locations(incoming_text)
    candidates = []
    today = datetime.utcnow().date()

    for entry in archive:
        if not entry.get("slug") or entry.get("is_weather_alert"):
            continue
        # Keep the semantic comparison focused on recent continuing coverage.
        raw_date = str(entry.get("lastmod") or entry.get("date") or "")[:10]
        try:
            age = (today - datetime.strptime(raw_date, "%Y-%m-%d").date()).days
            if age > 45:
                continue
        except Exception:
            pass

        entry_text = _story_text(entry)
        entry_locations = _audit_locations(entry_text)
        if incoming_locations and entry_locations and not (incoming_locations & entry_locations):
            continue
        shared = _shared_tokens(incoming_tokens, _sig_tokens(entry_text))
        distinctive = [t for t in shared if t not in GENERIC_TOKENS]
        action_overlap = len(_audit_action_families(incoming_text) & _audit_action_families(entry_text))
        # Two distinctive shared entities/terms plus a related action family is enough
        # to warrant an ongoing-event comparison, but not an automatic merge.
        if len(distinctive) < 2 or action_overlap < 1:
            continue
        score = len(distinctive) * 10 + len(shared) * 2 + action_overlap * 8
        candidates.append((score, entry))

    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    shortlist = candidates[:8]

    choices = "\n\n".join(
        f"{i}. Headline: {e.get('headline','')}\nSummary: {(e.get('teaser') or '')[:350]}"
        for i, (_, e) in enumerate(shortlist, 1)
    )
    prompt = (
        "An incoming local-news item may be a new development in an already published "
        "ongoing event. Choose the ONE existing article covering the same underlying "
        "case/event, even if the new angle is a lawsuit, arrest, union response, official "
        "report, contradiction, ruling, identification, suspension or other development. "
        "Choose NONE only for a genuinely separate incident or proceeding.\n\n"
        f"INCOMING:\nHeadline: {headline}\nSummary: {(item.get('teaser') or item.get('body','')[:500])[:500]}\n\n"
        f"EXISTING CANDIDATES:\n{choices}\n\n"
        "Answer only the candidate number or NONE."
    )
    try:
        resp = client.messages.create(
            model=MODEL_SELECTION, max_tokens=12,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = resp.content[0].text.strip().upper()
        match = re.search(r"\b([1-8])\b", answer)
        if match:
            idx = int(match.group(1)) - 1
            if 0 <= idx < len(shortlist):
                candidate = shortlist[idx][1]
                if _hard_canonical_identity_gate(item, candidate):
                    return candidate
                print(f"    CANONICAL IDENTITY BLOCKED after semantic selection: '{headline[:55]}'")
                return None
        return None
    except Exception as exc:
        # Fail toward canonical continuity only when the lexical candidate is very
        # strong. Otherwise suppressing/merging unrelated stories would be worse.
        top_score, top_entry = shortlist[0]
        if top_score >= 54 and _hard_canonical_identity_gate(item, top_entry):
            print(f"    Semantic event check failed ({exc}); locking to identity-safe canonical candidate")
            return top_entry
        print(f"    Semantic event check failed ({exc}); no canonical candidate selected")
        return None


def _page_head(title, description, canonical_path="", structured_data=None, image_url="", article_meta=None):
    canonical = f"{SITE_URL}{canonical_path}" if canonical_path else SITE_URL
    og_image  = image_url if image_url else f"{SITE_URL}/og-image.png"
    schema = ""
    if structured_data:
        import json as _json
        schema = f'  <script type="application/ld+json">{_json.dumps(structured_data)}</script>'
    # Articles declare og:type=article with published/modified/author/section so news
    # crawlers correctly identify them as articles, not generic pages. Everything else
    # stays og:type=website.
    if article_meta:
        og_type = "article"
        _am = article_meta
        og_article_tags = (
            f'  <meta property="og:type" content="article">\n'
            f'  <meta property="article:published_time" content="{_am.get("published","")}">\n'
            f'  <meta property="article:modified_time" content="{_am.get("modified","") or _am.get("published","")}">\n'
            f'  <meta property="article:author" content="Andrew Dobrow">\n'
            f'  <meta property="article:section" content="{_am.get("section","")}">\n'
        )
    else:
        og_article_tags = '  <meta property="og:type" content="website">\n'
    return f"""  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{canonical}">
{og_article_tags}  <meta property="og:image" content="{og_image}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:image" content="{og_image}">
  <meta name="geo.region" content="US-FL">
  <meta name="geo.placename" content="Treasure Coast, Florida">
  <meta name="google-adsense-account" content="ca-pub-9679836198092378">
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/style.css">
  <style id="tct-mobile-overflow-fix">
    html, body {{ width: 100%; max-width: 100%; overflow-x: clip; }}
    *, *::before, *::after {{ box-sizing: border-box; }}
    img, video, iframe, svg, canvas, table {{ max-width: 100%; }}
    img, video, svg, canvas {{ height: auto; }}
    main, header, footer, section, article, aside, nav, div {{ min-width: 0; }}
    p, h1, h2, h3, h4, a, span, li {{ overflow-wrap: anywhere; word-break: normal; }}
    @media (max-width: 700px) {{
      body {{ margin: 0; width: 100%; }}
      .header-inner, .header-top, .header-actions, .category-nav,
      .page-wrap, .site-wrap, .content-wrap, .main-wrap, .article-wrap,
      .archive-wrap, .author-wrap, .policy-wrap, .about-wrap, .adv-wrap,
      .hero, .hero-grid, .section-grid, .news-grid, .cards-grid, .card-grid,
      .content-grid, .latest-grid, .story-grid, .footer-inner {{
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
      }}
      .hero-grid, .section-grid, .news-grid, .cards-grid, .card-grid,
      .content-grid, .latest-grid, .story-grid, .adv-row, .adv-stats {{
        grid-template-columns: minmax(0, 1fr) !important;
      }}
      .header-inner, .header-top, .header-actions, .category-nav,
      .hero, .card, .story-card, .article-card {{
        flex-wrap: wrap;
      }}
      .category-nav {{
        overflow-x: auto;
        overscroll-behavior-inline: contain;
        scrollbar-width: none;
      }}
      .category-nav::-webkit-scrollbar {{ display: none; }}
      pre, code {{ max-width: 100%; white-space: pre-wrap; overflow-wrap: anywhere; }}
      table {{ display: block; overflow-x: auto; }}
    }}
  </style>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,500;0,9..144,600;1,9..144,300&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700;9..40,800&display=swap" rel="stylesheet">
{schema}
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-GLJY7M6F3G"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-GLJY7M6F3G');
  </script>"""


def _page_header(active=""):
    def cat_link(label, href, key):
        cls = "cat-btn active" if key == active else "cat-btn"
        if key == active:
            return f'<span class="{cls}">{label}</span>'
        return f'<a href="{href}" class="{cls}" style="text-decoration:none">{label}</a>'

    # Build the category links from CATEGORIES so these labels always match the
    # homepage nav. Previously they were hardcoded abbreviations ("Crime",
    # "Martin Co.") which drifted from the real labels ("Crime & Safety",
    # "Martin County") shown on the homepage.
    cat_links = "\n        ".join(
        cat_link(cfg["label"], f"/?cat={key}", key)
        for key, cfg in CATEGORIES.items()
    )
    return f"""  <header>
    <div class="header-inner">
      <div class="header-top">
        <a href="/" class="wordmark" aria-label="Treasure Coast Today"><span class="wordmark-tct">TCT</span><span class="wordmark-divider"></span><span class="wordmark-full">TREASURE<br>COAST<br>TODAY</span></a>
      </div>
      <nav class="category-nav">
        {cat_link("Top News", "/", "news")}
        {cat_links}
        {cat_link("Weather", "/weather.html", "weather")}
        {cat_link("Archive", "/archive.html", "archive")}
      </nav>
      <div class="header-actions">
        <a href="/advertise.html" class="support-btn" style="text-decoration:none">Advertise</a>
      </div>
    </div>
  </header>"""


def _page_footer():
    return """  <footer>
    <div class="footer-inner footer-v2">
      <div class="footer-brand"><span class="footer-wordmark">TCT</span><p>Independent, hyperlocal journalism for the Treasure Coast.</p></div>
      <div class="footer-column"><strong>Quick Links</strong><div class="footer-links">
        <a href="/about.html">About</a>
        <a href="/author/andrew-dobrow.html">Author</a>
        <a href="/editorial-standards.html">Editorial Standards</a>
        <a href="/corrections-policy.html">Corrections</a>
        <a href="/ownership.html">Ownership</a>
        <a href="/weather.html">Weather</a>
        <a href="/archive.html">Archive</a>
        <a href="/advertise.html">Advertise</a>
        <a href="/privacy.html">Privacy</a>
        <a href="/contact.html">Contact</a>
      </div></div>
      <div class="footer-column"><strong>Counties</strong><a href="/?cat=martin">Martin County</a><a href="/?cat=st_lucie">St. Lucie County</a><a href="/?cat=indian_river">Indian River County</a></div>
      <div class="footer-column footer-connect"><strong>Stay Connected</strong><p>Join our local community for news, updates and discussion.</p><a class="footer-cta" href="/contact.html">Connect with TCT</a></div>
    </div>
    <div class="footer-bottom">© 2026 Treasure Coast Today. All rights reserved.</div>
  </footer>
  <script src="/main.js"></script>"""


def render_author_page():
    author_schema = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": "Andrew Dobrow",
        "jobTitle": "Founder and Publisher",
        "url": f"{SITE_URL}/author/andrew-dobrow.html",
        "email": "hello@treasurecoast.today",
        "worksFor": {
            "@type": "Organization",
            "name": SITE_NAME,
            "url": SITE_URL,
        },
        "knowsAbout": [
            "Local government", "Public safety", "Development", "Education",
            "Sports", "Community events", "Martin County Florida",
            "St. Lucie County Florida", "Indian River County Florida",
        ],
        "address": {
            "@type": "PostalAddress",
            "addressLocality": "Hobe Sound",
            "addressRegion": "FL",
            "addressCountry": "US",
        },
    }
    head   = _page_head(
        "Andrew Dobrow, Founder and Publisher | Treasure Coast Today",
        "Andrew Dobrow is the founder and publisher of Treasure Coast Today, an independent local news outlet serving Martin, St. Lucie and Indian River counties, Florida.",
        "/author/andrew-dobrow.html",
        structured_data=author_schema,
    )
    header = _page_header()
    footer = _page_footer()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
  <style>
    .author-wrap {{ max-width: 720px; margin: 56px auto 80px; padding: 0 24px; }}
    .author-eyebrow {{ font-size: 11px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: var(--accent); margin-bottom: 14px; display: block; }}
    .author-name {{ font-family: 'Fraunces', serif; font-size: clamp(30px, 5vw, 44px); font-weight: 600; line-height: 1.1; color: var(--text); margin: 0 0 6px; letter-spacing: -.02em; }}
    .author-role {{ font-size: 15px; color: var(--text-muted); margin: 0 0 28px; }}
    .author-body {{ font-size: 16px; color: var(--text-secondary); line-height: 1.75; }}
    .author-body p {{ margin: 0 0 20px; }}
    .author-body a {{ color: var(--accent); font-weight: 500; text-decoration: none; }}
    .author-body a:hover {{ text-decoration: underline; }}
    .author-divider {{ border: none; border-top: 1px solid var(--border); margin: 36px 0; }}
    .author-contact-card {{ background: var(--bg-secondary); border-radius: 12px; padding: 22px 24px; font-size: 15px; color: var(--text-secondary); }}
    .author-contact-card strong {{ color: var(--text); }}
  </style>
</head>
<body>
{header}
  <main>
    <div class="author-wrap">
      <span class="author-eyebrow">Author</span>
      <h1 class="author-name">Andrew Dobrow</h1>
      <p class="author-role">Founder and Publisher, Treasure Coast Today</p>
      <div class="author-body">
        <p>Andrew Dobrow is the founder and publisher of Treasure Coast Today, an independent local news outlet serving Martin, St. Lucie and Indian River counties.</p>
        <p>Based in Hobe Sound, Andrew focuses on timely, useful coverage of the issues that affect Treasure Coast residents, including local government, public safety, development, schools, sports, community events and breaking news. He created Treasure Coast Today to give readers a fast, accessible source for local reporting without unnecessary sensationalism or clutter.</p>
        <p>Andrew is committed to building stronger connections between residents, public agencies, local organizations and businesses throughout the Treasure Coast.</p>
        <p>As publisher, Andrew is responsible for the editorial standards, accuracy and independence of everything published on Treasure Coast Today. You can read more about <a href="/editorial-standards.html">how our coverage is produced</a>, <a href="/corrections-policy.html">how we handle corrections</a>, and <a href="/ownership.html">how the site is owned and funded</a>.</p>
        <hr class="author-divider">
        <div class="author-contact-card">
          <strong>Get in touch.</strong> Readers can reach Andrew at <a href="mailto:hello@treasurecoast.today">hello@treasurecoast.today</a> with story tips, questions, or feedback.
        </div>
      </div>
    </div>
  </main>
{footer}
</body>
</html>"""


def _policy_page_css():
    return """
    .policy-wrap { max-width: 720px; margin: 56px auto 80px; padding: 0 24px; }
    .policy-eyebrow { font-size: 11px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: var(--accent); margin-bottom: 14px; display: block; }
    .policy-headline { font-family: 'Fraunces', serif; font-size: clamp(30px, 5vw, 44px); font-weight: 600; line-height: 1.1; color: var(--text); margin: 0 0 10px; letter-spacing: -.02em; }
    .policy-updated { font-size: 12px; color: var(--text-muted); margin: 0 0 32px; }
    .policy-body { font-size: 16px; color: var(--text-secondary); line-height: 1.75; }
    .policy-body p { margin: 0 0 20px; }
    .policy-body h2 { font-family: 'Fraunces', serif; font-size: 22px; font-weight: 500; color: var(--text); margin: 38px 0 12px; }
    .policy-body ul { margin: 0 0 20px; padding-left: 22px; }
    .policy-body li { margin: 0 0 10px; line-height: 1.7; }
    .policy-body a { color: var(--accent); font-weight: 500; text-decoration: none; }
    .policy-body a:hover { text-decoration: underline; }
    .policy-divider { border: none; border-top: 1px solid var(--border); margin: 36px 0; }
    .policy-callout { background: var(--bg-secondary); border-left: 4px solid var(--accent); border-radius: 10px; padding: 18px 22px; margin: 0 0 20px; font-size: 15px; line-height: 1.7; }
    .policy-callout strong { color: var(--text); }
    .policy-nav { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 40px; padding-top: 24px; border-top: 1px solid var(--border); }
    .policy-nav a { font-size: 13px; color: var(--accent); font-weight: 600; text-decoration: none; }
    .policy-nav a:hover { text-decoration: underline; }
    """


def _policy_footer_nav(current=""):
    links = [
        ("/about.html", "About"),
        ("/editorial-standards.html", "Editorial Standards"),
        ("/corrections-policy.html", "Corrections Policy"),
        ("/ownership.html", "Ownership &amp; Funding"),
        ("/author/andrew-dobrow.html", "Author"),
        ("/contact.html", "Contact"),
    ]
    items = "".join(
        f'<a href="{href}">{label}</a>'
        for href, label in links if href != current
    )
    return f'<div class="policy-nav">{items}</div>'


def render_editorial_standards_page():
    head   = _page_head(
        "Editorial Standards | Treasure Coast Today",
        "How Treasure Coast Today reports, sources, edits and publishes local news for Martin, St. Lucie and Indian River counties.",
        "/editorial-standards.html",
    )
    header = _page_header()
    footer = _page_footer()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
  <style>{_policy_page_css()}</style>
</head>
<body>
{header}
  <main>
    <div class="policy-wrap">
      <span class="policy-eyebrow">Editorial Standards</span>
      <h1 class="policy-headline">Editorial Standards</h1>
      <p class="policy-updated">How we report, source and publish the news.</p>
      <div class="policy-body">
        <p>Treasure Coast Today is an independent local news outlet serving Martin, St. Lucie and Indian River counties. Our goal is to give residents accurate, timely and useful coverage of the issues that affect their communities, without sensationalism or clutter.</p>

        <h2>Our mission</h2>
        <p>We cover local government, public safety, development, schools, sports, community events and breaking news across the Treasure Coast. We prioritize stories that have a direct impact on the people who live and work here, and we aim to present them clearly and fairly.</p>

        <h2>Sourcing</h2>
        <p>Our reporting draws on public records, official statements and releases from government agencies, law enforcement, school districts and other public bodies, publicly available reporting, and information provided directly to us by residents and organizations. We aim to attribute information to its source so readers can judge it for themselves.</p>

        <h2>How our coverage is produced</h2>
        <p>Treasure Coast Today uses automated tools to help gather, organize and synthesize information from public sources and to assist in drafting and surfacing coverage. All coverage is produced and published under the editorial oversight of the publisher, Andrew Dobrow, who is responsible for what appears on this site.</p>
        <p>We use technology to help us cover more local news more quickly, but the editorial responsibility for accuracy, fairness and judgment rests with us, not with any tool.</p>

        <h2>Accuracy and corrections</h2>
        <p>We work to get things right, and when we get something wrong we correct it promptly and transparently. If you spot an error, please tell us. See our <a href="/corrections-policy.html">Corrections Policy</a> for how we handle mistakes.</p>

        <h2>Independence</h2>
        <p>Treasure Coast Today is independently owned and personally funded, with no parent company and no outside investors. Advertising and editorial are kept separate: advertisers do not receive coverage in exchange for their business, and paying for an ad does not influence how or whether we report a story. See our <a href="/ownership.html">Ownership &amp; Funding</a> page for details.</p>

        <h2>Fairness</h2>
        <p>We aim to be fair to the people and institutions we cover, to give a reasonable opportunity for response where appropriate, and to distinguish clearly between news and opinion.</p>

        <div class="policy-callout">
          <strong>Have a concern about a story?</strong> Email <a href="mailto:corrections@treasurecoast.today">corrections@treasurecoast.today</a> for factual errors, or <a href="mailto:hello@treasurecoast.today">hello@treasurecoast.today</a> for anything else.
        </div>
      </div>
      {_policy_footer_nav("/editorial-standards.html")}
    </div>
  </main>
{footer}
</body>
</html>"""


def render_corrections_page():
    head   = _page_head(
        "Corrections Policy | Treasure Coast Today",
        "How to report an error and how Treasure Coast Today handles corrections, clarifications and updates.",
        "/corrections-policy.html",
    )
    header = _page_header()
    footer = _page_footer()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
  <style>{_policy_page_css()}</style>
</head>
<body>
{header}
  <main>
    <div class="policy-wrap">
      <span class="policy-eyebrow">Corrections Policy</span>
      <h1 class="policy-headline">Corrections Policy</h1>
      <p class="policy-updated">We would rather be corrected than be wrong.</p>
      <div class="policy-body">
        <p>Treasure Coast Today is committed to accuracy. When we make a mistake, we fix it promptly and openly. This page explains how to report an error and how we handle corrections.</p>

        <h2>How to report an error</h2>
        <p>If you believe something we published is inaccurate, email <a href="mailto:corrections@treasurecoast.today">corrections@treasurecoast.today</a> with the headline or link to the story and a clear description of what you believe is wrong. If you can point us to a source for the correct information, that helps us review it faster.</p>

        <h2>How we handle corrections</h2>
        <ul>
          <li><strong>Factual errors</strong> are corrected as soon as we have confirmed the correct information.</li>
          <li>When we correct a material error in a published story, we update the article and, where appropriate, note that a correction was made.</li>
          <li><strong>Clarifications</strong> are added when a story is accurate but could be misunderstood.</li>
          <li><strong>Updates</strong> are made when a developing story changes after publication.</li>
        </ul>

        <h2>Our commitment</h2>
        <p>We review every correction request we receive. We do not ignore credible reports of errors, and we do not quietly delete stories to avoid acknowledging a mistake. Transparency is part of earning your trust.</p>

        <div class="policy-callout">
          <strong>Report a correction:</strong> <a href="mailto:corrections@treasurecoast.today">corrections@treasurecoast.today</a>
        </div>
      </div>
      {_policy_footer_nav("/corrections-policy.html")}
    </div>
  </main>
{footer}
</body>
</html>"""


def render_ownership_page():
    head   = _page_head(
        "Ownership &amp; Funding | Treasure Coast Today",
        "Treasure Coast Today is independently owned and personally funded by Andrew Dobrow, with no parent company and no outside investors.",
        "/ownership.html",
    )
    header = _page_header()
    footer = _page_footer()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
  <style>{_policy_page_css()}</style>
</head>
<body>
{header}
  <main>
    <div class="policy-wrap">
      <span class="policy-eyebrow">Ownership &amp; Funding</span>
      <h1 class="policy-headline">Ownership &amp; Funding</h1>
      <p class="policy-updated">Who owns Treasure Coast Today, and how it is funded.</p>
      <div class="policy-body">
        <h2>Ownership</h2>
        <p>Treasure Coast Today is independently owned and operated by Andrew Dobrow, its founder and publisher. It is a sole proprietorship with a single owner. There is no parent company, no corporate group, and no outside ownership stake in the publication.</p>

        <h2>Funding</h2>
        <p>Treasure Coast Today is personally funded by its owner and supported by advertising. It has no outside investors, grants, or financial backers, and it is not funded by any political party, campaign, government agency or advocacy organization.</p>

        <h2>Advertising and independence</h2>
        <p>Advertising revenue helps keep Treasure Coast Today free to read, with no paywall. Advertising is kept separate from editorial decisions. Advertisers do not receive news coverage in exchange for their business, and buying an ad does not influence whether or how we report on a person, business or organization. Advertisements are identified as such.</p>

        <h2>Our independence</h2>
        <p>Because we answer to no parent company and no investors, our coverage decisions are our own. We are accountable to our readers on the Treasure Coast, and to the standards described on our <a href="/editorial-standards.html">Editorial Standards</a> page.</p>

        <div class="policy-callout">
          <strong>Questions about ownership or funding?</strong> Email <a href="mailto:hello@treasurecoast.today">hello@treasurecoast.today</a>.
        </div>
      </div>
      {_policy_footer_nav("/ownership.html")}
    </div>
  </main>
{footer}
</body>
</html>"""


def render_about_page():
    head   = _page_head("About | Treasure Coast Today", "Treasure Coast Today is an independent local news outlet covering Martin, St. Lucie, and Indian River counties, Florida. Local government, crime, business, sports and weather for the Treasure Coast.", "/about.html")
    header = _page_header(active="about")
    footer = _page_footer()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
  <style>
    .about-wrap {{ max-width: 720px; margin: 56px auto 80px; padding: 0 24px; }}
    .about-eyebrow {{ font-size: 11px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: var(--accent); margin-bottom: 14px; display: block; }}
    .about-headline {{ font-family: 'Fraunces', serif; font-size: clamp(32px, 5vw, 48px); font-weight: 600; line-height: 1.1; color: var(--text); margin: 0 0 24px; letter-spacing: -.02em; }}
    .about-body {{ font-size: 16px; color: var(--text-secondary); line-height: 1.75; }}
    .about-body p {{ margin: 0 0 20px; }}
    .about-body h2 {{ font-family: 'Fraunces', serif; font-size: 22px; font-weight: 500; color: var(--text); margin: 40px 0 12px; }}
    .about-divider {{ border: none; border-top: 1px solid var(--border); margin: 40px 0; }}
    .about-contact {{ display: inline-block; margin-top: 8px; color: var(--accent); font-weight: 500; text-decoration: none; }}
    .about-contact:hover {{ text-decoration: underline; }}
    .about-nav {{ display: flex; gap: 16px; flex-wrap: wrap; margin-top: 40px; padding-top: 24px; border-top: 1px solid var(--border); }}
    .about-nav a {{ font-size: 13px; color: var(--accent); font-weight: 600; text-decoration: none; }}
    .about-nav a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
{header}
  <main>
    <div class="about-wrap">
      <span class="about-eyebrow">About</span>
      <h1 class="about-headline">Local news for Florida's Treasure Coast.</h1>
      <div class="about-body">
        <p>Treasure Coast Today is an independent local news outlet covering Martin County, St. Lucie County, and Indian River County, Florida. We bring residents the stories that matter most close to home.</p>
        <p>Our focus is simple: the news that actually affects the people who live and work here. From county commission decisions in Stuart to development in Port St. Lucie, school district news in Vero Beach to public safety in Fort Pierce.</p>
        <p>Treasure Coast Today was founded by Andrew Dobrow, who serves as its publisher. It is independently owned and personally funded, with no parent company and no outside investors, so our coverage decisions answer only to our readers.</p>
        <h2>Coverage area</h2>
        <p><strong>Martin County:</strong> Stuart, Jensen Beach, Palm City, Hobe Sound, Port Salerno.</p>
        <p><strong>St. Lucie County:</strong> Port St. Lucie, Fort Pierce, St. Lucie West.</p>
        <p><strong>Indian River County:</strong> Vero Beach, Sebastian, Fellsmere.</p>
        <h2>How we work</h2>
        <p>We hold ourselves to clear standards for sourcing, accuracy and independence. Learn more about <a href="/editorial-standards.html" class="about-contact">our editorial standards</a>, <a href="/corrections-policy.html" class="about-contact">how we handle corrections</a>, and <a href="/ownership.html" class="about-contact">who owns and funds this site</a>.</p>
        <h2>Advertise with us</h2>
        <p>Connect your business with engaged local readers. <a href="/advertise.html" class="about-contact">Learn more &rarr;</a></p>
        <hr class="about-divider">
        <h2>Get in touch</h2>
        <p>Have a news tip, a correction, or a question? <a href="/contact.html" class="about-contact">Contact us &rarr;</a> or email <a href="mailto:hello@treasurecoast.today" class="about-contact">hello@treasurecoast.today</a>.</p>
        <div class="about-nav">
          <a href="/editorial-standards.html">Editorial Standards</a>
          <a href="/corrections-policy.html">Corrections Policy</a>
          <a href="/ownership.html">Ownership &amp; Funding</a>
          <a href="/author/andrew-dobrow.html">Author</a>
          <a href="/contact.html">Contact</a>
        </div>
      </div>
    </div>
  </main>
{footer}
</body>
</html>"""



def render_advertise_page():
    """Generate advertise.html — Formspree contact form for ad inquiries."""
    head   = _page_head("Advertise — Treasure Coast Today", "Reach thousands of Treasure Coast readers every day. Advertise with Treasure Coast Today.", "/advertise.html")
    header = _page_header(active="advertise")
    footer = _page_footer()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
  <style>
    .adv-wrap {{ max-width: 720px; margin: 56px auto 80px; padding: 0 24px; }}
    .adv-eyebrow {{ font-size: 11px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: var(--accent); margin-bottom: 14px; display: block; }}
    .adv-headline {{ font-family: 'Fraunces', serif; font-size: clamp(32px, 5vw, 52px); font-weight: 600; line-height: 1.1; color: var(--text); margin: 0 0 20px; letter-spacing: -.02em; }}
    .adv-sub {{ font-size: 16px; color: var(--text-secondary); line-height: 1.65; margin: 0 0 40px; max-width: 560px; }}
    .adv-stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: var(--border); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; margin-bottom: 48px; }}
    .adv-stat {{ background: var(--bg); padding: 20px 18px; text-align: center; }}
    .adv-stat-num {{ font-family: 'Fraunces', serif; font-size: 28px; font-weight: 600; color: var(--accent); display: block; line-height: 1; margin-bottom: 6px; }}
    .adv-stat-label {{ font-size: 12px; color: var(--text-secondary); line-height: 1.4; }}
    .adv-divider {{ border: none; border-top: 1px solid var(--border); margin: 0 0 40px; }}
    .adv-form-title {{ font-family: 'Fraunces', serif; font-size: 22px; font-weight: 500; color: var(--text); margin: 0 0 28px; }}
    .adv-form {{ display: flex; flex-direction: column; gap: 20px; }}
    .adv-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .adv-field {{ display: flex; flex-direction: column; gap: 6px; }}
    .adv-field label {{ font-size: 12px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--text-secondary); }}
    .adv-field input, .adv-field select, .adv-field textarea {{ background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 11px 14px; font-family: 'DM Sans', sans-serif; font-size: 14px; color: var(--text); outline: none; transition: border-color .15s; width: 100%; box-sizing: border-box; -webkit-appearance: none; }}
    .adv-field input:focus, .adv-field select:focus, .adv-field textarea:focus {{ border-color: var(--accent); }}
    .adv-field select {{ background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%230A7075' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 14px center; padding-right: 36px; cursor: pointer; }}
    .adv-field textarea {{ resize: vertical; min-height: 100px; }}
    .adv-field input::placeholder, .adv-field textarea::placeholder {{ color: var(--text-secondary); opacity: .5; }}
    .adv-check-group {{ display: flex; flex-direction: column; gap: 10px; }}
    .adv-check {{ display: flex; align-items: center; gap: 10px; cursor: pointer; }}
    .adv-check input[type="checkbox"] {{ position: absolute; opacity: 0; width: 0; height: 0; }}
    .adv-check-box {{ width: 18px; height: 18px; min-width: 18px; border: 2px solid var(--border); border-radius: 4px; background: var(--bg); display: flex; align-items: center; justify-content: center; transition: background .15s, border-color .15s; flex-shrink: 0; }}
    .adv-check input[type="checkbox"]:checked + .adv-check-box {{ background: var(--accent); border-color: var(--accent); }}
    .adv-check input[type="checkbox"]:checked + .adv-check-box::after {{ content: ""; display: block; width: 5px; height: 9px; border: 2px solid white; border-top: none; border-left: none; transform: rotate(45deg) translate(-1px, -1px); }}
    .adv-check span {{ font-size: 14px; color: var(--text); line-height: 1.4; }}
    .adv-submit {{ background: var(--accent); color: white; border: none; border-radius: 8px; padding: 14px 28px; font-family: 'DM Sans', sans-serif; font-size: 15px; font-weight: 600; cursor: pointer; transition: opacity .15s; align-self: flex-start; }}
    .adv-submit:hover {{ opacity: .88; }}
    .adv-submit:disabled {{ opacity: .5; cursor: not-allowed; }}
    .adv-success {{ display: none; background: var(--bg); border: 1px solid var(--accent); border-radius: 12px; padding: 32px; text-align: center; }}
    .adv-success-icon {{ font-size: 36px; display: block; margin-bottom: 12px; }}
    .adv-success h3 {{ font-family: 'Fraunces', serif; font-size: 22px; color: var(--text); margin: 0 0 8px; }}
    .adv-success p {{ font-size: 14px; color: var(--text-secondary); margin: 0; }}
    .adv-fine {{ font-size: 12px; color: var(--text-secondary); line-height: 1.6; margin-top: 4px; }}
    @media (max-width: 580px) {{ .adv-wrap {{ margin-top: 32px; }} .adv-row {{ grid-template-columns: 1fr; }} .adv-stats {{ grid-template-columns: 1fr; }} .adv-submit {{ width: 100%; text-align: center; }} }}
  </style>
</head>
<body>
{header}
  <main>
    <div class="adv-wrap">
      <span class="adv-eyebrow">Advertising</span>
      <h1 class="adv-headline">Reach the Treasure Coast every day.</h1>
      <p class="adv-sub">Treasure Coast Today delivers local news to Martin, St. Lucie, and Indian River County residents throughout the day, every day. Your business appears alongside stories they actually read.</p>
      <div class="adv-stats">
        <div class="adv-stat"><span class="adv-stat-num">706K+</span><span class="adv-stat-label">Residents across Martin, St. Lucie &amp; Indian River counties</span></div>
        <div class="adv-stat"><span class="adv-stat-num">100%</span><span class="adv-stat-label">No paywall. Every reader sees your ad, every time</span></div>
        <div class="adv-stat"><span class="adv-stat-num">Top 5</span><span class="adv-stat-label">Fastest-growing metro in the U.S. with new residents every day</span></div>
      </div>
      <hr class="adv-divider">
      <h2 class="adv-form-title">Tell us about your business</h2>
      <form class="adv-form" id="advForm" action="https://formspree.io/f/mqejrpdv" method="POST">
        <div class="adv-row">
          <div class="adv-field"><label for="name">Your name *</label><input type="text" id="name" name="name" required placeholder="Jane Smith"></div>
          <div class="adv-field"><label for="business">Business name *</label><input type="text" id="business" name="business" required placeholder="Sunrise Realty"></div>
        </div>
        <div class="adv-row">
          <div class="adv-field"><label for="email">Email address *</label><input type="email" id="email" name="email" required placeholder="jane@example.com"></div>
          <div class="adv-field"><label for="phone">Phone number</label><input type="tel" id="phone" name="phone" placeholder="(772) 555-0100"></div>
        </div>
        <div class="adv-field"><label for="website">Website</label><input type="url" id="website" name="website" placeholder="https://yourbusiness.com"></div>
        <div class="adv-field">
          <label for="industry">Industry / business type *</label>
          <select id="industry" name="industry" required>
            <option value="" disabled selected>Select one</option>
            <option>Real estate</option><option>Restaurant / food &amp; beverage</option><option>Healthcare / medical</option><option>Legal services</option><option>Home services / contractors</option><option>Retail</option><option>Financial services</option><option>Automotive</option><option>Non-profit / community org</option><option>Events / entertainment</option><option>Education</option><option>Tourism / hospitality</option><option>Other</option>
          </select>
        </div>
        <div class="adv-field">
          <label>Which counties are most important for your audience?</label>
          <div class="adv-check-group">
            <label class="adv-check"><input type="checkbox" name="counties" value="Martin County"><div class="adv-check-box"></div><span>Martin County (Stuart, Jensen Beach, Palm City, Hobe Sound)</span></label>
            <label class="adv-check"><input type="checkbox" name="counties" value="St. Lucie County"><div class="adv-check-box"></div><span>St. Lucie County (Port St. Lucie, Fort Pierce)</span></label>
            <label class="adv-check"><input type="checkbox" name="counties" value="Indian River County"><div class="adv-check-box"></div><span>Indian River County (Vero Beach, Sebastian)</span></label>
            <label class="adv-check"><input type="checkbox" name="counties" value="All three counties"><div class="adv-check-box"></div><span>All three counties</span></label>
          </div>
        </div>
        <div class="adv-field">
          <label for="budget">Estimated monthly budget</label>
          <select id="budget" name="budget"><option value="" disabled selected>Select a range</option><option>Under $250/month</option><option>$250 – $500/month</option><option>$500 – $1,000/month</option><option>$1,000 – $2,500/month</option><option>$2,500+/month</option><option>Not sure yet</option></select>
        </div>
        <div class="adv-field">
          <label for="goal">What's the main goal of your advertising?</label>
          <select id="goal" name="goal"><option value="" disabled selected>Select one</option><option>Drive traffic to my website</option><option>Increase foot traffic / calls</option><option>Promote a specific event or offer</option><option>Build brand awareness in the area</option><option>Reach new customers in a specific county</option><option>Other</option></select>
        </div>
        <div class="adv-field">
          <label for="start">When are you looking to start?</label>
          <select id="start" name="start"><option value="" disabled selected>Select one</option><option>As soon as possible</option><option>Within the next month</option><option>1–3 months from now</option><option>Just exploring for now</option></select>
        </div>
        <div class="adv-field"><label for="message">Anything else you'd like us to know?</label><textarea id="message" name="message" placeholder="Tell us about your business, upcoming promotions, or any questions..."></textarea></div>
        <p class="adv-fine">We'll get back to you within one business day. No spam, no automated sales sequences.</p>
        <button type="submit" class="adv-submit" id="submitBtn">Send inquiry &rarr;</button>
      </form>
      <div class="adv-success" id="successMsg">
        <span class="adv-success-icon">&#10003;</span>
        <h3>Got it — thanks!</h3>
        <p>We'll be in touch within one business day.</p>
      </div>
    </div>
  </main>
{footer}
  <script>
    const form=document.getElementById('advForm'),success=document.getElementById('successMsg'),btn=document.getElementById('submitBtn');
    form.addEventListener('submit',async(e)=>{{
      e.preventDefault();btn.disabled=true;btn.textContent='Sending...';
      try{{
        const res=await fetch(form.action,{{method:'POST',body:new FormData(form),headers:{{'Accept':'application/json'}}}});
        if(res.ok){{form.style.display='none';success.style.display='block';}}
        else{{btn.disabled=false;btn.textContent='Send inquiry \u2192';alert('Something went wrong. Please try again.');}}
      }}catch(err){{btn.disabled=false;btn.textContent='Send inquiry \u2192';alert('Something went wrong. Please try again.');}}
    }});
  </script>
</body>
</html>"""

def write_data_json(all_categories, top_cat):
    def card_to_dict(c):
        return {
            "headline":      c.get("headline", ""),
            "teaser":        c.get("teaser", ""),
            "body":          c.get("body", ""),
            "published":     c.get("published", ""),
            "cat_label":     c.get("cat_label", "") or c.get("category_label", ""),
            "urgency_score": c.get("urgency_score", 0),
            "image_url":     c.get("image_url", ""),
        }
    _all = []
    for cat in all_categories:
        hero = cat["hero"]
        _all.append({**hero, "cat_label": cat["category_label"], "is_hero": True})
        for card in cat.get("cards", []):
            _all.append({**card, "cat_label": cat["category_label"], "is_hero": False})
    _all.sort(key=lambda c: int(c.get("urgency_score", 0) or 0), reverse=True)
    fp_key = re.sub(r"[^a-z0-9 ]", "", top_cat["hero"].get("headline","").lower())[:60]
    seen, deduped = set(), []
    for c in _all:
        k = re.sub(r"[^a-z0-9 ]", "", c.get("headline","").lower())[:60]
        if k != fp_key and k not in seen:
            seen.add(k); deduped.append(c)
    app_data = {
        "updated": now_et(),
        "front_page": {
            "hero": {
                "headline":      top_cat["hero"].get("headline", ""),
                "teaser":        top_cat["hero"].get("teaser", ""),
                "body":          top_cat["hero"].get("body", ""),
                "image_url":     top_cat["hero"].get("image_url", ""),
                "image_credit":  top_cat["hero"].get("image_credit", ""),
                "published":     top_cat["hero"].get("published", ""),
                "cat_label":     top_cat["category_label"],
                "urgency_score": top_cat["hero"].get("urgency_score", 0),
            },
            "cards": [card_to_dict(c) for c in deduped[:6]],
        },
        "categories": [
            {
                "key":   cat["category_key"],
                "label": cat["category_label"],
                "hero":  card_to_dict(cat["hero"]),
                "cards": [card_to_dict(c) for c in cat.get("cards", [])[:6]],
            }
            for cat in all_categories
        ],
    }
    (OUTPUT_DIR / "data.json").write_text(json.dumps(app_data, indent=2), encoding="utf-8")
    print("  data.json written")


def classify_story_relationship(new_item, existing_entry):
    """Classify how an incoming article relates to an existing canonical.

    Returns one of:
      SAME_EVENT    - advances the same underlying case/event and may evolve the URL.
      RELATED_ANGLE - reaction, profile, advice, analysis, consequence, or local response;
                      must remain a separate permalink but may be cross-linked.
      DISTINCT      - merely shares a broad topic and must remain fully independent.

    This deliberately separates event identity from topical similarity. For example,
    outbreak case-count updates are SAME_EVENT with earlier outbreak reporting, while a
    profile of a resident growing vegetables because of outbreak fears is RELATED_ANGLE.
    """
    new_item = new_item or {}
    existing_entry = existing_entry or {}
    new_headline = (new_item.get("headline") or "").strip()
    new_teaser = (new_item.get("teaser") or new_item.get("body", "")[:500] or "").strip()
    old_headline = (existing_entry.get("headline") or "").strip()
    old_teaser = (existing_entry.get("teaser") or existing_entry.get("body", "")[:500] or "").strip()

    new_key = _known_event_key(" ".join([new_headline, new_teaser]))
    old_key = _known_event_key(" ".join([old_headline, old_teaser]))
    if new_key and old_key and new_key == old_key:
        return "SAME_EVENT"

    prompt = (
        "Classify the relationship between two local-news articles. Choose exactly one label.\n\n"
        "SAME_EVENT: The new article advances the same underlying incident, case, outbreak, "
        "government action, court proceeding, investigation, game, closure, or other concrete "
        "news event. New counts, arrests, rulings, identifications, official findings, reopening, "
        "or status changes in that same event belong here.\n\n"
        "RELATED_ANGLE: The articles concern the same broader issue, but the new article is a "
        "reaction, human-interest profile, community response, advice/explainer, analysis, "
        "consequence, business response, or behavior change. It deserves its own permalink and "
        "must never replace the event article. Example: an outbreak case-count article versus a "
        "resident growing food because of concern about the outbreak.\n\n"
        "DISTINCT: They only share a broad topic or keywords and concern different events, people, "
        "organizations, places, or proceedings.\n\n"
        f"EXISTING ARTICLE:\nHeadline: {old_headline}\nSummary: {old_teaser[:500]}\n\n"
        f"NEW ARTICLE:\nHeadline: {new_headline}\nSummary: {new_teaser[:500]}\n\n"
        "Answer only SAME_EVENT, RELATED_ANGLE, or DISTINCT."
    )
    try:
        resp = client.messages.create(
            model=MODEL_SELECTION, max_tokens=18,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = resp.content[0].text.strip().upper().replace(" ", "_")
        if "RELATED" in answer:
            return "RELATED_ANGLE"
        if "SAME" in answer:
            return "SAME_EVENT"
        return "DISTINCT"
    except Exception as e:
        # Fail closed: an unavailable classifier must never permit a canonical overwrite.
        print(f"    Story relationship check failed ({e}); treating as DISTINCT")
        return "DISTINCT"


def _related_angle_fallback_link(related_entry):
    """Return a safe, non-merged related-story link when context cannot be proven."""
    slug = (related_entry or {}).get("slug", "")
    headline = ((related_entry or {}).get("headline") or "Related local coverage").strip()
    if not slug:
        return ""
    url = f"{SITE_URL}/articles/{slug}.html"
    return f"**Related:** [{headline}]({url})"


def _build_contextual_related_paragraph(canonical, related_entry):
    """Create a concise bridge that explains why a related angle belongs.

    The result must connect the related feature to the canonical event in two or three
    sentences. It may not simply summarize the feature or list colorful details. When
    the model cannot establish a supported causal/contextual connection, this function
    returns an empty string and the caller uses only a Related link.
    """
    canonical = canonical or {}
    related_entry = related_entry or {}
    related_slug = related_entry.get("slug", "")
    if not related_slug:
        return ""

    canonical_headline = (canonical.get("headline") or "").strip()
    canonical_context = re.sub(r"\s+", " ", (
        canonical.get("teaser") or canonical.get("body", "")[:1400] or ""
    ).strip())
    related_headline = (related_entry.get("headline") or "").strip()
    related_context = re.sub(r"\s+", " ", (
        related_entry.get("teaser") or related_entry.get("body", "")[:1400] or ""
    ).strip())
    related_url = f"{SITE_URL}/articles/{related_slug}.html"

    prompt = (
        "You are editing a local-news canonical article. Write one short contextual "
        "bridge paragraph of exactly 2 or 3 sentences that explains WHY the related "
        "story belongs in the canonical article. The first sentence must state the "
        "connection to the canonical event (reaction, behavior change, local impact, "
        "consequence, advice, or response). Use only facts supported by the supplied "
        "text. Do not invent motive or causation. Do not merely list details from the "
        "related story. Keep the paragraph under 90 words. End with a natural markdown "
        "link to the related article using its headline. If the supplied text does not "
        "support a clear connection, answer exactly NO_CONTEXT.\n\n"
        f"CANONICAL HEADLINE: {canonical_headline}\n"
        f"CANONICAL CONTEXT: {canonical_context[:1400]}\n\n"
        f"RELATED HEADLINE: {related_headline}\n"
        f"RELATED CONTEXT: {related_context[:1400]}\n"
        f"RELATED URL: {related_url}\n"
    )
    try:
        resp = client.messages.create(
            model=MODEL_SELECTION,
            max_tokens=220,
            messages=[{"role": "user", "content": prompt}],
        )
        paragraph = re.sub(r"\s+", " ", resp.content[0].text.strip())
    except Exception as e:
        print(f"    Related-angle context generation failed ({e}); using link only")
        return ""

    if not paragraph or paragraph.upper() == "NO_CONTEXT":
        return ""

    # Structural and editorial validation. Fail closed to a plain Related link.
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", paragraph) if x.strip()]
    if len(sentences) not in (2, 3) or len(paragraph.split()) > 95:
        return ""
    if related_url not in paragraph and f"/articles/{related_slug}.html" not in paragraph:
        return ""

    connection_terms = (
        "response", "reaction", "concern", "because", "prompt", "led", "influenc",
        "impact", "effect", "amid", "as residents", "as families", "in light of",
        "against that backdrop", "the outbreak", "the investigation", "the case",
        "the crash", "the ruling", "the closure", "the recall", "food safety",
    )
    first_sentence = sentences[0].lower()
    if not any(term in first_sentence for term in connection_terms):
        return ""

    # Reject list-heavy garden/profile copy that does not advance the canonical story.
    list_markers = ("includes", "including", "pineapple", "bananas", "peppers", "herbs")
    if sum(marker in paragraph.lower() for marker in list_markers) >= 3:
        return ""

    return paragraph


def _append_related_angle_to_canonical(canonical, related_entry, articles_dir):
    """Cross-link a related angle without merging story identities.

    A related profile/reaction remains a separate permalink. The canonical receives
    either a validated 2-3 sentence context bridge or, when the relationship cannot be
    supported cleanly, only a Related link. Headline, teaser, slug, publication date,
    and RSS freshness remain untouched.
    """
    if not canonical or not related_entry:
        return False
    canonical_slug = canonical.get("slug", "")
    related_slug = related_entry.get("slug", "")
    if not canonical_slug or not related_slug or canonical_slug == related_slug:
        return False

    body = (canonical.get("body") or "").strip()
    start_marker = f"<!-- RELATED-ANGLE:{related_slug}:START -->"
    end_marker = f"<!-- RELATED-ANGLE:{related_slug}:END -->"

    contextual_paragraph = _build_contextual_related_paragraph(canonical, related_entry)
    addition = contextual_paragraph or _related_angle_fallback_link(related_entry)
    if not addition:
        return False
    block = f"{start_marker}\n{addition}\n{end_marker}"

    # Idempotent replacement: reruns improve the same related block rather than append
    # another paragraph. Older unmarked article prose is intentionally left untouched.
    marker_pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker), re.S
    )
    if marker_pattern.search(body):
        new_body = marker_pattern.sub(block, body)
        if new_body == body:
            return False
        canonical["body"] = new_body
    else:
        related_url = f"{SITE_URL}/articles/{related_slug}.html"
        if related_url in body or f"/articles/{related_slug}.html" in body:
            # A legacy unmarked link already exists. Do not append a duplicate or try
            # to rewrite surrounding historical prose automatically.
            return False
        canonical["body"] = (body + "\n\n" + block).strip() if body else block

    canonical["content_hash"] = _canonical_content_hash(
        canonical.get("headline", ""), canonical.get("teaser", ""),
        canonical.get("body", ""), canonical.get("image_url", "")
    )
    links = canonical.setdefault("related_angle_slugs", [])
    if related_slug not in links:
        links.append(related_slug)

    article_path = Path(articles_dir) / f"{canonical_slug}.html"
    if article_path.exists():
        category_key = canonical.get("category_key", "top_news")
        category_label = canonical.get("category_label") or CATEGORIES.get(category_key, {}).get("label", "Top News")
        article_path.write_text(
            render_article_page(
                canonical, category_label, category_key,
                canonical.get("date") or datetime.now(EASTERN).strftime("%Y-%m-%d"),
                canonical_slug, related=[]
            ),
            encoding="utf-8"
        )
    mode = "context bridge" if contextual_paragraph else "link only"
    print(f"  RELATED ANGLE ({mode}): linked '{related_entry.get('headline','')[:55]}' from canonical '{canonical.get('headline','')[:55]}'")
    return True


CANONICAL_CLEANUP_CONFIDENCE = 95
CANONICAL_REDIRECT_LIMIT = 5000


def _redirect_target_path(slug):
    return f"/articles/{slug}.html"


def _render_canonical_redirect_page(source_slug, target_slug, target_headline=""):
    """Static-host-safe redirect fallback."""
    target_path = _redirect_target_path(target_slug)
    target_url = f"{SITE_URL}{target_path}"
    safe_title = re.sub(r"[<>]", "", target_headline or "Article moved")
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{safe_title} | {SITE_NAME}</title>
  <link rel="canonical" href="{target_url}">
  <meta name="robots" content="noindex,follow">
  <meta http-equiv="refresh" content="0; url={target_url}">
  <script>window.location.replace({json.dumps(target_url)});</script>
</head>
<body>
  <p>This article has moved to <a href="{target_url}">{safe_title}</a>.</p>
</body>
</html>'''


def _canonical_candidate_score(entry):
    return (
        1 if entry.get("is_custom") or entry.get("authoritative_custom") else 0,
        int(entry.get("article_word_count", 0) or 0),
        entry.get("lastmod") or entry.get("date") or "",
    )


def _strict_custom_duplicate_pair(candidate, canonical):
    if not candidate or not canonical or candidate.get("slug") == canonical.get("slug"):
        return False, 0
    if candidate.get("is_custom") or candidate.get("authoritative_custom"):
        return False, 0
    if not (canonical.get("is_custom") or canonical.get("authoritative_custom")):
        return False, 0
    a = _event_audit_item(candidate, "archive")
    b = _event_audit_item(canonical, "archive")
    # Major milestones are still part of the same event and must consolidate.
    if not _same_story_topic(a, b):
        return False, 0
    confidence = _story_match_confidence(a, b)
    known_a = _known_event_key(_story_text(a))
    known_b = _known_event_key(_story_text(b))
    if known_a and known_a == known_b:
        confidence = max(confidence, 99)
    return confidence >= CANONICAL_CLEANUP_CONFIDENCE, confidence


def apply_canonical_story_cleanup(archive, articles_dir, output_root):
    """Consolidate all proven duplicate developments into one canonical article."""
    archive = list(archive or [])
    customs = [e for e in archive if e.get("slug") and
               (e.get("is_custom") or e.get("authoritative_custom"))]
    redirects = []
    removed_slugs = set()

    for candidate in archive:
        if not candidate.get("slug") or candidate.get("slug") in removed_slugs:
            continue
        best = None
        best_confidence = 0
        for canonical in customs:
            ok, confidence = _strict_custom_duplicate_pair(candidate, canonical)
            if ok and (confidence, _canonical_candidate_score(canonical)) > (best_confidence, _canonical_candidate_score(best or {})):
                best = canonical
                best_confidence = confidence
        if not best:
            continue
        removed_slugs.add(candidate["slug"])
        redirects.append({
            "source_slug": candidate["slug"],
            "source_headline": candidate.get("headline", ""),
            "target_slug": best["slug"],
            "target_headline": best.get("headline", ""),
            "story_stage": _story_stage(_story_text(_event_audit_item(candidate, "archive"))),
            "match_confidence": best_confidence,
            "canonical_is_custom": True,
            "reason": "High-confidence duplicate consolidated into authoritative custom coverage.",
        })

    # Consolidate every stable known-event group, not only custom stories. The
    # canonical URL is the authoritative custom article when one exists; otherwise
    # it is the oldest published permalink. Later developments are represented by
    # updated content at that URL and every duplicate URL becomes a 301 redirect.
    known_groups = {}
    for entry in archive:
        if not entry.get("slug"):
            continue
        key = _known_event_key(_story_text(_event_audit_item(entry, "archive")))
        if key:
            known_groups.setdefault(key, []).append(entry)

    existing_redirect_sources = {r["source_slug"] for r in redirects}
    for event_key, members in known_groups.items():
        active = [m for m in members if m.get("slug") not in removed_slugs]
        if len(active) < 2:
            continue
        custom_members = [m for m in active if m.get("is_custom") or m.get("authoritative_custom")]
        if custom_members:
            canonical = max(custom_members, key=_canonical_candidate_score)
        else:
            def _oldest_key(e):
                first = str(e.get("first_published") or "")
                date = str(e.get("date") or e.get("lastmod") or "9999-99-99")
                return (date, first, e.get("slug", ""))
            canonical = min(active, key=_oldest_key)

        for duplicate in active:
            if duplicate.get("slug") == canonical.get("slug"):
                continue
            source_slug = duplicate["slug"]
            if source_slug in existing_redirect_sources:
                continue
            removed_slugs.add(source_slug)
            existing_redirect_sources.add(source_slug)
            redirects.append({
                "source_slug": source_slug,
                "source_headline": duplicate.get("headline", ""),
                "target_slug": canonical["slug"],
                "target_headline": canonical.get("headline", ""),
                "story_stage": _story_stage(_story_text(_event_audit_item(duplicate, "archive"))),
                "match_confidence": 100,
                "canonical_is_custom": bool(canonical.get("is_custom") or canonical.get("authoritative_custom")),
                "event_key": event_key,
                "reason": "Duplicate development consolidated under the single canonical event URL.",
            })

    known_animal_sources = {
        # Exact live generated duplicate.
        "2026-07-21-martin-county-deputies-rescue-80-cats-from-stuart-home-in-worst-animal-hoarding",
        # Older truncated variants retained for backward compatibility.
        "2026-07-21-stuart-woman-arrested-after-deputies-rescue-about-80-cats-from-home-in-worst-hoa",
        "2026-07-21-martin-county-deputies-rescue-80-cats-from-stuart-home-in-worst-hoarding-case-sh",
    }
    animal_customs = [e for e in customs if re.search(r"\b(80|eighty)\b", _story_text(_event_audit_item(e, "archive")), re.I)
                      and re.search(r"\bcat", _story_text(_event_audit_item(e, "archive")), re.I)
                      and re.search(r"\bhoard", _story_text(_event_audit_item(e, "archive")), re.I)]
    if animal_customs:
        canonical = next((e for e in animal_customs if e.get("slug") ==
                          "2026-07-20-more-than-70-animals-found-in-stuart-home-during-large-scale-hoarding-response"), None)
        if canonical is None:
            canonical = max(animal_customs, key=_canonical_candidate_score)
        existing_sources = {r["source_slug"] for r in redirects}
        for source_slug in sorted(known_animal_sources - existing_sources):
            if source_slug == canonical.get("slug"):
                continue
            redirects.append({
                "source_slug": source_slug,
                "source_headline": "Previously published animal-hoarding duplicate",
                "target_slug": canonical["slug"],
                "target_headline": canonical.get("headline", ""),
                "story_stage": "canonical-migration",
                "match_confidence": 100,
                "canonical_is_custom": True,
                "reason": "Migration of a known duplicate previously removed by an older cleanup block.",
            })
            removed_slugs.add(source_slug)

    cleaned = [e for e in archive if e.get("slug") not in removed_slugs]
    if not redirects:
        return cleaned, []

    for record in redirects:
        redirect_file = articles_dir / f"{record['source_slug']}.html"
        redirect_file.write_text(
            _render_canonical_redirect_page(record["source_slug"], record["target_slug"], record["target_headline"]),
            encoding="utf-8",
        )

    data_dir = output_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = data_dir / "canonical-redirects.json"
    old_manifest = _read_json_file(manifest_path, {"redirects": []})
    merged = {r.get("source_slug"): r for r in old_manifest.get("redirects", []) if r.get("source_slug")}
    for r in redirects:
        merged[r["source_slug"]] = r
    merged_records = list(merged.values())[-CANONICAL_REDIRECT_LIMIT:]
    run_id = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    manifest_path.write_text(json.dumps({
        "schema_version": 1,
        "updated_at": run_id,
        "redirect_count": len(merged_records),
        "redirects": merged_records,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    log_path = data_dir / "canonical-cleanup-history.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        for r in redirects:
            fh.write(json.dumps({**r, "run_id": run_id, "action_taken": True}, ensure_ascii=False) + "\n")

    redirect_rules = [
        f"/articles/{r['source_slug']}.html /articles/{r['target_slug']}.html 301!"
        for r in merged_records
    ]
    (output_root / "_redirects").write_text("\n".join(redirect_rules) + "\n", encoding="utf-8")
    print(f"  Canonical Story Manager redirected {len(redirects)} duplicate URL(s) to canonical event coverage")
    return cleaned, redirects




def enforce_canonical_redirects(archive, articles_dir, output_root, current_run_redirects=None):
    """Apply every canonical redirect after all article pages have been generated.

    This is the production-critical enforcement pass. Earlier versions wrote a
    redirect page before article generation, allowing the later permalink loop to
    overwrite it with the duplicate article. V6.1 always runs last, removes redirect
    sources from archive-driven surfaces, and verifies the final HTML contents.
    """
    output_root = Path(output_root)
    articles_dir = Path(articles_dir)
    data_dir = output_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = data_dir / "canonical-redirects.json"
    payload = _read_json_file(manifest_path, {"redirects": []})
    merged = {r.get("source_slug"): r for r in payload.get("redirects", []) if r.get("source_slug")}
    for record in current_run_redirects or []:
        if record.get("source_slug"):
            merged[record["source_slug"]] = record
    records = list(merged.values())[-CANONICAL_REDIRECT_LIMIT:]

    source_slugs = {r["source_slug"] for r in records if r.get("source_slug")}
    cleaned = [e for e in (archive or []) if e.get("slug") not in source_slugs]
    verification = []
    for record in records:
        source = record.get("source_slug", "")
        target = record.get("target_slug", "")
        if not source or not target or source == target:
            continue
        path = articles_dir / f"{source}.html"
        html = _render_canonical_redirect_page(source, target, record.get("target_headline", ""))
        path.write_text(html, encoding="utf-8")
        rendered = path.read_text(encoding="utf-8")
        verification.append({
            "source_slug": source,
            "target_slug": target,
            "file_exists": path.exists(),
            "contains_target": _redirect_target_path(target) in rendered,
            "contains_noindex": 'noindex,follow' in rendered,
            "contains_replace": 'window.location.replace' in rendered,
            "passed": path.exists() and _redirect_target_path(target) in rendered
                      and 'noindex,follow' in rendered and 'window.location.replace' in rendered,
        })

    run_id = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    manifest_path.write_text(json.dumps({
        "schema_version": 2,
        "updated_at": run_id,
        "redirect_count": len(records),
        "redirects": records,
        "verification": verification,
        "all_redirect_pages_verified": all(v["passed"] for v in verification) if verification else True,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    rules = [f"/articles/{r['source_slug']}.html /articles/{r['target_slug']}.html 301!"
             for r in records if r.get("source_slug") and r.get("target_slug")]
    (output_root / "_redirects").write_text("\n".join(rules) + ("\n" if rules else ""), encoding="utf-8")
    return cleaned, verification


def write_story_regression_report(output_root, archive, redirect_verification):
    """Fail-safe regression report for production-gating known editorial cases."""
    output_root = Path(output_root)
    data_dir = output_root / "data"
    stories_payload = _read_json_file(data_dir / "stories.json", {"stories": []})
    stories = stories_payload.get("stories", [])
    manifest = _read_json_file(data_dir / "canonical-redirects.json", {"redirects": []})
    redirects = manifest.get("redirects", [])
    hoarding_key = "2026-07-stuart-martin-animal-hoarding"
    hoarding_stories = []
    for story in stories:
        members = story.get("articles", []) or []
        if any(_known_event_key(" ".join([m.get("headline", ""), m.get("teaser", "")])) == hoarding_key for m in members):
            hoarding_stories.append(story)
    hoarding_redirects = [r for r in redirects if "hoarding" in (r.get("reason", "") + " " + r.get("source_headline", "")).lower()
                          or r.get("source_slug") in {
        "2026-07-21-stuart-woman-arrested-after-deputies-rescue-about-80-cats-from-home-in-worst-hoa",
        "2026-07-21-martin-county-deputies-rescue-80-cats-from-stuart-home-in-worst-hoarding-case-sh",
    }]
    expected_sources = {
        "2026-07-21-martin-county-deputies-rescue-80-cats-from-stuart-home-in-worst-animal-hoarding",
    }
    expected_target = "2026-07-20-more-than-70-animals-found-in-stuart-home-during-large-scale-hoarding-response"
    redirect_sources = {r.get("source_slug") for r in hoarding_redirects}
    exact_live_redirect = next((r for r in redirects if r.get("source_slug") in expected_sources), None)
    archive_slugs = {e.get("slug") for e in archive or []}
    checks = {
        "hoarding_is_one_story": len(hoarding_stories) == 1,
        "hoarding_canonical_is_custom": len(hoarding_stories) == 1 and bool(hoarding_stories[0].get("canonical_is_custom")),
        "exact_custom_slug_is_canonical": len(hoarding_stories) == 1 and hoarding_stories[0].get("canonical_slug") == expected_target,
        "exact_live_duplicate_redirect_exists": expected_sources <= redirect_sources,
        "exact_live_duplicate_targets_custom": bool(exact_live_redirect) and exact_live_redirect.get("target_slug") == expected_target,
        "redirect_sources_removed_from_archive": not bool(expected_sources & archive_slugs),
        "custom_article_remains_in_archive": expected_target in archive_slugs,
        "all_redirect_html_verified": all(v.get("passed") for v in redirect_verification) if redirect_verification else False,
    }
    report = {
        "schema_version": 1,
        "engine_version": "story-centric-newsroom-v6.5.14.1",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "production_gate_passed": all(checks.values()),
        "checks": checks,
        "hoarding_story_ids": [s.get("story_id") for s in hoarding_stories],
        "hoarding_redirect_sources": sorted(redirect_sources),
    }
    (data_dir / "story-regression-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if not report["production_gate_passed"]:
        print("  WARNING: Story regression production gate FAILED; inspect data/story-regression-report.json")
    else:
        print("  Story regression production gate PASSED")
    return report

def write_story_health_report(output_root, archive, current_run_redirects=None):
    """Write a compact operational health snapshot for the Story Engine.

    The report intentionally separates cumulative totals from actions taken in the
    current run so a quiet healthy run is not confused with a failed run.
    """
    output_root = Path(output_root)
    data_dir = output_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    stories_payload = _read_json_file(data_dir / "stories.json", {"stories": []})
    stories = stories_payload.get("stories", []) if isinstance(stories_payload, dict) else []
    shadow = _read_json_file(data_dir / "story-shadow-log.json", {})
    suppression = _read_json_file(data_dir / "story-suppression-report.json", {"suppressions": []})
    redirects_payload = _read_json_file(data_dir / "canonical-redirects.json", {"redirects": []})

    redirects = redirects_payload.get("redirects", []) if isinstance(redirects_payload, dict) else []
    suppressions = suppression.get("suppressions", []) if isinstance(suppression, dict) else []
    current_run_redirects = list(current_run_redirects or [])

    today = datetime.utcnow().date()
    active_cutoff = today - timedelta(days=7)
    active = 0
    closed = 0
    largest = {"story_id": "", "story": "", "articles": 0, "canonical_slug": ""}
    multi_article_stories = 0
    custom_canonical_stories = 0
    article_total = 0

    for story in stories:
        articles = story.get("articles", []) or []
        count = len(articles)
        article_total += count
        if count > 1:
            multi_article_stories += 1
        if story.get("canonical_is_custom"):
            custom_canonical_stories += 1
        latest = None
        for article in articles:
            raw = article.get("lastmod") or article.get("date") or ""
            try:
                d = datetime.fromisoformat(str(raw)[:10]).date()
                latest = d if latest is None or d > latest else latest
            except Exception:
                pass
        if latest and latest >= active_cutoff:
            active += 1
        else:
            closed += 1
        if count > largest["articles"]:
            largest = {
                "story_id": story.get("story_id", ""),
                "story": story.get("title") or story.get("canonical_headline", ""),
                "articles": count,
                "canonical_slug": story.get("canonical_slug", ""),
            }

    # Fall back to archive counts if stories.json is unavailable on a first run.
    if not stories:
        article_total = len(archive or [])
        active = sum(1 for e in (archive or []) if str(e.get("lastmod") or e.get("date") or "")[:10] >= active_cutoff.isoformat())
        closed = max(0, article_total - active)

    summary = shadow.get("summary", {}) if isinstance(shadow, dict) else {}
    decisions = shadow.get("decisions", []) if isinstance(shadow, dict) else []
    if not isinstance(decisions, list):
        decisions = []
    custom_overrides = int(summary.get("custom_overrides", 0) or 0)
    if not custom_overrides:
        custom_overrides = sum(1 for d in decisions if d.get("decision") == "WOULD_PUBLISH_CUSTOM_OVERRIDE")
    reviews = int(summary.get("reviews", 0) or 0)
    if not reviews:
        reviews = sum(1 for d in decisions if d.get("decision") == "WOULD_REVIEW")
    major_updates = int(summary.get("major_updates", 0) or 0)
    if not major_updates:
        major_updates = sum(1 for d in decisions if d.get("decision") == "WOULD_PUBLISH_MAJOR_UPDATE")

    report = {
        "schema_version": 2,
        "engine_version": "story-centric-newsroom-v6.5.14.1",
        "generated_at": run_id,
        "active_window_days": 7,
        "stories": {
            "total": len(stories),
            "active": active,
            "closed_or_inactive": closed,
            "multi_article": multi_article_stories,
            "custom_canonical": custom_canonical_stories,
            "average_articles_per_story": round(article_total / len(stories), 3) if stories else 0,
            "largest_story": largest,
        },
        "articles": {
            "archive_total": len(archive or []),
            "story_membership_total": article_total,
        },
        "confidence_bands": {
            "clustered_85_89": int(summary.get("clustered_85_89", 0) or 0),
            "clustered_90_94": int(summary.get("clustered_90_94", 0) or 0),
            "eligible_95_plus": int(summary.get("eligible_95_plus", 0) or 0),
            "meaning": "85-94 groups stories only; 95+ may be eligible for separate guarded action.",
        },
        "actions": {
            "redirects_created_this_run": len(current_run_redirects),
            "redirects_cumulative": len(redirects),
            "actual_guarded_suppressions_this_run": int(suppression.get("suppressions_this_run", 0) or 0),
            "actual_guarded_suppressions_retained": len(suppressions),
            "custom_overrides_last_shadow_run": custom_overrides,
            "major_updates_last_shadow_run": major_updates,
            "reviews_last_shadow_run": reviews,
            "grouped_no_action_last_shadow_run": int(summary.get("grouped_no_action", 0) or 0),
        },
        "safety": {
            "story_clustering_confidence": STORY_CLUSTERING_CONFIDENCE,
            "observation_band_starts": STORY_OBSERVATION_CONFIDENCE,
            "minimum_suppression_confidence": AUTO_SUPPRESSION_CONFIDENCE,
            "minimum_canonical_cleanup_confidence": CANONICAL_CLEANUP_CONFIDENCE,
            "redirects_below_cleanup_threshold": sum(
                1 for r in redirects
                if int(r.get("match_confidence", 0) or 0) < CANONICAL_CLEANUP_CONFIDENCE
                and r.get("story_stage") != "canonical-migration"
            ),
            "suppressions_below_threshold": sum(
                1 for r in suppressions
                if int(r.get("match_confidence", 0) or 0) < AUTO_SUPPRESSION_CONFIDENCE
            ),
        },
    }
    (data_dir / "story-health-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"  Story health report: {report['stories']['total']} stories, "
        f"{len(current_run_redirects)} redirects this run, {len(suppressions)} retained suppressions"
    )
    return report


def _repair_article_shells(output_root):
    """Normalize every retained article to one banner, grid and populated sidebar.

    This pass is intentionally content-aware. Retained permanent article files may have
    been generated by older templates, so banner suitability and sidebar contents are
    recalculated from the article itself rather than inherited from the old markup.
    """
    import re
    import html as _html
    from datetime import datetime as _dt

    articles_dir = Path(output_root) / "articles"
    if not articles_dir.exists():
        return {"checked": 0, "repaired": 0, "wrapped": 0, "unrepairable": 0}

    def _plain(value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", _html.unescape(value)).strip()

    def _extract(pattern, value, flags=re.I | re.S):
        match = re.search(pattern, value, flags)
        return _plain(match.group(1)) if match else ""

    # Build a recent-story catalog first so every fallback sidebar contains real links.
    catalog = []
    for candidate in articles_dir.glob("*.html"):
        raw = candidate.read_text(encoding="utf-8", errors="ignore")
        if 'http-equiv="refresh"' in raw or "window.location.replace" in raw:
            continue
        headline = _extract(r'<h1[^>]*>(.*?)</h1>', raw)
        if not headline:
            continue
        category = _extract(r'class="article-category"[^>]*>(.*?)</', raw)
        date_text = _extract(r'class="article-date"[^>]*>(.*?)</', raw)
        iso = re.search(r'20\d{2}-\d{2}-\d{2}', raw)
        sort_key = iso.group(0) if iso else "1900-01-01"  # Never treat a repair/write timestamp as editorial freshness.
        catalog.append({
            "path": candidate,
            "slug": candidate.stem,
            "headline": headline,
            "category": category,
            "date": date_text or sort_key,
            "sort": sort_key,
        })
    catalog.sort(key=lambda item: (item["sort"], item["slug"]), reverse=True)

    sensitive_terms = (
        "murder", "murdered", "homicide", "killed", "killing", "shooting", "shot dead",
        "stabbing", "stabbed", "rape", "raped", "sexual assault", "sexual battery",
        "molest", "molestation", "molested", "child abuse", "child porn", "child sex",
        "csam", "sex abuse", "sexual abuse", "abducted", "abduction", "kidnap",
        "human trafficking", "sex trafficking", "manslaughter", "fatal shooting",
        "domestic violence", "domestic abuse", "assault", "overdose death", "suicide",
        "dead body", "body found", "remains found", "fatal crash", "deadly crash",
        "wrongful death", "death investigation", "died", "deadly collision"
    )
    sexual_terms = (
        "rape", "raped", "sexual assault", "sexual battery", "molest", "molestation",
        "molested", "child porn", "child sex", "csam", "sex abuse", "sexual abuse",
        "sex trafficking"
    )
    domestic_terms = ("domestic violence", "domestic abuse", "intimate partner violence")
    crisis_terms = ("suicide", "suicidal", "self-harm", "mental health crisis")

    ad_html = (
        '<a href="/advertise.html" class="article-banner-slot article-ad-banner" '
        'aria-label="Advertise with Treasure Coast Today">'
        '<img src="/images/advertise-banner.png" '
        'alt="Advertise with Treasure Coast Today. Reach Martin, St. Lucie and Indian River readers every day">'
        '</a>'
    )

    def _notice(label, headline, copy, resource_html=""):
        return (
            f'<section class="article-banner-slot article-house-banner" aria-label="{label}">'
            '<div class="article-house-mark" aria-hidden="true">TCT</div>'
            '<div class="article-house-copy">'
            f'<span class="article-house-label">{label}</span>'
            f'<strong class="article-house-headline">{headline}</strong>'
            f'<span class="article-house-text">{copy}</span>'
            '</div>' + resource_html + '</section>'
        )

    def _banner_for(article_text):
        lowered = article_text.lower()
        if any(term in lowered for term in sexual_terms):
            resource = ('<a class="article-house-resource" href="https://rainn.org/" target="_blank" '
                        'rel="noopener noreferrer external"><span>Confidential support</span>'
                        '<strong>RAINN: 800-656-HOPE (4673)</strong></a>')
            return _notice("Community Resource", "Support is available.",
                           "Free, confidential help is available 24 hours a day.", resource)
        if any(term in lowered for term in domestic_terms):
            resource = ('<a class="article-house-resource" href="https://www.thehotline.org/" target="_blank" '
                        'rel="noopener noreferrer external"><span>Confidential support</span>'
                        '<strong>Call 800-799-SAFE or text START to 88788</strong></a>')
            return _notice("Community Resource", "You are not alone.",
                           "Confidential domestic violence support is available 24 hours a day.", resource)
        if any(term in lowered for term in crisis_terms):
            resource = ('<a class="article-house-resource" href="https://988lifeline.org/" target="_blank" '
                        'rel="noopener noreferrer external"><span>Free and confidential</span>'
                        '<strong>Call or text 988</strong></a>')
            return _notice("Community Resource", "Help is available now.",
                           "The 988 Lifeline provides free, confidential crisis support.", resource)
        if any(term in lowered for term in sensitive_terms):
            return _notice(
                "Editorial Notice",
                "Some stories are too important for commercial sponsorship.",
                "To maintain appropriate context, Treasure Coast Today does not display paid advertising alongside certain sensitive news coverage."
            )
        return ad_html

    def _sidebar_for(current_slug, current_category):
        same = [item for item in catalog if item["slug"] != current_slug and current_category and item["category"] == current_category]
        other = [item for item in catalog if item["slug"] != current_slug and item not in same]
        chosen = (same + other)[:5]
        if not chosen:
            return (
                '<aside class="article-side-rail"><section class="related-section related-section-fallback">'
                '<h2 class="related-title">More Local News</h2>'
                '<p class="related-empty">Browse the latest reporting from across the Treasure Coast.</p>'
                '<a class="related-more-link" href="/archive.html">View the latest stories &rarr;</a>'
                '</section></aside>'
            )
        items = ''.join(
            '<li class="related-item"><a class="related-link" href="/articles/{slug}.html">'
            '<span class="related-headline">{headline}</span>'
            '<span class="related-date">{date}</span></a></li>'.format(
                slug=item["slug"], headline=_html.escape(item["headline"]), date=_html.escape(item["date"])
            ) for item in chosen
        )
        return (
            '<aside class="article-side-rail"><section class="related-section">'
            '<h2 class="related-title">More Local News</h2>'
            f'<ul class="related-list">{items}</ul>'
            '<a class="related-more-link" href="/archive.html">View all latest stories &rarr;</a>'
            '</section></aside>'
        )

    def _replace_banner(raw, desired):
        # Replace either commercial <a> or editorial/resource <section> banner.
        patterns = (
            r'<a\b[^>]*class="[^"]*article-banner-slot[^"]*"[^>]*>.*?</a>',
            r'<section\b[^>]*class="[^"]*article-banner-slot[^"]*"[^>]*>.*?</section>',
        )
        for pattern in patterns:
            if re.search(pattern, raw, re.I | re.S):
                return re.sub(pattern, desired, raw, count=1, flags=re.I | re.S), True
        return raw.replace('<div class="article-meta">', desired + '\n      <div class="article-meta">', 1), True

    critical_banner_css = r"""
<style id="tct-banner-critical">
.article-wrap>.article-banner-slot{width:min(100%,970px)!important;margin:0 auto 30px!important}
.article-wrap>.article-ad-banner{display:block!important;height:auto!important;max-height:none!important;aspect-ratio:auto!important;border:0!important;border-radius:0!important;background:transparent!important;overflow:visible!important;box-shadow:none!important}
.article-wrap>.article-ad-banner img{display:block!important;width:100%!important;height:auto!important;max-height:none!important;object-fit:contain!important;border-radius:10px!important}
.article-wrap>.article-house-banner{position:relative!important;display:grid!important;grid-template-columns:auto minmax(0,1fr) auto!important;align-items:center!important;gap:clamp(16px,3vw,32px)!important;aspect-ratio:970/250!important;max-height:250px!important;padding:clamp(20px,3vw,34px)!important;overflow:hidden!important;border:1px solid #dfe5e1!important;border-top:4px solid #087075!important;border-radius:12px!important;background:linear-gradient(115deg,#f8fbfa 0%,#fff 68%)!important;box-shadow:0 8px 26px rgba(9,15,15,.05)!important}
.article-house-mark{width:clamp(54px,7vw,78px)!important;aspect-ratio:1!important;display:grid!important;place-items:center!important;border-radius:50%!important;background:#087075!important;color:#fff!important;font-family:Georgia,serif!important;font-size:clamp(18px,2.4vw,25px)!important;font-weight:700!important}
.article-house-copy{min-width:0!important;display:grid!important;gap:5px!important}
.article-house-label{width:max-content!important;padding:3px 8px!important;border-radius:999px!important;background:rgba(8,112,117,.10)!important;color:#087075!important;font-size:9px!important;font-weight:800!important;letter-spacing:.11em!important;text-transform:uppercase!important}
.article-house-headline{display:block!important;color:#0b1210!important;font-family:Georgia,serif!important;font-size:clamp(19px,2.4vw,29px)!important;line-height:1.12!important}
.article-house-text{display:block!important;max-width:650px!important;color:#5f6863!important;font-size:clamp(11px,1.3vw,14px)!important;line-height:1.45!important}
.article-house-resource{display:grid!important;min-width:205px!important;max-width:260px!important;padding:13px 15px!important;border:1px solid rgba(8,112,117,.22)!important;border-radius:10px!important;background:rgba(255,255,255,.82)!important;color:#0b1210!important;text-decoration:none!important}
@media(max-width:800px){.article-wrap>.article-banner-slot{margin-bottom:22px!important}.article-wrap>.article-house-banner{display:block!important;aspect-ratio:auto!important;min-height:0!important;max-height:none!important;height:auto!important;padding:16px 17px 17px!important;overflow:visible!important}.article-house-mark{display:none!important}.article-house-copy{display:block!important;width:100%!important;gap:0!important}.article-house-label{display:inline-block!important;margin:0 0 8px!important}.article-house-headline{display:block!important;margin:0 0 7px!important;font-size:clamp(17px,4.8vw,21px)!important;line-height:1.1!important;-webkit-line-clamp:unset!important;line-clamp:unset!important;-webkit-box-orient:initial!important;overflow:visible!important;white-space:normal!important;text-overflow:clip!important;text-wrap:wrap!important}.article-house-text{display:block!important;margin:0!important;max-width:none!important;font-size:clamp(11px,3.1vw,13px)!important;line-height:1.4!important}.article-house-resource{display:block!important;margin:11px 0 0!important;min-width:0!important;max-width:none!important;padding:9px 10px!important}}
</style>
"""

    article_runtime_css = r"""
<style id="tct-article-runtime-critical">
.article-reading-progress{position:fixed!important;top:0!important;left:0!important;z-index:10000!important;width:0;height:3px!important;background:#087075!important;pointer-events:none!important;transition:width 70ms linear!important}
</style>
"""

    article_runtime_script = r"""
<script id="tct-article-runtime">
(function(){
  'use strict';
  function updateProgress(){
    var bar=document.querySelector('.article-reading-progress');
    if(!bar)return;
    var doc=document.documentElement;
    var body=document.body;
    var scrollTop=window.pageYOffset||doc.scrollTop||(body&&body.scrollTop)||0;
    var scrollHeight=Math.max(doc.scrollHeight,body?body.scrollHeight:0);
    var viewport=window.innerHeight||doc.clientHeight||0;
    var max=Math.max(0,scrollHeight-viewport);
    var pct=max>0?Math.min(100,Math.max(0,(scrollTop/max)*100)):0;
    bar.style.width=pct+'%';
  }

  var timeEl=document.getElementById('tct-live-time');
  var weatherEl=document.getElementById('tct-live-weather');
  var iconEl=document.getElementById('tct-weather-icon');
  var tempEl=document.getElementById('tct-weather-temp');
  var conditionEl=document.getElementById('tct-weather-condition');

  function updateClock(){
    if(!timeEl)return;
    try{
      var now=new Date();
      var datePart=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short',month:'short',day:'numeric'}).format(now);
      var timePart=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit',hour12:true,timeZoneName:'short'}).format(now);
      timeEl.textContent=datePart+' · '+timePart;
      timeEl.dateTime=now.toISOString();
    }catch(e){
      timeEl.textContent='Treasure Coast time';
    }
  }

  var codes={0:['☀','Clear'],1:['🌤','Mostly clear'],2:['⛅','Partly cloudy'],3:['☁','Cloudy'],45:['🌫','Fog'],48:['🌫','Fog'],51:['🌦','Light drizzle'],53:['🌦','Drizzle'],55:['🌧','Heavy drizzle'],61:['🌦','Light rain'],63:['🌧','Rain'],65:['🌧','Heavy rain'],80:['🌦','Rain showers'],81:['🌧','Rain showers'],82:['⛈','Heavy showers'],95:['⛈','Thunderstorms'],96:['⛈','Storms with hail'],99:['⛈','Storms with hail']};
  function paintWeather(d){
    if(!d||typeof d.temperature!=='number'||!weatherEl)return;
    var pair=codes[d.code]||['◌','Local weather'];
    if(iconEl)iconEl.textContent=pair[0];
    if(tempEl)tempEl.textContent=Math.round(d.temperature)+'°';
    if(conditionEl)conditionEl.textContent=pair[1];
    weatherEl.title='Treasure Coast: '+Math.round(d.temperature)+'°F, '+pair[1];
  }
  async function updateWeather(){
    if(!weatherEl)return;
    var key='tct-weather-v1',age=20*60*1000;
    try{
      var cached=JSON.parse(localStorage.getItem(key)||'null');
      if(cached&&Date.now()-cached.savedAt<age){paintWeather(cached);return;}
    }catch(e){}
    try{
      var response=await fetch('https://api.open-meteo.com/v1/forecast?latitude=27.1975&longitude=-80.2528&current=temperature_2m,weather_code&temperature_unit=fahrenheit&timezone=America%2FNew_York',{cache:'no-store'});
      if(!response.ok)throw new Error('weather request failed');
      var json=await response.json();
      var data={temperature:json.current&&json.current.temperature_2m,code:json.current&&json.current.weather_code,savedAt:Date.now()};
      paintWeather(data);
      try{localStorage.setItem(key,JSON.stringify(data));}catch(e){}
    }catch(e){
      if(conditionEl)conditionEl.textContent='Local weather';
    }
  }

  function start(){
    updateProgress();
    updateClock();
    updateWeather();
    window.addEventListener('scroll',updateProgress,{passive:true});
    window.addEventListener('resize',updateProgress);
    window.addEventListener('load',updateProgress);
    setInterval(updateClock,30000);
    setInterval(updateWeather,20*60*1000);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});
  else start();
})();
</script>
"""

    def _ensure_article_runtime(raw):
        """Install one canonical runtime on every retained article page."""
        changed = False
        css_pattern = r'<style\s+id=["\']tct-article-runtime-critical["\'][^>]*>.*?</style>'
        if re.search(css_pattern, raw, re.I | re.S):
            updated = re.sub(css_pattern, article_runtime_css.strip(), raw, count=1, flags=re.I | re.S)
            changed = changed or updated != raw
            raw = updated
        elif '</head>' in raw:
            raw = raw.replace('</head>', article_runtime_css + '\n</head>', 1)
            changed = True

        script_pattern = r'<script\s+id=["\']tct-article-runtime["\'][^>]*>.*?</script>'
        if re.search(script_pattern, raw, re.I | re.S):
            updated = re.sub(script_pattern, article_runtime_script.strip(), raw, count=1, flags=re.I | re.S)
            changed = changed or updated != raw
            raw = updated
        elif '</body>' in raw:
            raw = raw.replace('</body>', article_runtime_script + '\n</body>', 1)
            changed = True
        return raw, changed

    def _category_key(label):
        normalized = re.sub(r"[^a-z0-9]+", " ", (label or "").lower()).strip()
        aliases = {
            "top news": "news", "news": "news",
            "local government": "local_gov",
            "crime safety": "crime", "crime and safety": "crime",
            "business development": "business", "business and development": "business",
            "sports": "sports", "things to do": "things_to_do", "florida": "florida",
            "martin county": "martin", "st lucie county": "st_lucie",
            "saint lucie county": "st_lucie", "indian river county": "indian_river",
        }
        return aliases.get(normalized, "")

    def _canonical_article_prefix(active_key):
        newsroom = """<div class="newsroom-strip">
    <div class="newsroom-strip-inner">
      <span class="newsroom-local-label">Local news for Martin, St. Lucie &amp; Indian River counties</span>
      <div class="newsroom-live-tools" aria-label="Current Treasure Coast time and weather">
        <time id="tct-live-time" class="newsroom-live-time" datetime=""></time>
        <a id="tct-live-weather" class="newsroom-live-weather" href="/weather.html" aria-label="View local weather">
          <span id="tct-weather-icon" class="newsroom-weather-icon" aria-hidden="true">◌</span>
          <span id="tct-weather-temp">--°</span>
          <span id="tct-weather-condition">Local weather</span>
        </a>
      </div>
    </div>
  </div>"""
        return (
            '<div class="article-reading-progress" aria-hidden="true"></div>\n'
            + _page_header(active=active_key) + '\n  ' + newsroom + '\n  '
        )

    def _normalize_article_header(raw, category_label):
        """Replace every retained article header with the canonical site header.

        Banner choice only changes the banner contents. It must never preserve or
        select an older masthead for sensitive stories.
        """
        body_match = re.search(r'<body[^>]*>', raw, re.I)
        main_match = re.search(r'<main\b', raw, re.I)
        if not body_match or not main_match or main_match.start() <= body_match.end():
            return raw, False
        prefix = _canonical_article_prefix(_category_key(category_label))
        replacement = body_match.group(0) + '\n  ' + prefix + '<main'
        updated = raw[:body_match.start()] + replacement + raw[main_match.end():]
        return updated, updated != raw

    checked = repaired = wrapped = unrepairable = header_normalized = 0
    for path in articles_dir.glob("*.html"):
        html = path.read_text(encoding="utf-8", errors="ignore")
        if 'http-equiv="refresh"' in html or "window.location.replace" in html:
            continue
        checked += 1
        if 'class="article-wrap"' not in html or 'class="article-meta"' not in html:
            continue

        changed = False
        headline = _extract(r'<h1[^>]*>(.*?)</h1>', html)
        category = _extract(r'class="article-category"[^>]*>(.*?)</', html)
        body_excerpt = _extract(r'class="article-body"[^>]*>(.*?)</div>', html)

        # Normalize the shell before changing the banner. This removes the legacy
        # text-only masthead from retained articles, including sensitive stories.
        html, header_changed = _normalize_article_header(html, category)
        if header_changed:
            changed = True
            header_normalized += 1
        critical_style_pattern = r'<style\s+id=["\']tct-banner-critical["\'][^>]*>.*?</style>'
        if re.search(critical_style_pattern, html, re.I | re.S):
            updated_html = re.sub(critical_style_pattern, critical_banner_css.strip(), html, count=1, flags=re.I | re.S)
            if updated_html != html:
                html = updated_html
                changed = True
        else:
            html = html.replace('</head>', critical_banner_css + '\n</head>', 1)
            changed = True

        html, runtime_changed = _ensure_article_runtime(html)
        changed = changed or runtime_changed

        desired_banner = _banner_for((headline + " " + body_excerpt[:1200]).strip())
        html, banner_changed = _replace_banner(html, desired_banner)
        changed = changed or banner_changed

        desired_sidebar = _sidebar_for(path.stem, category)

        if 'class="article-editorial-grid"' not in html:
            body_candidates = [html.find('<figure class="article-hero-image">'), html.find('<div class="article-body">')]
            body_candidates = [position for position in body_candidates if position >= 0]
            body_start = min(body_candidates) if body_candidates else -1
            end_match = re.search(r'\n\s*<a href="/\?cat=[^"]+"[^>]*class="article-(?:back|more-link)"', html[body_start:] if body_start >= 0 else '')
            if body_start >= 0 and end_match:
                body_end = body_start + end_match.start()
                original_body = html[body_start:body_end]
                replacement = (
                    '<div class="article-editorial-grid">\n'
                    '        <div class="article-main-column">\n' + original_body + '\n        </div>\n'
                    '        ' + desired_sidebar + '\n      </div>'
                )
                html = html[:body_start] + replacement + html[body_end:]
                changed = True
                wrapped += 1
            else:
                unrepairable += 1
        else:
            # Replace an existing rail, including an empty fallback, with populated current links.
            rail_pattern = r'<aside\b[^>]*class="[^"]*article-side-rail[^"]*"[^>]*>.*?</aside>'
            if re.search(rail_pattern, html, re.I | re.S):
                html = re.sub(rail_pattern, desired_sidebar, html, count=1, flags=re.I | re.S)
                changed = True
            else:
                link_match = re.search(r'\n\s*<a href="/\?cat=[^"]+"[^>]*class="article-(?:back|more-link)"', html)
                if link_match:
                    prefix = html[:link_match.start()]
                    close_at = prefix.rfind('</div>')
                    if close_at >= 0:
                        html = html[:close_at] + desired_sidebar + '\n      ' + html[close_at:]
                        changed = True
                    else:
                        unrepairable += 1
                else:
                    unrepairable += 1

        if changed:
            path.write_text(html, encoding="utf-8")
            repaired += 1

    print(
        f"  Article shell repair: checked {checked}, repaired {repaired}, "
        f"headers normalized {header_normalized}, legacy grids wrapped {wrapped}, "
        f"unrepairable {unrepairable}"
    )
    return {"checked": checked, "repaired": repaired, "wrapped": wrapped,
            "header_normalized": header_normalized, "unrepairable": unrepairable}

def _validate_presentation_contract(output_root):
    """Validate current presentation without blocking an urgent deploy on old archives.

    Homepage regressions remain fatal. Retained article files that cannot be upgraded are
    recorded as warnings so a single old URL cannot prevent the entire site from publishing.
    """
    root = Path(output_root)
    fatal = []
    warnings = []
    index_path = root / "index.html"
    if not index_path.exists():
        fatal.append("index.html missing")
    else:
        index = index_path.read_text(encoding="utf-8", errors="ignore")
        for token in ('hero-v3-link', 'hero-v3-media', 'hero-v3-content', 'latest-rail'):
            if token not in index:
                fatal.append(f"homepage missing {token}")

    article_count = valid_article_count = 0
    for path in (root / "articles").glob("*.html") if (root / "articles").exists() else []:
        html = path.read_text(encoding="utf-8", errors="ignore")
        if 'http-equiv="refresh"' in html or 'window.location.replace' in html:
            continue
        if 'class="article-wrap"' not in html:
            continue
        article_count += 1
        missing = [t for t in ('article-banner-slot', 'article-editorial-grid', 'article-side-rail') if t not in html]
        if missing:
            warnings.append(f"{path.name} missing {', '.join(missing)}")
        else:
            valid_article_count += 1

    # A broad renderer failure is still fatal. A small number of preserved legacy pages
    # is reported but does not stop the morning deployment.
    if article_count and valid_article_count == 0:
        fatal.append("no article pages satisfy the current presentation contract")

    report = {
        "version": TCT_PRESENTATION_VERSION,
        "passed": not fatal,
        "fatal_failures": fatal,
        "warnings": warnings[:250],
        "article_pages_checked": article_count,
        "article_pages_valid": valid_article_count,
    }
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "presentation-contract.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if fatal:
        raise RuntimeError("Presentation contract failed: " + "; ".join(fatal[:8]))
    if warnings:
        print(f"  Presentation contract PASSED with {len(warnings)} legacy warning(s); see data/presentation-contract.json")
    else:
        print("  Presentation contract PASSED")


def _plain_article_body_from_html(path):
    """Recover the readable body from an already-published canonical page."""
    try:
        raw = Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    match = re.search(r'<div[^>]+class=["\']article-body["\'][^>]*>(.*?)</div>', raw, re.I | re.S)
    if not match:
        return ""
    fragment = match.group(1)
    paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', fragment, re.I | re.S)
    if not paragraphs:
        paragraphs = [fragment]
    import html as _html
    cleaned = []
    for paragraph in paragraphs:
        text = re.sub(r'<[^>]+>', ' ', paragraph)
        text = _html.unescape(re.sub(r'\s+', ' ', text)).strip()
        if text:
            cleaned.append(text)
    return "\n\n".join(cleaned)


def _canonical_body_quality_issues(body):
    """Return structural problems that make a canonical article unsafe to publish.

    Canonical articles must read as one complete story. Repeated versions, appended
    update blocks, related-angle markers, and near-duplicate paragraphs are rejected.
    """
    import difflib

    body = (body or "").strip()
    issues = []
    if not body:
        return ["empty body"]

    lowered = body.lower()
    forbidden = (
        "earlier coverage:",
        "<!-- related-angle:",
        "updated coverage:",
        "previously reported:",
    )
    for marker in forbidden:
        if marker in lowered:
            issues.append(f"append marker present: {marker}")

    paragraphs = [re.sub(r"\s+", " ", p).strip()
                  for p in re.split(r"\n\s*\n+", body) if p.strip()]
    if len(paragraphs) < 2:
        issues.append("fewer than two paragraphs")

    # Detect exact and near-duplicate paragraphs. This catches stacked rewrites even
    # when each generation changes a few words.
    normalized = [re.sub(r"[^a-z0-9 ]+", " ", p.lower()) for p in paragraphs]
    normalized = [re.sub(r"\s+", " ", p).strip() for p in normalized]
    for i in range(len(normalized)):
        if len(normalized[i].split()) < 12:
            continue
        for j in range(i + 1, len(normalized)):
            if len(normalized[j].split()) < 12:
                continue
            ratio = difflib.SequenceMatcher(None, normalized[i], normalized[j]).ratio()
            if ratio >= 0.76:
                issues.append(f"near-duplicate paragraphs {i+1} and {j+1} ({ratio:.2f})")

    # Repeated long sentences are another strong sign that multiple full versions were
    # appended together.
    sentences = [re.sub(r"\s+", " ", s).strip()
                 for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
    sentence_norm = [re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip() for s in sentences]
    for i in range(len(sentence_norm)):
        if len(sentence_norm[i].split()) < 10:
            continue
        for j in range(i + 1, len(sentence_norm)):
            if len(sentence_norm[j].split()) < 10:
                continue
            ratio = difflib.SequenceMatcher(None, sentence_norm[i], sentence_norm[j]).ratio()
            if ratio >= 0.88:
                issues.append(f"repeated sentence {i+1}/{j+1} ({ratio:.2f})")

    return issues


def _evolve_canonical_body(hero, existing, article_path):
    """Create one complete replacement article for an existing canonical URL.

    No article text is ever appended. The previous canonical and the incoming report
    are treated only as source material for a fresh, unified rewrite. If the rewrite
    fails structural validation, the build stops rather than publishing a duplicated
    or Frankenstein article.
    """
    new_body = (hero.get("body") or "").strip()
    old_body = (existing.get("body") or "").strip()
    if not old_body:
        old_body = _plain_article_body_from_html(article_path)

    if not new_body:
        raise RuntimeError(
            f"Canonical update has no incoming body for '{hero.get('headline','')[:80]}'"
        )

    # Brand-new canonical content with no usable prior body can be used directly, but
    # it still must pass the same anti-duplication checks.
    if not old_body:
        issues = _canonical_body_quality_issues(new_body)
        if issues:
            raise RuntimeError("Canonical body validation failed: " + "; ".join(issues[:8]))
        return new_body

    prompt = (
        "Rewrite the following developing local-news story as ONE complete, coherent "
        "article. The output will fully replace the current article at its permanent "
        "canonical URL. Use the previous article and the incoming report only as source "
        "material. Incorporate the newest verified development, retain important prior "
        "context, and remove duplicated facts. Start with a self-contained lead that "
        "states what happened and the latest status; do not begin in the middle of the "
        "story. Use a logical chronology. Mention each fact, statistic, quote, and source "
        "at most once unless repetition is essential for clarity. Do not add headings, "
        "notes, labels such as 'Earlier coverage,' markdown links, or commentary about "
        "the rewrite. Do not invent facts. Return only the finished article in plain "
        "paragraphs separated by blank lines.\n\n"
        f"UPDATED HEADLINE:\n{hero.get('headline','').strip()}\n\n"
        f"PREVIOUS CANONICAL ARTICLE:\n{old_body[:12000]}\n\n"
        f"INCOMING REPORT / NEW DEVELOPMENT:\n{new_body[:12000]}\n"
    )

    rewritten = ""
    try:
        resp = client.messages.create(
            model=MODEL_SELECTION,
            max_tokens=1800,
            messages=[{"role": "user", "content": prompt}],
        )
        rewritten = strip_markdown(resp.content[0].text.strip(), hero.get("headline", ""))
        rewritten = re.sub(r"\n{3,}", "\n\n", rewritten).strip()
    except Exception as e:
        print(f"    Full canonical rewrite failed ({e}); validating incoming article as fallback")

    # A clean incoming article is the only permissible fallback. The old article is
    # never concatenated to it.
    candidate = rewritten or new_body
    issues = _canonical_body_quality_issues(candidate)
    if issues and rewritten:
        fallback_issues = _canonical_body_quality_issues(new_body)
        if not fallback_issues:
            print("    Rewritten canonical failed validation; using clean incoming article only")
            candidate = new_body
            issues = []
    if issues:
        raise RuntimeError(
            f"Canonical rewrite rejected for '{hero.get('headline','')[:80]}': "
            + "; ".join(issues[:10])
        )
    return candidate

def _verify_canonical_permalink(path, expected_headline, expected_body):
    """Fail the build when a card update and its permanent article drift apart."""
    raw = Path(path).read_text(encoding="utf-8", errors="ignore")
    escaped_headline = re.escape(expected_headline.strip())
    if not re.search(r'<h1[^>]*>\s*' + escaped_headline + r'\s*</h1>', raw, re.I | re.S):
        raise RuntimeError(f"Canonical permalink did not receive updated headline: {path}")
    body_probe = re.sub(r'\s+', ' ', (expected_body or '').strip())[:100]
    if body_probe:
        visible = re.sub(r'<[^>]+>', ' ', raw)
        visible = re.sub(r'\s+', ' ', visible)
        if body_probe.lower() not in visible.lower():
            raise RuntimeError(f"Canonical permalink did not receive updated body: {path}")




# --- V6.5.6 canonical identity safety ---------------------------------------
def _slug_identity_tokens(slug):
    """Recover the immutable topic fingerprint encoded in a published URL."""
    raw = re.sub(r"^20\d{2}-\d{2}-\d{2}-", "", str(slug or "").lower())
    raw = raw.replace("-", " ")
    return {t for t in _sig_tokens(raw) if t not in GENERIC_TOKENS}


def _headline_proper_names(text):
    """Conservatively extract two-word proper names from headline/summary text."""
    text = str(text or "")
    blocked = {
        "Florida Governor", "Treasure Coast", "St Lucie", "St. Lucie",
        "Martin County", "Indian River", "Fort Pierce", "Vero Beach",
        "Port St", "Port St.", "Leon County", "Palm Beach"
    }
    names = set()
    for first, last in re.findall(r"\b([A-Z][a-z'’-]{2,})\s+([A-Z][a-z'’-]{2,})\b", text):
        name = f"{first} {last}"
        if name not in blocked:
            names.add(name.lower())
    return names


def _published_slug_still_matches_entry(entry):
    """A published slug is an immutable identity checksum, not just a filename.

    If the current headline no longer shares the people/topic encoded in the slug, the
    archive record has already been overwritten by an unrelated story and must never
    be used as a canonical update target.
    """
    slug_tokens = _slug_identity_tokens(entry.get("slug", ""))
    headline_tokens = {t for t in _sig_tokens(entry.get("headline", "")) if t not in GENERIC_TOKENS}
    if not slug_tokens or not headline_tokens:
        return True
    shared = slug_tokens & headline_tokens
    slug_names = _headline_proper_names(str(entry.get("slug", "")).replace("-", " " ).title())
    current_names = _headline_proper_names(" ".join([entry.get("headline", ""), entry.get("teaser", "")]))
    if slug_names and current_names and not (slug_names & current_names):
        return False
    return len(shared) >= 3 or (len(shared) / max(1, min(len(slug_tokens), len(headline_tokens)))) >= 0.35


def _hard_canonical_identity_gate(item, existing):
    """Fail closed before any model is allowed to merge into a live permalink.

    A canonical update needs a stable event key, a shared named person/entity, or a
    strong combination of distinctive topic, location and action overlap. Generic
    political/legal vocabulary alone can never authorize an overwrite.
    """
    if not existing or not existing.get("slug"):
        return False
    if not _published_slug_still_matches_entry(existing):
        return False

    incoming_text = _story_text(item or {})
    existing_text = _story_text(existing or {})
    incoming_key = _known_event_key(incoming_text)
    existing_key = _known_event_key(existing_text)
    if incoming_key and existing_key:
        return incoming_key == existing_key

    incoming_names = _headline_proper_names(incoming_text)
    existing_names = _headline_proper_names(existing_text)
    if incoming_names and existing_names:
        if not (incoming_names & existing_names):
            return False
        return True

    incoming_tokens = {t for t in _sig_tokens(incoming_text) if t not in GENERIC_TOKENS}
    existing_tokens = {t for t in _sig_tokens(existing_text) if t not in GENERIC_TOKENS}
    distinctive_shared = incoming_tokens & existing_tokens
    location_overlap = bool(_audit_locations(incoming_text) & _audit_locations(existing_text))
    action_overlap = bool(_audit_action_families(incoming_text) & _audit_action_families(existing_text))
    return len(distinctive_shared) >= 6 and location_overlap and action_overlap


def _write_canonical_integrity_report(archive, data_dir):
    corrupt = []
    for entry in archive or []:
        if entry.get("slug") and not _published_slug_still_matches_entry(entry):
            corrupt.append({
                "slug": entry.get("slug"),
                "headline": entry.get("headline"),
                "source_url": entry.get("source_url", ""),
                "reason": "Current headline no longer matches immutable permalink identity",
            })
    path = Path(data_dir) / "canonical-integrity-report.json"
    path.write_text(json.dumps({
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "passed": not bool(corrupt),
        "corrupt_count": len(corrupt),
        "corrupt_entries": corrupt,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return corrupt




def _find_authoritative_custom_canonical(item, archive):
    """Return the hand-written canonical that owns this event, if one exists.

    Custom stories are immutable event anchors. Matching is deliberately stronger than
    ordinary headline similarity: exact published slug, exact custom fingerprint, and
    narrow known-event keys are checked before any feed story may create a new URL.
    """
    item = item or {}
    incoming_slug = slugify(str(item.get("slug") or "")) if item.get("slug") else ""
    incoming_text = " ".join([
        item.get("headline", ""), item.get("teaser", ""), item.get("body", "")[:1200]
    ])
    incoming_key = _known_event_key(incoming_text)
    incoming_fp = _custom_story_fingerprint(
        item.get("headline", ""), item.get("teaser", "") or item.get("body", "")[:180]
    )

    candidates = []
    for entry in archive or []:
        if not (entry.get("is_custom") or entry.get("authoritative_custom")):
            continue
        score = 0
        if incoming_slug and incoming_slug == entry.get("slug"):
            score += 100
        if incoming_fp and incoming_fp == entry.get("custom_fingerprint"):
            score += 90
        entry_key = entry.get("custom_event_key") or _known_event_key(" ".join([
            entry.get("headline", ""), entry.get("teaser", ""), entry.get("body", "")[:1200]
        ]))
        if incoming_key and entry_key and incoming_key == entry_key:
            score += 80
        if _same_event_text(incoming_text, " ".join([
            entry.get("headline", ""), entry.get("teaser", ""), entry.get("body", "")[:1200]
        ])):
            score += 30
        if score:
            candidates.append((score, int(entry.get("article_word_count", 0) or 0), entry))
    if not candidates:
        return None
    candidates.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return candidates[0][2]


def _atomic_write_verified_article(path, html, expected_headline, expected_body):
    """Stage, verify, and atomically commit one article page.

    A permalink is never exposed to homepage/RSS generation until its complete HTML
    has been written and verified. Any failure leaves the previously published file
    untouched.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(path.name + ".staged")
    try:
        staged.write_text(html, encoding="utf-8")
        _verify_canonical_permalink(staged, expected_headline, expected_body)
        os.replace(staged, path)
    finally:
        if staged.exists():
            staged.unlink()
    if not path.exists() or path.stat().st_size < 500:
        raise RuntimeError(f"Atomic article commit failed: {path}")


def _assert_presentation_targets_exist(all_categories, top_cat, archive, articles_dir):
    """Fail closed if any rendered hero/card points at a missing article file.

    Before failing, try one safe repair: resolve the item back to an authoritative
    custom canonical or another verified archive canonical and hydrate it atomically.
    """
    failures = []
    items = [top_cat.get("hero")]
    for cat in all_categories:
        items.extend([cat.get("hero")] + list(cat.get("cards", [])))
    for item in items:
        if not item or item.get("_section_placeholder"):
            continue
        slug = item.get("_archived_slug") or item.get("slug")
        if not slug:
            canonical = _find_authoritative_custom_canonical(item, archive) or find_presentation_canonical(item, archive)
            if canonical:
                _hydrate_presentation_item(item, canonical)
                slug = canonical.get("slug")
        path = Path(articles_dir) / f"{slug}.html" if slug else None
        if not path or not path.exists():
            canonical = _find_authoritative_custom_canonical(item, archive) or find_presentation_canonical(item, archive)
            if canonical:
                candidate = Path(articles_dir) / f"{canonical.get('slug','')}.html"
                if candidate.exists():
                    _hydrate_presentation_item(item, canonical)
                    continue
            failures.append({"headline": item.get("headline", ""), "slug": slug or ""})
    if failures:
        raise RuntimeError(
            "Presentation publish aborted because permalink target(s) are missing: "
            + json.dumps(failures[:10], ensure_ascii=False)
        )

def write_archives(all_categories, top_cat):
    articles_dir = OUTPUT_DIR / "articles"
    archive_path = OUTPUT_DIR / "archive.json"
    articles_dir.mkdir(exist_ok=True)

    archive       = _sanitize_authoritative_custom_archive(
        load_archive(archive_path), articles_dir
    )
    today         = datetime.utcnow().strftime("%Y-%m-%d")
    new_count     = 0
    updated_count = 0
    this_run_token_sets = []

    # Canonical cleanup is handled below. Never unlink an already-published
    # duplicate URL: it is retained as a redirect destination so readers and search
    # engines do not encounter a 404.

    # BACKFILL is_custom on existing archive entries. The flag was added later, so
    # custom articles archived before then have no flag and would not be protected.
    # Match each currently-loaded custom article to its archive entry (by fuzzy
    # headline) and stamp the flag, so the protection guard below reliably fires even
    # for custom articles first published before the flag existed.
    try:
        _current_customs = load_custom_articles()
    except Exception:
        _current_customs = []
    if _current_customs:
        for _c in _current_customs:
            _ctok = _sig_tokens(_c.get("headline", ""))
            _matches = [e for e in archive if _same_story(_ctok, _sig_tokens(e.get("headline", "")))]
            if not _matches:
                continue
            _custom_headline = (_c.get("headline") or "").strip().lower()
            # Mark exactly one archive record authoritative: exact headline first,
            # then strongest token overlap/content depth. Never stamp every duplicate.
            def _custom_archive_rank(e):
                _headline = (e.get("headline") or "").strip().lower()
                _exact = 1 if _headline == _custom_headline else 0
                _overlap = len(_ctok & _sig_tokens(e.get("headline", "")))
                _words = int(e.get("article_word_count", 0) or 0)
                return (_exact, _overlap, _words)
            _entry = max(_matches, key=_custom_archive_rank)
            _entry["is_custom"] = True
            _entry["authoritative_custom"] = True
            _entry["custom_fingerprint"] = _custom_story_fingerprint(
                _c.get("headline", ""), _c.get("teaser", "") or _c.get("body", "")[:180]
            )
            _entry["custom_event_key"] = _known_event_key(
                " ".join([_c.get("headline", ""), _c.get("teaser", ""), _c.get("body", "")[:500]])
            )

    archive, _canonical_redirects = apply_canonical_story_cleanup(archive, articles_dir, OUTPUT_DIR)
    _integrity_dir = OUTPUT_DIR / "data"
    _integrity_dir.mkdir(parents=True, exist_ok=True)
    _corrupt_canonicals = _write_canonical_integrity_report(archive, _integrity_dir)
    if _corrupt_canonicals:
        print(f"  CRITICAL: {len(_corrupt_canonicals)} canonical permalink(s) already show identity drift; they are quarantined from all future overwrites. See data/canonical-integrity-report.json")

    heroes = [(top_cat["category_key"], top_cat["category_label"], top_cat["hero"])]
    for cat in all_categories:
        if cat["category_key"] != top_cat["category_key"]:
            heroes.append((cat["category_key"], cat["category_label"], cat["hero"]))

    # Also generate article pages for every card, since the homepage grid links
    # to permalink pages for all articles, not just heroes.
    all_articles = list(heroes)

    # Every active manually submitted article must be rendered through the current
    # article template, even when it is not selected as a hero or grid card during
    # this particular run. Previously, only selected articles were rewritten. That
    # left older custom pages on the legacy template, where the advertisement banner
    # appeared above the headline and the newsroom strip/sidebar were missing.
    # Adding all active custom articles here unifies ad and non-ad article layouts.
    for _custom_article in _current_customs:
        _custom_key = _custom_article.get("category", "top_news")
        _custom_cfg = CATEGORIES.get(_custom_key, {})
        _custom_label = _custom_cfg.get("label", _custom_key.replace("_", " ").title())
        all_articles.append((_custom_key, _custom_label, _custom_article))

    for cat in all_categories:
        for card in cat.get("cards", []):
            # Only archive cards that were actually enriched. Thin unenriched cards
            # (just a rehashed headline) don't get permalink pages, archive entries, or RSS.
            if not card.get("enriched"):
                continue
            all_articles.append((cat["category_key"], cat["category_label"], card))

    # A story classified into multiple categories (e.g. a Hobe Sound business opening
    # is both Business and Martin County) appears once per category in all_articles,
    # each writing to the SAME slug. Whichever is processed last wins — which meant the
    # later category could overwrite a good page with its own version that lacked the
    # real image and carried the wrong category label. Deduplicate by slug, keeping the
    # BEST copy: prefer one with a real (non-fallback) image, then the hero over a card.
    def _slug_key(headline):
        return re.sub(r"[^a-z0-9 ]", "", (headline or "").lower()).strip()[:60]

    def _copy_rank(entry):
        _ck, _cl, item = entry
        has_real_img = 1 if (item.get("image_url") and not item.get("image_from_google")) else 0
        is_hero_copy = 1 if item.get("_is_hero_copy") else 0
        return (has_real_img, is_hero_copy)

    # Tag hero copies so the ranker can prefer them
    for _ck, _cl, _item in heroes:
        _item["_is_hero_copy"] = True

    _best_by_slug = {}
    for entry in all_articles:
        k = _slug_key(entry[2].get("headline", ""))
        if not k:
            continue
        if k not in _best_by_slug or _copy_rank(entry) > _copy_rank(_best_by_slug[k]):
            _best_by_slug[k] = entry
    all_articles = list(_best_by_slug.values())

    for cat_key, cat_label, hero in all_articles:
        # Archive recovery items already have permanent article pages. They are reused
        # for section continuity only and must not rewrite/degrade those pages from a
        # short archive teaser.
        if hero.get("_archive_only") or hero.get("_section_placeholder"):
            continue
        headline = hero.get("headline", "").strip()
        if not headline:
            continue
        if not _publishable_article(hero, hero=bool(hero.get("_is_hero_copy"))):
            print(f"  Skipped thin article before permalink creation: {headline[:60]}")
            continue

        source_url = hero.get("link", "")
        # Custom canonicals own their event before ordinary fuzzy/semantic matching.
        # This catches syndicated headline rewrites such as the July 2026 St. Lucie
        # firefighter hazing story and guarantees the hand-written URL always wins.
        _authoritative_custom = _find_authoritative_custom_canonical(hero, archive)
        existing = _authoritative_custom or find_canonical_event_entry(hero, archive)
        if _authoritative_custom and not hero.get("is_custom"):
            print(f"  CUSTOM CANONICAL PREEMPTION: '{headline[:55]}' -> '{existing.get('slug','')}'")
        _relationship = "SAME_EVENT" if existing else "DISTINCT"
        _related_canonical = None

        # OVERRIDE for recurring series (weekly traffic reports, roundups, game recaps).
        # These share a title prefix and vocabulary, so the matcher treats each new
        # edition as an update of the last and OVERWRITES the previous permalink. A
        # custom article can opt out:
        #   "unique_slug": true      -> always create a fresh permalink this run, never
        #                               overwrite a previous edition
        #   "slug": "my-custom-slug" -> use this exact slug (also implies unique)
        # Both only apply to custom articles.
        _forced_slug = None
        if hero.get("is_custom"):
            if hero.get("slug"):
                _forced_slug = slugify(str(hero["slug"]))
                existing = None
            elif hero.get("unique_slug"):
                existing = None

        # CLASSIFY EVENT IDENTITY BEFORE ANY OVERWRITE OR CUSTOM-story suppression.
        # A topical or human-interest angle may be related to a canonical article but
        # must receive its own permalink. Only SAME_EVENT may evolve an existing URL.
        if existing and not hero.get("is_weather_alert"):
            if not _hard_canonical_identity_gate(hero, existing):
                print(f"  CANONICAL OVERWRITE BLOCKED: '{headline[:55]}' does not match immutable URL '{existing.get('slug','')}'")
                existing = None
                _relationship = "DISTINCT"
            elif existing.get("headline", "").strip().lower() != headline.strip().lower():
                _relationship = classify_story_relationship(hero, existing)
                if _relationship == "RELATED_ANGLE":
                    _related_canonical = existing
                    existing = None
                    hero["related_canonical_slug"] = _related_canonical.get("slug", "")
                    print(f"  RELATED ANGLE: preserving separate permalink for '{headline[:55]}'")
                elif _relationship != "SAME_EVENT":
                    existing = None

        # Hand-written custom coverage is the authoritative canonical anchor. A feed
        # item may never create a second URL for the same event. Non-significant
        # duplicates are hydrated back to the custom record so hero/cards/Latest News
        # all point to the existing live page. A truly significant milestone may
        # rewrite the complete article at that same custom permalink.
        if existing and existing.get("is_custom") and not hero.get("is_custom"):
            if not _is_significant_story_update(hero, existing):
                _hydrate_presentation_item(hero, existing)
                print(f"  PROTECTED CUSTOM CANONICAL: ignored duplicate '{headline[:45]}' and restored "
                      f"'{existing.get('slug','')}' everywhere")
                continue
            print(f"  SIGNIFICANT CUSTOM UPDATE: rewriting authoritative permalink '{existing.get('slug','')}'")

        # FRESHNESS LOCK: a source may republish an old development with a new RSS
        # timestamp or slightly changed wording. When the deterministic matcher points
        # to an existing canonical article and the editorial milestone has not changed,
        # leave the canonical HTML and metadata untouched. This prevents an old story
        # from receiving today's lastmod and resurfacing as the homepage hero.
        if existing and not hero.get("is_custom") and _same_published_milestone(hero, existing):
            _hydrate_presentation_item(hero, existing)
            print(f"  REPUBLICATION: keeping canonical freshness for '{existing.get('headline','')[:55]}'")
            continue

        # Skip cross-category duplicates within the same run
        if not existing and _is_duplicate_headline(headline, this_run_token_sets):
            print(f"  Skipped cross-category duplicate: {headline[:60]}")
            continue

        this_run_token_sets.append(_sig_tokens(headline))

        # HARD SIGNIFICANCE GATE: identifying the same event is necessary but not
        # sufficient to modify its canonical article. Routine follow-ups, duplicate
        # reports, extra quotes, wording changes, and non-material details leave the
        # canonical page, headline, teaser, timestamp, cards, hero, Latest News and RSS
        # completely untouched. Only a major new milestone reaches the full-rewrite path.
        if existing and not hero.get("is_custom"):
            _significant_update = _is_significant_story_update(hero, existing)
            if not _significant_update:
                _hydrate_presentation_item(hero, existing)
                print(f"  NON-SIGNIFICANT FOLLOW-UP: canonical unchanged for '{existing.get('headline','')[:55]}'")
                continue

        if existing:
            # Same event + significant development — rewrite the existing canonical
            # article in full while retaining its permanent URL.
            slug = existing["slug"]
            hero["first_published"] = existing.get("first_published") or existing.get("date", "")

            _significant_update = _is_significant_story_update(hero, existing)
            _prior_for_update = dict(existing)
            if not _significant_update:
                # Custom/manual rewrites are allowed only when explicitly supplied as
                # custom content; automated feed updates have already been blocked above.
                if not hero.get("is_custom"):
                    raise RuntimeError("Non-significant update reached canonical rewrite path")
            _article_path = articles_dir / f"{slug}.html"

            # Compare complete reader-visible canonical payloads, not workflow metadata.
            # For older archive rows without content_hash, derive a baseline from their
            # stored canonical fields without falsely marking them updated.
            _old_content_hash = existing.get("content_hash") or _canonical_content_hash(
                existing.get("headline", ""), existing.get("teaser", ""),
                existing.get("body", ""), existing.get("image_url", "")
            )

            # Rebuild the canonical document as one complete replacement article.
            # Previous and incoming reporting are source material only; nothing is appended.
            hero["body"] = _evolve_canonical_body(hero, existing, _article_path)
            hero["teaser"] = hero.get("teaser", "") or hero.get("body", "")[:180]
            _final_image_url = hero.get("image_url","") or existing.get("image_url", "")
            _new_content_hash = _canonical_content_hash(
                headline, hero.get("teaser", ""), hero.get("body", ""), _final_image_url
            )
            _content_changed = _new_content_hash != _old_content_hash

            existing["headline"]  = headline
            existing["teaser"]    = hero.get("teaser", "")
            existing["body"]      = hero.get("body", "")
            existing["image_url"] = _final_image_url
            existing["content_hash"] = _new_content_hash
            if not hero.get("image_url") and existing.get("image_url"):
                hero["image_url"] = existing.get("image_url")
            existing["article_word_count"] = _word_count(hero.get("body", ""))
            existing["article_paragraph_count"] = _paragraph_count(hero.get("body", ""))
            if hero.get("event_url"):
                existing["event_url"] = hero.get("event_url")
                existing["event_link_text"] = hero.get("event_link_text", "")
            # Advance the public update timestamp only when reader-visible canonical
            # content actually changed. This value is never touched by a routine run.
            if _content_changed:
                _editorial_update_now = _now_eastern_rfc822()
                existing["editorial_updated_at"] = _editorial_update_now
                existing["lastmod"] = today
                hero["editorial_updated_at"] = _editorial_update_now
            elif existing.get("editorial_updated_at"):
                hero["editorial_updated_at"] = existing.get("editorial_updated_at")
            if _significant_update:
                existing["significant_update_at"] = _now_eastern_rfc822()
                existing["significant_update_reason"] = ", ".join(sorted(
                    _material_update_stages(" ".join([
                        hero.get("headline", ""), hero.get("teaser", ""), hero.get("body", "")[:1200]
                    ])) - _material_update_stages(" ".join([
                        _prior_for_update.get("headline", ""), _prior_for_update.get("teaser", ""), _prior_for_update.get("body", "")[:1200]
                    ]))
                )) or "major milestone"
                existing["freshness_boost_ratio"] = SIGNIFICANT_UPDATE_BOOST_RATIO
                existing["freshness_boost_hours"] = SIGNIFICANT_UPDATE_BOOST_HOURS
                print(f"  SIGNIFICANT UPDATE BOOST: '{headline[:55]}' for {SIGNIFICANT_UPDATE_BOOST_HOURS}h")

            # Render only after all canonical metadata has been advanced, then verify
            # the permanent page contains the same headline and body shown on cards.
            hero["first_published"] = existing.get("first_published") or existing.get("date", "")
            hero["lastmod"] = existing.get("lastmod", today)
            if existing.get("significant_update_at"):
                hero["significant_update_at"] = existing.get("significant_update_at")
            if existing.get("editorial_updated_at"):
                hero["editorial_updated_at"] = existing.get("editorial_updated_at")
            _related = [e for e in archive
                        if e.get("category_key") == cat_key and e.get("slug") != slug]
            _related.sort(key=lambda e: _effective_story_datetime(e), reverse=True)
            _atomic_write_verified_article(
                _article_path,
                render_article_page(hero, cat_label, cat_key, today, slug, related=_related),
                headline, hero.get("body", "")
            )
            # If a custom article is writing here, permanently mark the entry custom so
            # it can never be overwritten by a later feed story (see the PROTECTED guard).
            if hero.get("is_custom"):
                existing["is_custom"] = True
                existing["authoritative_custom"] = True
                existing["custom_fingerprint"] = _custom_story_fingerprint(
                    headline, hero.get("teaser", "") or hero.get("body", "")[:180]
                )
                existing["custom_event_key"] = _known_event_key(
                    " ".join([headline, hero.get("teaser", ""), hero.get("body", "")[:500]])
                )
            if source_url:
                existing["source_url"] = source_url
            _hydrate_presentation_item(hero, existing)
            updated_count += 1
        else:
            # New story — create new page
            existing_slugs = {e["slug"] for e in archive}
            if _forced_slug:
                base_slug = _forced_slug
            else:
                base_slug = f"{today}-{slugify(headline)}"
            slug = base_slug
            counter = 1
            while slug in existing_slugs:
                slug = f"{base_slug}-{counter}"; counter += 1
            # Byline timestamp: brand-new article, first-published is now.
            hero["first_published"] = hero.get("first_published") or _now_eastern_rfc822()
            _related = [e for e in archive
                        if e.get("category_key") == cat_key and e.get("slug") != slug]
            _related.sort(key=lambda e: e.get("lastmod") or e.get("date",""), reverse=True)
            _new_article_path = articles_dir / f"{slug}.html"
            _atomic_write_verified_article(
                _new_article_path,
                render_article_page(hero, cat_label, cat_key, today, slug, related=_related),
                headline, hero.get("body", "")
            )
            _new_archive_entry = {
                "slug": slug, "headline": headline,
                "teaser": hero.get("teaser","") or hero.get("body","")[:180],
                "category_key": cat_key, "category_label": cat_label,
                "date": today, "lastmod": today,
                # Full timestamp of when WE first published this, in Eastern time,
                # RFC-822. This is what the RSS feed uses for pubDate so Nextdoor and
                # other consumers show when the story appeared on OUR site, not when
                # the original source posted it.
                "first_published": hero.get("first_published") or _now_eastern_rfc822(),
                "editorial_updated_at": "",
                "content_hash": _canonical_content_hash(
                    headline, hero.get("teaser", "") or hero.get("body", "")[:180],
                    hero.get("body", ""), hero.get("image_url", "")
                ),
                "image_url": hero.get("image_url",""),
                "feed_url": hero.get("feed_url",""),
                "source_url": hero.get("link",""),
                "is_weather_alert": bool(hero.get("is_weather_alert")),
                "is_custom": bool(hero.get("is_custom")),
                "authoritative_custom": bool(hero.get("is_custom")),
                "custom_fingerprint": _custom_story_fingerprint(
                    headline, hero.get("teaser", "") or hero.get("body", "")[:180]
                ) if hero.get("is_custom") else "",
                "custom_event_key": _known_event_key(
                    " ".join([headline, hero.get("teaser", ""), hero.get("body", "")[:500]])
                ) if hero.get("is_custom") else "",
                "body": hero.get("body", ""),
                "article_word_count": _word_count(hero.get("body", "")),
                "article_paragraph_count": _paragraph_count(hero.get("body", "")),
                "event_url": hero.get("event_url", ""),
                "event_link_text": hero.get("event_link_text", ""),
            }
            archive.append(_new_archive_entry)
            _hydrate_presentation_item(hero, _new_archive_entry)
            # Related angles always remain separate stories. They may retain a
            # relationship pointer for future UI use, but they never modify, append to,
            # or rewrite the event canonical article.
            if _related_canonical is not None:
                _new_archive_entry["related_canonical_slug"] = _related_canonical.get("slug", "")
                print(f"  RELATED ANGLE: kept separate from canonical '{_related_canonical.get('headline','')[:55]}'")
            new_count += 1

    # FINAL production enforcement: article generation above may have recreated a
    # known duplicate permalink. Reapply all cumulative redirects now, then build
    # archive/RSS/sitemaps only from the cleaned archive.
    archive, _redirect_verification = enforce_canonical_redirects(
        archive, articles_dir, OUTPUT_DIR, current_run_redirects=_canonical_redirects
    )
    # Final atomic presentation synchronization. Every homepage/category object now
    # carries the exact canonical slug and reader-visible copy from the same archive
    # row. This prevents a headline/teaser from one story linking to another story's
    # permalink, even when the two stories share a broad topic such as cyclospora.
    for _cat in all_categories:
        for _item in [_cat.get("hero")] + list(_cat.get("cards", [])):
            _canonical = find_presentation_canonical(_item, archive)
            if _canonical:
                _hydrate_presentation_item(_item, _canonical)
    _top_canonical = find_presentation_canonical(top_cat.get("hero"), archive)
    if _top_canonical:
        _hydrate_presentation_item(top_cat["hero"], _top_canonical)

    # Transaction boundary: no homepage/category/RSS state is committed unless every
    # presentation object resolves to an article file that already exists on disk.
    _assert_presentation_targets_exist(all_categories, top_cat, archive, articles_dir)

    _archive_stage = archive_path.with_name(archive_path.name + ".staged")
    _archive_stage.write_text(json.dumps(archive, indent=2), encoding="utf-8")
    os.replace(_archive_stage, archive_path)
    write_story_regression_report(OUTPUT_DIR, archive, _redirect_verification)
    write_story_health_report(OUTPUT_DIR, archive, current_run_redirects=_canonical_redirects)
    (OUTPUT_DIR / "archive.html").write_text(render_archive_page(archive), encoding="utf-8")
    (OUTPUT_DIR / "sitemap.xml").write_text(update_sitemap(archive), encoding="utf-8")
    (OUTPUT_DIR / "news-sitemap.xml").write_text(update_news_sitemap(archive), encoding="utf-8")
    print(f"  Archived {new_count} new, updated {updated_count} existing ({len(archive)} total)")

def classify_stories(feed_cache):
    """ONE batched LLM call assigns categories to every unique story across all feeds.
    Replaces the per-category banned-word lists with actual comprehension: the model
    knows a DEA meth story is crime (not business because it says 'prices'), that
    campaign fundraising is not local government, and that a national survey doesn't
    belong on a hyperlocal site at all.

    Returns {headline_lower: set(category_keys)} or None on failure (caller falls
    back to keyword behavior). A story can get MULTIPLE categories (e.g. a Hobe Sound
    business opening is both 'business' and 'martin'). 'none' means the story does
    not belong on the site (national fluff, out-of-area, syndicated filler).
    """
    # Collect unique stories from all feeds
    seen = {}
    for url, entries in feed_cache.items():
        for e in entries[:15]:
            title = sanitize_text((e.get("title") or "").strip())
            if not title or title.lower() in seen:
                continue
            summary = ""
            try:
                summary = extract_rss_text(e)[:300]
            except Exception:
                pass
            seen[title.lower()] = {"title": title, "summary": summary}

    stories = list(seen.values())
    if not stories:
        return None

    # Cap the batch to keep the call reasonable; freshest-first ordering is
    # preserved by feed order. 120 covers a typical run's unique stories.
    stories = stories[:120]

    listing = "\n".join(
        f"{i+1}. {s['title']}" + (f" — {s['summary'][:140]}" if s['summary'] else "")
        for i, s in enumerate(stories)
    )

    prompt = (
        "You classify stories for Treasure Coast Today, a hyperlocal news site covering "
        "Martin County, St. Lucie County, and Indian River County, Florida (the Treasure Coast). "
        "Palm Beach County, Miami, Orlando etc. are OUTSIDE the coverage area.\n\n"
        "Categories:\n"
        "- local_gov: city/county government, schools, budgets, ordinances, public meetings IN the three counties\n"
        "- crime: crime, arrests, courts, fires, crashes, drug enforcement, public safety affecting the three counties "
        "(including threats spreading INTO the area from elsewhere)\n"
        "- business: local business openings/closings, development, real estate, economy IN the three counties\n"
        "- sports: local sports specifically (St. Lucie Mets, Treasure Coast high schools and colleges). "
        "Do NOT tag national or world sports (World Cup, NFL, NBA, national leagues) unless a Treasure Coast team, "
        "school or athlete is the subject\n"
        "- things_to_do: local events, festivals, restaurants, recreation in the three counties\n"
        "- florida: statewide Florida news including state politics, laws, insurance, DeSantis, elections\n"
        "- martin / st_lucie / indian_river: stories specifically tied to that county. Assign the county ONLY when "
        "the story's events happen in, or its subject is clearly located in, that specific county. Assign the "
        "CORRECT county and no other: a St. Lucie story is st_lucie, NOT indian_river or martin. A story about one "
        "county must never be tagged with a different county. If a story spans the whole Treasure Coast, it may take "
        "more than one county; if it names no specific county, assign NO county tag (a topic category or florida only)\n"
        "- none: does NOT belong on this site. This includes:\n"
        "  * national or world news with no Treasure Coast angle (e.g. 'World Cup boosts national beer sales')\n"
        "  * stories about Palm Beach County, Miami, Orlando, Tampa or anywhere outside the three counties, "
        "with no direct Treasure Coast impact\n"
        "  * syndicated lifestyle, survey, or listicle filler\n"
        "  * PROMOTIONAL or ADVERTORIAL content: sponsored posts, contributed 'articles' from law firms, "
        "clinics, contractors or other businesses, SEO content marketing, and anything whose real purpose is to "
        "advertise a service rather than report news (e.g. 'Vero Beach truck accident lawyer explains what to do "
        "after a crash' is a law-firm ad, not news). If it reads like marketing or a business explaining/promoting "
        "its own services, it is none\n"
        "  * a TV or radio station promoting itself or its own people (weather spotter, anchor, reporter, "
        "meteorologist or on-air personality profiles; behind-the-scenes-at-our-station pieces) — self-promotion "
        "for a competing outlet, not news, even when it names a local town\n"
        "  * NON-NEWSWORTHY or automated data: a private individual's routine activity, automated flight-tracking "
        "or vessel-tracking logs (e.g. 'Piper Aztec flew from Stuart to Georgia'), weather-station readings, "
        "auto-generated data pages, obituaries-as-listings, or anything with no genuine public interest. If it is "
        "just a record of one person's or family's private activity and not a matter of public concern, it is none. "
        "A local news site reports events that matter to the community, not logs of who flew or sailed where\n\n"
        "Rules:\n"
        "- A story can have multiple categories (e.g. a Stuart restaurant opening = business + martin + things_to_do)\n"
        "- Statewide political stories (campaigns, fundraising, primaries) = florida ONLY, never local_gov\n"
        "- A story about a threat/trend spreading INTO the Treasure Coast from outside IS relevant (crime/florida as fits)\n"
        "- Feel-good human interest about a local person = the county + the closest topic fit\n"
        "- NEVER assign a county tag to a national, statewide, or out-of-area story just because it mentions a topic; "
        "a national business or sports story does not become local\n"
        "- Be strict. This is a LOCAL news site. When in doubt between none and a category, choose none. It is far "
        "better to drop a marginal or out-of-area story than to show it in a local section\n\n"
        f"Stories:\n{listing}\n\n"
        "Return ONLY a JSON object mapping story number to an array of category keys, e.g.\n"
        '{"1": ["crime", "martin"], "2": ["none"], "3": ["florida"]}\n'
        "Every story number must appear. No other text."
    )

    try:
        resp = client.messages.create(
            model=MODEL_SELECTION,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        mapping = json.loads(raw)
    except Exception as e:
        print(f"  Story classification failed ({e}); falling back to keyword filters")
        return None

    valid_keys = set(CATEGORIES.keys()) | {"none"}
    result = {}
    for i, s in enumerate(stories):
        cats = mapping.get(str(i + 1), [])
        if isinstance(cats, str):
            cats = [cats]
        cats = {c for c in cats if c in valid_keys}
        if not cats:
            cats = {"none"}
        result[s["title"].lower()] = cats

    n_none = sum(1 for v in result.values() if v == {"none"})
    print(f"  Classified {len(result)} stories via LLM ({n_none} rejected as non-local)")
    return result



def ensure_all_category_sections(all_categories, min_cards=6):
    """Guarantee every configured category has a visible, populated section.

    Fresh/live content remains preferred. When a category fails generation, has no
    valid hero, or has too few cards, recover the newest matching stories from the
    permanent archive. Archive recovery has no freshness cutoff: an older real story
    is always better than hiding a category or presenting an empty section.
    """
    archive = _sanitize_authoritative_custom_archive(
        load_archive(OUTPUT_DIR / "archive.json"), OUTPUT_DIR / "articles"
    )
    archive.sort(key=lambda e: e.get("lastmod") or e.get("date", ""), reverse=True)

    def entry_matches(e, category_key):
        if not e.get("headline") or not e.get("slug"):
            return False
        if not _archive_entry_publishable(e):
            return False
        if category_key in COUNTY_KEYS:
            probe = {
                "headline": e.get("headline", ""),
                "title": e.get("headline", ""),
                "teaser": e.get("teaser", ""),
                "summary": e.get("teaser", ""),
                "body": _archive_article_body(e),
                "feed_url": e.get("feed_url", ""),
            }
            # County archive recovery never trusts the old category_key by itself.
            # That old label may be exactly how a bad Stuart/Sebastian match entered.
            return _county_locality_evidence(category_key, probe)
        return e.get("category_key") == category_key

    def archived_story(e, category_key):
        label = CATEGORIES[category_key]["label"]
        body = (_archive_article_body(e) or e.get("body") or e.get("teaser") or "").strip()
        if not body:
            body = f"Read this {label.lower()} story from the Treasure Coast Today archive."
        image_url = e.get("image_url", "")
        image_credit = e.get("image_credit", "")
        if not image_url:
            image_url, image_credit = get_fallback_image(category_key, e.get("headline", ""))
        return {
            "headline": e.get("headline", ""),
            "teaser": e.get("teaser", "") or body[:220],
            "body": body,
            "image_url": image_url,
            "image_credit": image_credit,
            "published": _story_display_timestamp(e),
            "published_raw": _story_display_timestamp(e),
            "urgency_score": 2,
            "enriched": True,
            "source_quality": "archive",
            "category_key": category_key,
            "category_label": label,
            "link": f"{SITE_URL}/articles/{e['slug']}.html",
            "_archived_slug": e["slug"],
            "_archive_only": True,
            "_archive_verified_quality": True,
            "article_word_count": _archive_article_metrics(e)[0],
        }

    by_key = {c.get("category_key"): c for c in all_categories if c.get("category_key")}
    rebuilt = []

    for category_key, config in CATEGORIES.items():
        category = by_key.get(category_key)
        if category is None:
            category = {
                "category_key": category_key,
                "category_label": config["label"],
                "hero": None,
                "cards": [],
            }
        category["category_key"] = category_key
        category["category_label"] = config["label"]
        category["_drop_category"] = False
        category.setdefault("cards", [])

        # Permanent county safety: revalidate live and recovered content with contextual
        # geography. A stale archive category label or bare name like "Stuart" is not
        # enough to survive here.
        if category_key in COUNTY_KEYS:
            if category.get("hero") and not _county_locality_evidence(category_key, category["hero"]):
                print(f"  Permanent county guard removed non-local hero from {config['label']}: "
                      f"'{category['hero'].get('headline','')[:55]}'")
                category["hero"] = None
            category["cards"] = [
                c for c in category.get("cards", [])
                if _county_locality_evidence(category_key, c)
            ]

        # Collect archive candidates once, newest first, and avoid duplicates already
        # present in the live category.
        existing_headlines = {
            (item.get("headline", "") or "").strip().lower()
            for item in ([category.get("hero")] + category.get("cards", []))
            if item
        }
        candidates = [e for e in archive if entry_matches(e, category_key)]

        if not category.get("hero") or not category["hero"].get("headline"):
            for entry in candidates:
                headline_key = entry.get("headline", "").strip().lower()
                if not headline_key or headline_key in existing_headlines:
                    continue
                category["hero"] = archived_story(entry, category_key)
                existing_headlines.add(headline_key)
                print(f"  Permanent archive recovery hero for {config['label']}: "
                      f"'{entry.get('headline','')[:55]}'")
                break

        # Populate a thin live category with older real articles. These appear as normal
        # cards and the remaining archive entries continue to appear in More Stories.
        for entry in candidates:
            if len(category["cards"]) >= min_cards:
                break
            headline_key = entry.get("headline", "").strip().lower()
            if not headline_key or headline_key in existing_headlines:
                continue
            category["cards"].append(archived_story(entry, category_key))
            existing_headlines.add(headline_key)

        if not category.get("hero") and category.get("cards"):
            category["hero"] = category["cards"].pop(0)

        # Absolute first-run safety. This should almost never be used once archive.json
        # contains stories, but it keeps the navigation and section structurally intact.
        if not category.get("hero"):
            fallback_img, fallback_credit = get_fallback_image(category_key, config["label"])
            category["hero"] = {
                "headline": f"{config['label']} coverage",
                "teaser": f"Browse Treasure Coast Today's latest {config['label'].lower()} reporting.",
                "body": f"Browse Treasure Coast Today's latest {config['label'].lower()} reporting and archived stories.",
                "image_url": fallback_img,
                "image_credit": fallback_credit,
                "published": "",
                "published_raw": "",
                "urgency_score": 0,
                "enriched": True,
                "source_quality": "section_placeholder",
                "category_key": category_key,
                "category_label": config["label"],
                "link": f"{SITE_URL}/archive.html",
                "_section_placeholder": True,
            }
            print(f"  Structural placeholder used for {config['label']} (archive has no matching story)")

        rebuilt.append(category)

    all_categories[:] = rebuilt
    return all_categories

def main():
    print("Treasure Coast Today — building site...")
    image_bank   = build_image_bank()
    content_bank = build_content_bank()
    used_bank_images = set()
    all_categories = []

    # Pre-fetch all unique feed URLs once to avoid hammering WPTV with
    # duplicate requests across categories that share the same feeds.
    all_feed_urls = list({url for cat in CATEGORIES.values() for url in cat.get("feeds", [])})
    print(f"  Pre-fetching {len(all_feed_urls)} unique feeds...")
    feed_cache = {}

    def _fetch_and_cache(url):
        try:
            import socket
            old = socket.getdefaulttimeout()
            socket.setdefaulttimeout(8)
            feed = feedparser.parse(url)
            socket.setdefaulttimeout(old)
            return url, feed.entries
        except Exception as e:
            print(f"  Feed error ({url[:60]}): {e}")
            return url, []

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_fetch_and_cache, url): url for url in all_feed_urls}
        # Initialize all feeds to empty so any that never complete still have an entry
        for url in all_feed_urls:
            feed_cache.setdefault(url, [])
        try:
            for fut in as_completed(futures, timeout=45):
                try:
                    url, entries = fut.result(timeout=10)
                    feed_cache[url] = entries
                except Exception as e:
                    feed_cache[futures[fut]] = []
                    print(f"  Feed timeout ({futures[fut][:60]}): {e}")
        except (FuturesTimeoutError, TimeoutError):
            # Some feeds never finished within the overall window — proceed with
            # whatever we have rather than crashing the whole run.
            unfinished = [futures[f] for f in futures if not f.done()]
            print(f"  {len(unfinished)} feed(s) did not finish in time; proceeding with cached results")
            for f in futures:
                f.cancel()

    print(f"  Feed cache: {sum(len(v) for v in feed_cache.values())} total entries across {len(feed_cache)} feeds")

    # LLM classification pass: one batched call assigns categories to every story.
    # Replaces piecemeal banned-word lists with comprehension. On failure, this is
    # None and all filtering falls back to the keyword system automatically.
    global STORY_CLASSIFICATION
    STORY_CLASSIFICATION = classify_stories(feed_cache)

    for cat_key, cat_config in CATEGORIES.items():
        print(f"Processing: {cat_config['label']}...")
        # Pull a wider candidate pool because broad WPTV feeds can contain several
        # sections' worth of local stories. Then rank/filter down to this category.
        headlines = fetch_headlines(cat_config["feeds"], limit=24, feed_cache=feed_cache)

        # Filter headlines older than 48 hours
        from datetime import timezone as _tz2
        _now2 = datetime.now(_tz2.utc)
        def _headline_stale(h):
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(h.get("published","")).astimezone(_tz2.utc)
                return (_now2 - dt).total_seconds() > category_max_age_hours(cat_key) * 3600
            except Exception:
                return False
        fresh_h = [h for h in headlines if not _headline_stale(h)]
        if len(fresh_h) >= 6:
            headlines = fresh_h
        else:
            print(f"  Freshness guard: only {len(fresh_h)} fresh stories for {category_max_age_hours(cat_key)}h window; keeping wider pool")
        if not headlines:
            print(f"  No headlines found for {cat_config['label']}, skipping.")
            continue

        # Publication begins with source quality, not generated word count. Remove
        # thin/brief/discovery items before Claude sees them so they cannot become an
        # article at all. Permanent archive recovery handles categories with no usable
        # fresh source material.
        _source_ready = [h for h in headlines if _source_candidate_publishable(h)]
        _source_rejected = len(headlines) - len(_source_ready)
        if _source_rejected:
            print(f"  Source-depth gate: rejected {_source_rejected} item(s) before article generation")
        headlines = _source_ready
        if not headlines:
            print(f"  No publishable source material for {cat_config['label']}; using archive recovery")
            continue

        headlines = filter_category_headlines(cat_key, headlines, target=HEADLINES_PER_CATEGORY, min_keep=6)

        print(f"  {len(headlines)} publishable-source headlines fetched")
        try:
            try:
                data = generate_category_content(cat_key, cat_config["label"], headlines)
            except (ValueError, json.JSONDecodeError) as first_generation_error:
                # A blank/truncated model response should not erase an entire category.
                # Retry once with the same grounded source set; the outer handler still
                # isolates a persistent failure so the rest of the site can finish.
                print(f"  Category generation returned invalid JSON for {cat_config['label']} "
                      f"({first_generation_error}); retrying once")
                data = generate_category_content(cat_key, cat_config["label"], headlines)

            # Do not mark generated blurbs publishable merely because they crossed a
            # low word threshold. Final publication quality is checked after optional
            # source enrichment below.

            # If the category was dropped or produced no usable hero, skip it entirely
            # rather than crashing on data["hero"]["headline"] below.
            if data.get("_drop_category") or not data.get("hero") or not data["hero"].get("headline"):
                print(f"  Skipping {cat_config['label']}: no usable hero produced")
                continue

            # Images — source_index already attached image_url, fall back to image bank
            source_img = data["hero"].get("image_url", "")
            src_idx = data["hero"].get("source_index")
            original_title = ""
            if src_idx is not None:
                try:
                    original_title = headlines[int(src_idx) - 1].get("title", "")
                except Exception:
                    pass
            bank_img, bank_credit = ("", "")
            if original_title:
                bank_img, bank_credit = match_image(original_title, image_bank, cat_key, used_bank_images)
            if not bank_img:
                bank_img, bank_credit = match_image(data["hero"]["headline"], image_bank, cat_key, used_bank_images)
            img    = source_img if (source_img and not data["hero"].get("image_from_google")) else ""
            credit = bank_credit

            # og:image fetch as fallback
            if not img:
                link = data["hero"].get("link", "")
                if link:
                    og_img = fetch_og_image(link)
                    if og_img:
                        img    = og_img
                        credit = get_image_credit(link)
                        print(f"  Hero image via og:image fetch")

            if not img and bank_img:
                img    = bank_img
                credit = bank_credit
                used_bank_images.add(canonical_image_url(bank_img))

            # Local fallback
            if not img:
                fb_img, fb_credit = get_fallback_image(cat_key, data["hero"].get("headline", ""))
                if fb_img:
                    img    = fb_img
                    credit = fb_credit
                    print(f"  Hero image via local fallback")

            data["hero"]["image_url"]    = img
            data["hero"]["image_credit"] = credit

            # Hero enrichment — live fetch first, then content bank + related RSS
            hero_headline = data["hero"]["headline"]
            hero_link     = data["hero"].get("link", "")
            _is_thin_src  = any(d in hero_link.lower() for d in THIN_SOURCE_DOMAINS)
            if _is_thin_src:
                print(f"  Thin source ({hero_link[:40]}): skipping hero enrichment, capping urgency")
                data["hero"]["urgency_score"] = min(int(data["hero"].get("urgency_score", 5) or 5), 5)

            # Try to fetch full article text for the hero — much richer than RSS summary
            fetched_text = ""
            if hero_link and not _is_thin_src:
                fetched_text = fetch_article_text(hero_link)
                if fetched_text:
                    print(f"  Hero article text fetched: {len(fetched_text.split())} words")

            bank_content  = find_content(hero_headline, content_bank)
            stops = {"that","this","with","from","have","been","said","will","more",
                     "also","when","were","they","their","about","says","just"}
            hero_tokens = set(re.sub(r"[^a-z0-9 ]", " ", hero_headline.lower()).split()) - stops
            related_parts = []
            for h in headlines:
                h_tokens = set(re.sub(r"[^a-z0-9 ]", " ", h.get("title","").lower()).split()) - stops
                if len(hero_tokens & h_tokens) >= 2:
                    related_parts.append(h.get("title","") + ". " + h.get("summary",""))
            related_text = " | ".join(related_parts[:6])

            # Prefer exact full article text from the selected source; do not rely on fuzzy bank matches
            # unless there is no extracted body available.
            selected_article_text = data["hero"].get("article_text", "")
            if selected_article_text and len(selected_article_text.split()) >= 140:
                source_text = selected_article_text
            elif fetched_text and len(fetched_text.split()) >= 80:
                source_text = fetched_text
            else:
                source_parts = [p for p in [related_text] if p]
                source_text  = "\n\n".join(source_parts)

            if source_text and len(source_text.split()) >= 80 and not _is_thin_src:
                stops2 = {"the","a","an","in","of","for","to","and","or","on","at","is","was","are","were","that","this","with"}
                hl_tok  = set(re.sub(r"[^a-z0-9 ]", " ", hero_headline.lower()).split()) - stops2
                src_tok = set(re.sub(r"[^a-z0-9 ]", " ", source_text[:500].lower()).split()) - stops2
                if len(hl_tok & src_tok) >= 2:
                    data["hero"] = enhance_hero_article(data["hero"], source_text)
                    print(f"  Enhanced with: {'bank+' if bank_content else ''}{'related' if related_text else ''}")
                else:
                    print(f"  Enhancement skipped: insufficient keyword overlap")

            # Do not perform another stale swap here. generate_category_content already
            # ran stale selection followed by the final category guard. A second blind
            # cards[0] promotion here was reintroducing category bleed after validation.

            if data.get("_drop_category"):
                print(f"  Skipping {cat_config['label']}: no on-topic content")
                continue

            all_categories.append(data)
            print(f"  Hero: {data['hero']['headline'][:60]}... (urgency: {data['hero'].get('urgency_score')}, image: {'yes' if img else 'no'})")

            # Enrich cards in parallel
            from concurrent.futures import ThreadPoolExecutor as _TPE, as_completed as _ac
            with _TPE(max_workers=6) as _ex:
                _futs = {_ex.submit(enhance_card, card, content_bank, headlines): card
                         for card in data.get("cards", [])}
                for _fut in _ac(_futs, timeout=45):
                    try: _fut.result(timeout=10)
                    except Exception: pass

            # Final publication gate. A hero must be both on-topic and substantial
            # enough to deserve a standalone permalink. Thin cards are discarded; the
            # permanent archive recovery step will fill the section with older real work.
            publishable_cards = []
            for card in data.get("cards", []):
                if _publishable_article(card, hero=False) and _hero_eligible(cat_key, card):
                    card["enriched"] = True
                    publishable_cards.append(card)
            data["cards"] = publishable_cards

            hero_ok = (
                _hero_eligible(cat_key, data.get("hero", {}))
                and _publishable_article(data.get("hero", {}), hero=True)
            )
            if hero_ok:
                data["hero"]["enriched"] = True
            else:
                replacement_i = next(
                    (i for i, c in enumerate(data.get("cards", []))
                     if _publishable_article(c, hero=True) and _hero_eligible(cat_key, c)),
                    None,
                )
                if replacement_i is not None:
                    rejected = data.get("hero", {})
                    data["hero"] = data["cards"].pop(replacement_i)
                    data["hero"]["enriched"] = True
                    print(f"  Publication-quality hero swap for {cat_config['label']}: "
                          f"'{rejected.get('headline','')[:50]}' -> "
                          f"'{data['hero'].get('headline','')[:50]}'")
                else:
                    print(f"  Live {cat_config['label']} content rejected as too thin or off-topic; "
                          "using permanent archive recovery")
                    all_categories.remove(data)

            # Things To Do articles may include a verified official event, ticket, or
            # registration link found on the reporting source page. Never guess a URL,
            # never link back to the source article here, and omit the CTA when confidence
            # is low. Custom articles can provide event_url/event_link_text directly.
            if cat_key == "things_to_do" and data in all_categories:
                _event_items = [
                    item for item in [data.get("hero", {})] + list(data.get("cards", []))
                    if item and not item.get("event_url") and item.get("link")
                ]
                # Source pages are independent; fetch a few in parallel so a slow event
                # site cannot add a minute to the workflow. This uses no Claude tokens.
                if _event_items:
                    with ThreadPoolExecutor(max_workers=min(4, len(_event_items))) as _event_ex:
                        _event_futures = {
                            _event_ex.submit(
                                find_official_event_link,
                                item.get("link", ""),
                                item.get("source_title", "") or item.get("headline", ""),
                            ): item
                            for item in _event_items
                        }
                        for _event_future in as_completed(_event_futures):
                            _event_item = _event_futures[_event_future]
                            try:
                                _event_url, _event_label = _event_future.result()
                            except Exception:
                                _event_url, _event_label = "", ""
                            if _event_url:
                                _event_item["event_url"] = _event_url
                                _event_item["event_link_text"] = _event_label
                                print(f"  Official event link attached: {_event_url[:80]}")

        except Exception as e:
            import traceback
            print(f"  Error for {cat_config['label']}: {e}")
            print(traceback.format_exc())
            continue

    if not all_categories:
        print("  No live categories passed this run; continuing to permanent archive recovery")

    # Inject custom (manually-submitted) articles into their category pools.
    # They get the same scoring/ranking/archival treatment. force_hero pins as
    # the category hero; pin_position is applied later during grid rendering.
    #
    # Auto-generated weather-alert articles (from NWS Extreme/Severe warnings) were
    # removed: the standalone weather page covers conditions, and auto-publishing alert
    # articles is no longer wanted. load_weather_alerts() is left defined but unused so
    # it can be re-enabled later if desired; the is_weather_alert plumbing elsewhere is
    # harmless and simply never fires now that nothing produces alerts.
    custom_articles = load_custom_articles()
    all_injected = custom_articles
    if all_injected:
        cat_by_key = {c["category_key"]: c for c in all_categories}
        for art in all_injected:
            ckey = art["category"]
            target = cat_by_key.get(ckey)
            if not target:
                # Category didn't generate this run — create a minimal container
                label = CATEGORIES.get(ckey, {}).get("label", ckey.replace("_", " ").title())
                target = {"category_key": ckey, "category_label": label,
                          "hero": None, "cards": []}
                all_categories.append(target)
                cat_by_key[ckey] = target
            if art.get("force_hero"):
                # Demote existing hero to a card, pin custom as hero
                if target.get("hero"):
                    target.setdefault("cards", []).insert(0, target["hero"])
                target["hero"] = art
                print(f"  Custom force_hero: '{art['headline'][:50]}' -> {ckey}")
            else:
                # A custom article is authoritative. If the feed generated its OWN
                # version of the same story this run, that feed version must be REPLACED
                # by the custom one everywhere it appears — not just in the custom
                # article's own category. The same story is often classified into
                # multiple categories (e.g. a hazing investigation is crime AND
                # st_lucie), so the feed can hero it in crime while the custom article
                # only targets st_lucie, leaving the feed version to win the FRONT PAGE.
                _art_tokens = _sig_tokens(art.get("headline", ""))

                def _same_as_custom(item):
                    if not item:
                        return False
                    # Permit only a major new milestone in the same underlying event.
                    # Routine rewrites and incremental follow-ups remain suppressed.
                    if _is_significant_story_update(item, art):
                        return False
                    return (_same_event_text(art.get("headline", ""), item.get("headline", ""))
                            or _same_story(_art_tokens, _sig_tokens(item.get("headline", ""))))

                # Sweep EVERY category: drop feed cards that are this story, and if a
                # feed hero in ANY category is this story, remove it (promote a card, or
                # mark the category for the normal no-hero recovery path).
                for _cat in all_categories:
                    if _cat.get("cards"):
                        _cat["cards"] = [c for c in _cat["cards"] if not _same_as_custom(c)]
                    if _same_as_custom(_cat.get("hero")) and _cat is not target:
                        # Feed's version of this story is heroing another category —
                        # replace it with the next card, or clear it.
                        _cards = _cat.get("cards", [])
                        _cat["hero"] = _cards.pop(0) if _cards else None
                        print(f"  Custom article displaced feed hero of same story in {_cat['category_key']}")

                # Now place the custom article in its own category
                _hero = target.get("hero")
                if _hero is None or _same_as_custom(_hero):
                    target["hero"] = art
                else:
                    target.setdefault("cards", []).append(art)
                print(f"  Custom article: '{art['headline'][:50]}' -> {ckey}")

    # PHASE 2 STORY ENGINE: guarded production mode. Only non-custom, same-story,
    # same-safe-stage matches at 95%+ confidence are removed from live output.
    # Everything uncertain, general-stage, or stage-advancing remains publishable.
    _archive_path = OUTPUT_DIR / "archive.json"
    _published_archive = load_archive(_archive_path)
    _live_suppressions = apply_guarded_story_suppression(
        all_categories, _published_archive, current_customs=custom_articles
    )
    _shadow = build_story_shadow(
        _published_archive,
        current_customs=custom_articles,
        live_categories=all_categories,
        output_dir=OUTPUT_DIR,
    )
    if _live_suppressions:
        _data_dir = OUTPUT_DIR / "data"
        _run_id = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        _persist_story_decision_logs(_data_dir, _live_suppressions, _run_id)
        print(f"  Guarded story engine suppressed {len(_live_suppressions)} high-confidence live duplicate placements")

    # Recover category depth after safe duplicate removal.
    ensure_all_category_sections(all_categories, min_cards=6)

    # Front page hero selection
    top_cat = select_front_page_hero(all_categories)
    if top_cat is None:
        eligible = [c for c in all_categories if CATEGORIES.get(c["category_key"],{}).get("front_page_hero", True)]
        top_cat  = max(eligible if eligible else all_categories,
                       key=lambda c: min(int(c["hero"].get("urgency_score",0) or 0),
                                         CATEGORIES.get(c["category_key"],{}).get("front_page_cap",10)))

    # Promote duplicate heroes
    promote_duplicate_heroes(top_cat, all_categories)

    # Final fallback images for any promoted heroes without images
    for cat in all_categories:
        hero = cat.get("hero", {})
        if not hero.get("image_url"):
            fb_img, fb_credit = get_fallback_image(cat.get("category_key","local_gov"), hero.get("headline",""))
            if fb_img:
                hero["image_url"]    = fb_img
                hero["image_credit"] = fb_credit
                print(f"  {cat.get('category_key')}: fallback image applied after hero promotion")
    if not top_cat.get("hero",{}).get("image_url"):
        fb_img, fb_credit = get_fallback_image(top_cat.get("category_key","local_gov"), top_cat["hero"].get("headline",""))
        if fb_img:
            top_cat["hero"]["image_url"]    = fb_img
            top_cat["hero"]["image_credit"] = fb_credit

    # Archive first — creates all article pages and populates archive.json so the
    # homepage grid can link to permalinks that actually exist with matching slugs.
    write_archives(all_categories, top_cat)

    # Render and write homepage (now archive lookups resolve to real slugs)
    index_html = render_index(all_categories, top_cat)
    (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")

    # Normalize persistent article files, then stop the deployment if the unified
    # presentation contract is not present. This prevents another apparently random
    # mix of old and new article shells from reaching production.
    _repair_article_shells(OUTPUT_DIR)
    _validate_presentation_contract(OUTPUT_DIR)

    # data.json
    write_data_json(all_categories, top_cat)

    # Static pages
    (OUTPUT_DIR / "about.html").write_text(render_about_page(), encoding="utf-8")
    _author_dir = OUTPUT_DIR / "author"
    _author_dir.mkdir(exist_ok=True)
    (_author_dir / "andrew-dobrow.html").write_text(render_author_page(), encoding="utf-8")
    (OUTPUT_DIR / "editorial-standards.html").write_text(render_editorial_standards_page(), encoding="utf-8")
    (OUTPUT_DIR / "corrections-policy.html").write_text(render_corrections_page(), encoding="utf-8")
    (OUTPUT_DIR / "ownership.html").write_text(render_ownership_page(), encoding="utf-8")
    (OUTPUT_DIR / "advertise.html").write_text(render_advertise_page(), encoding="utf-8")
    (OUTPUT_DIR / "feed.xml").write_text(render_rss_feed(all_categories, top_cat), encoding="utf-8")

    print(f"Done. {len(all_categories)} categories written.")


if __name__ == "__main__":
    main()
