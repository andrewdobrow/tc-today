"""
Treasure Coast Today - news generation pipeline
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
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# -- CONFIG --

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
            "https://www.wptv.com/news/local-news.rss",
            "https://www.wptv.com/news/region-martin-county.rss",
            "https://www.wptv.com/news/region-st-lucie-county.rss",
            "https://www.wptv.com/news/region-indian-river-county.rss",
            "https://news.google.com/rss/search?q=martin+county+high+school+sports+game+score+when:3d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=st+lucie+county+high+school+sports+game+when:3d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=treasure+coast+florida+football+basketball+baseball+soccer+when:3d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=st+lucie+mets+florida+when:7d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=jensen+beach+south+fork+martin+county+high+school+sports+when:7d&hl=en-US&gl=US&ceid=US:en",
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
            "https://news.google.com/rss/search?q=florida+news+when:1d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=florida+legislature+governor+desantis+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=florida+economy+housing+insurance+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://floridapolitics.com/feed/",
        ],
    },
    "martin": {
        "label": "Martin County",
        "front_page_hero": False,
        "feeds": [
            "https://www.wptv.com/news/region-martin-county.rss",
            "https://www.wptv.com/news/local-news.rss",
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

# Content bank — loaded once at startup, used for card enrichment
CONTENT_BANK_FEEDS = [
    "https://www.wptv.com/news/local-news.rss",
    "https://www.wptv.com/news/education/back-to-school.rss",
    "https://www.wptv.com/news/state.rss",
    "https://www.wptv.com/feeds/rss/news",
    "https://www.wptv.com/feeds/rss/local",
    "https://news.google.com/rss/search?q=treasure+coast+florida&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=martin+county+florida&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=port+st+lucie+florida&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=vero+beach+florida&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=fort+pierce+florida&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=stuart+florida+news&hl=en-US&gl=US&ceid=US:en",
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

def get_fallback_image(category_key, headline=""):
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
        for fut in as_completed(futures, timeout=25):
            try:
                url, feed_entries = fut.result(timeout=10)
                feed_results.append((url, feed_entries))
            except Exception as e:
                print(f"  Feed timeout ({futures[fut][:60]}): {e}")

    seen, entries = set(), []
    for url, feed_entries in feed_results:
        try:
            for entry in feed_entries[:15]:
                title = sanitize_text(entry.get("title", "").strip())
                if not title or title.lower() in seen:
                    continue
                seen.add(title.lower())

                link = extract_publisher_url(entry)
                summary = extract_rss_text(entry)[:2500]
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
            full = fetch_article_text(link, max_words=1000)
            if full and len(full.split()) >= 140:
                h["article_text"] = full
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
        h.get("summary", ""),
        h.get("article_text", "")[:1200],
    ]).lower()


def _has_any(text, terms):
    return any(term in text for term in terms)


# Hero selection is stricter than card inclusion. Cards may use softer fallback
# logic to keep a section populated, but a section lead must clearly belong to
# that section.
def _hero_eligible(category_key, h):
    text = _text_for_category_match(h)
    title = (h.get("title", "") or "").lower()
    quality = h.get("source_quality", "")

    if quality in {"thin", "discovery_only"}:
        return False

    topic_terms = {
        "local_gov": ["commission", "commissioner", "city council", "county council", "school board", "zoning", "rezoning", "ordinance", "budget", "tax", "millage", "mayor", "public meeting", "vote", "approved", "approval", "proposal", "hearing", "development order", "planning", "public policy", "ban", "takes effect", "school district", "superintendent", "principal", "education", "student", "teacher", "curriculum", "school closure", "school merger"],
        "crime": ["arrest", "arrested", "charged", "charges", "sheriff", "police", "deputies", "deputy", "officer", "shooting", "stabbed", "stabbing", "homicide", "murder", "crash", "fatal", "killed", "injured", "fire rescue", "missing", "suspect", "victim", "jail", "court", "public safety", "fraud", "burglary", "robbery"],
        "business": ["business", "development", "developer", "real estate", "housing", "restaurant", "store", "retail", "mall", "company", "jobs", "hiring", "economic", "economy", "construction", "project", "commercial", "warehouse", "factory", "plant", "opening", "closing", "closes", "expansion", "wawa", "publix", "downtown", "permit", "property", "market", "walmart", "campbell soup"],
        "sports": ["sports", "football", "basketball", "baseball", "softball", "soccer", "volleyball", "tennis", "golf", "lacrosse", "wrestling", "track", "cross country", "swimming", "game", "score", "win", "wins", "won", "loss", "defeats", "beats", "championship", "playoff", "tournament", "athlete", "coach", "team", "mets", "st. lucie mets", "st lucie mets"],
        "things_to_do": ["event", "events", "festival", "concert", "show", "weekend", "things to do", "restaurant", "food", "arts", "art", "music", "theater", "theatre", "park", "market", "farmers market", "fair", "fundraiser", "community", "parade", "holiday", "museum", "exhibit", "taste", "family-friendly", "activities"],
        "florida": ["florida", "state", "desantis", "legislature", "tallahassee", "supreme court", "insurance", "hurricane", "weather", "statewide", "lawmakers", "law", "governor", "environment", "economy", "housing", "property insurance"],
    }

    hard_negatives = {
        "sports":       ["sues", "lawsuit", "campbell soup", "spaghettios", "worms", "walmart",
                         "fertilizer", "ban", "commission", "politics", "arrest", "charged",
                         "shooting", "homicide", "murder", "missing", "fatal crash", "zoning",
                         "ordinance", "budget", "tax", "city council", "county council",
                         "restaurant opens", "business opens", "store opens", "new store"],
        "business":     ["shooting", "homicide", "murder", "missing", "fatal crash",
                         "arrest", "arrested", "charged", "stabbing", "robbery", "burglary",
                         "game recap", "score", "wins over", "defeats", "beats", "championship",
                         "playoff", "tournament", "festival", "concert", "parade"],
        "crime":        ["restaurant", "business opens", "store opens", "new store", "hiring",
                         "festival", "concert", "event", "game recap", "score", "wins", "defeats",
                         "zoning", "ordinance", "budget vote", "commission vote", "development order"],
        "things_to_do": ["shooting", "homicide", "murder", "fatal crash", "arrest", "charged",
                         "stabbing", "robbery", "burglary", "zoning", "ordinance", "budget",
                         "tax", "lawsuit", "commission vote"],
        "local_gov":    ["concert", "festival", "game recap", "score", "wins over", "defeats",
                         "arrest", "shooting", "homicide", "murder"],
        "florida":      ["game recap", "score", "wins over", "defeats", "beats"],
    }

    county_terms = {
        "martin": ["martin county", "stuart", "jensen beach", "palm city", "hobe sound", "port salerno", "jupiter island"],
        "st_lucie": ["st. lucie", "st lucie", "port st. lucie", "port st lucie", "fort pierce", "st. lucie west", "st lucie west"],
        "indian_river": ["indian river", "vero beach", "sebastian", "fellsmere"],
    }

    if category_key in county_terms:
        feed_url = (h.get("feed_url", "") or "").lower()
        county_feed_hints = {"martin": "region-martin-county", "st_lucie": "region-st-lucie-county", "indian_river": "region-indian-river-county"}
        return county_feed_hints.get(category_key, "") in feed_url or _has_any(text, county_terms[category_key])

    if category_key in topic_terms:
        if _has_any(text, hard_negatives.get(category_key, [])):
            return False
        return _has_any(title, topic_terms[category_key]) or _has_any(text, topic_terms[category_key])

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
        # If WPTV itself placed the story in a county feed, trust that signal.
        # Do not force the headline/body to repeat the county name.
        if county_feed_hints.get(category_key, "") in feed_url:
            score += 9
        if _has_any(text, county_terms[category_key]):
            score += 5
        if h.get("source_quality") == "full":
            score += 2
        elif h.get("source_quality") in {"summary", "brief"}:
            score += 1
        # County pages can carry all local-news topics, so do not over-filter by topic.
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
        threshold = 1  # County pages are already narrow feeds — don't filter aggressively

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
        return f"{i+1}. {title} [source_type:{stype}] [source_quality:{quality}] [hero_eligible:{hero_eligible}] [category_match_score:{match_score}]{pub_str}\n   {sanitize(content)[:5000]}"
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
- Stories marked [source_quality:summary] may be used for normal cards if the provided text has concrete facts.
- Stories marked [source_quality:brief] or [source_type:discovery_only] may be used as short factual cards when needed to keep the county section populated, but they must not be padded with generic context.
- The hero must come from [source_quality:full] or [source_quality:summary] whenever possible. Do not use [source_quality:thin] for the hero.
- For county sections, aim to return six cards. If a source is thin, write a brief factual card instead of inventing filler or dropping the item.
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
        model="claude-sonnet-4-5",
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
                start = cleaned.index("{")
                end   = cleaned.rindex("}") + 1
                data  = json.loads(cleaned[start:end], strict=False)
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
    data["hero"]["body"] = strip_markdown(data["hero"].get("body", ""), data["hero"].get("headline", ""))
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

    def _story_is_stale(item):
        content = (item.get("teaser", "") + " " + item.get("body", "")[:800]).lower()
        # Fresh-development language always wins (e.g. "suspect arrested today" in an old story)
        if any(p in content for p in _fresh_override):
            return False
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
            if not _story_is_stale(card):
                old_hero = data["hero"]
                print(f"  Stale hero swapped: '{old_hero.get('headline','')[:50]}' -> '{card.get('headline','')[:50]}'")
                # Give the demoted hero a teaser (heroes lack one; cards need one)
                if not old_hero.get("teaser"):
                    _body = old_hero.get("body", "").strip()
                    _first = _body.split(". ")[0].strip()
                    old_hero["teaser"] = (_first[:160] + ".") if _first else ""
                data["hero"] = card
                data["cards"][ci] = old_hero
                break

    return data


# -- HTML GENERATION --

def now_et():
    from datetime import timezone, timedelta
    utc = datetime.now(timezone.utc)
    et  = utc - timedelta(hours=4)
    return et.strftime("%-I:%M %p ET")

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
    return "".join(
        f"<p>{p.strip()}</p>"
        for p in paragraphs
        if p.strip() and len(p.strip()) > 30
    )


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
                summary = entry.get("summary", entry.get("description", ""))[:1200]
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




def fetch_article_text(url, max_words=1000):
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

    # If this is an open source but article_text was not stored, try once here.
    if not source_text and link and not is_thin and source.get("source_type") == "full_source":
        source_text = fetch_article_text(link, max_words=900)
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
            model="claude-haiku-4-5-20251001",
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
    except Exception:
        pass

    return card


def enhance_hero_article(hero, full_text):
    """Rewrite the hero article using the full source text for accuracy and detail."""
    if not full_text or len(full_text.split()) < 150:
        return hero  # Not enough text to improve on
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
            model="claude-haiku-4-5-20251001",
            max_tokens=1600,
            messages=[{"role": "user", "content": prompt}]
        )
        enhanced = resp.content[0].text.strip()
        # Detect if Claude returned an explanation instead of an article
        explanation_signals = ["i cannot rewrite", "source material", "does not match", "i must return", "cannot proceed"]
        if enhanced and not any(s in enhanced.lower()[:200] for s in explanation_signals):
            hero["body"] = strip_markdown(enhanced, hero.get("headline", ""))
            print(f"  Hero article enhanced with full source text")
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
    Considers systemic impact and US relevance — not just raw urgency or casualty count.
    Localized tragedies (regional accidents) lose to geopolitical events with broad reach,
    even when casualty counts are similar."""
    if not all_categories:
        return None

    def _is_eligible(cat):
        if not CATEGORIES.get(cat["category_key"], {}).get("front_page_hero", True):
            us_words = ["us strikes", "us military", "american forces", "u.s. strikes",
                        "u.s. military", "united states strikes", "trump orders", "pentagon"]
            return any(w in cat["hero"].get("headline", "").lower() for w in us_words)
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
        # Check timestamp — 18+ hours old with no fresh-development language is stale
        pub = hero.get("published", "")
        if pub:
            try:
                dt  = parsedate_to_datetime(pub).astimezone(_tz.utc)
                hrs = (_now - dt).total_seconds() / 3600
                if hrs >= 18:
                    return True
            except Exception:
                pass
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
        "But \"matters to US readers\" is about national/systemic relevance, NOT just whether it happened on US soil. "
        "A regional US tragedy is local to that region; a foreign event involving US allies or US interests can have "
        "broader national implications.\n"
        "\n"
        "FRESHNESS IS CRITICAL: This app updates throughout the day. The front page hero must be CURRENT news — what is "
        "happening NOW, not what already happened. Each candidate has a timestamp label, but BE SKEPTICAL OF TIMESTAMPS — "
        "publishers often re-publish or update old articles with minor changes, which refreshes the timestamp even though "
        "the event itself is old.\n"
        "\n"
        "CRITICAL DISTINCTION: differentiate between (A) an OLD EVENT being republished with a refreshed timestamp, vs "
        "(B) a NEW DEVELOPMENT in an ongoing story. The former is stale; the latter is fresh and can absolutely be hero-worthy.\n"
        "- (A) STALE: The article describes an event that already happened, with no new action today. Example: \"Blue Origin "
        "rocket exploded yesterday at Cape Canaveral\" — this is yesterday's explosion being recapped. Avoid as hero.\n"
        "- (B) FRESH: The article describes a NEW action, decision, arrest, ruling, statement, or development today, even if "
        "it's connected to an older story. Example: \"Suspect in Trump assassination attempt arrested\" — even though the "
        "attempt was days ago, the arrest is happening NOW and is breaking news. This IS hero-worthy.\n"
        "\n"
        "Look at the teaser to determine which case applies:\n"
        "- Phrases like \"announced today\", \"arrested today\", \"ruled today\", \"said this morning\", \"hours ago\", "
        "\"just\", \"breaking\" — these signal a NEW development happening now, even in an old story. TREAT AS FRESH.\n"
        "- Phrases that recap an old event with no new action today — \"yesterday's\", \"earlier this week\", \"last "
        "Monday's\", and the article is just summarizing what already happened — TREAT AS STALE.\n"
        "- When in doubt, ask: \"Is something new happening today in this story, or is this just a recap of an old event?\"\n"
        "\n"
        "Freshness tiers (combining timestamp AND content signals):\n"
        "- New event or new development from the past few hours: strong hero candidate\n"
        "- New development today in an older ongoing story: also strong (arrests, rulings, statements, decisions)\n"
        "- From 6-12 hours ago and still actively unfolding: still acceptable\n"
        "- Pure recap of an event from yesterday or earlier with no new development: AVOID as hero — it belongs as a card if at all\n"
        "\n"
        "When comparing, ask: \"Is something NEW happening in this story right now, or did it already happen and move on?\" "
        "If something new is happening, it's fresh regardless of when the original event occurred. If it has moved on with "
        "no new development, pick a fresher story.\n"
        "\n"
        "Pick the story with the GREATEST systemic impact for the US audience among CURRENT stories — not the biggest story regardless of when it happened.\n"
        "\n"
        "STRONG front-page heroes for a local news site:\n"
        "1. Breaking court rulings or legal decisions involving the President, Congress, or major US institutions — these are the kind of stories that make every major outlet's front page\n"
        "2. Major US national policy/political developments affecting millions (Supreme Court rulings, major legislation passed/signed, executive actions with broad immediate impact)\n"
        "3. US national security crises, attacks on US soil, US military action\n"
        "4. Major economic events affecting US consumers/markets (Fed decisions, market crashes, major industry collapses, jobs reports)\n"
        "5. Major geopolitical events involving US allies or US interests (attacks on NATO countries, peace deals, sanctions, treaties) — these affect US foreign policy even when they happen abroad\n"
        "6. Major US infrastructure/space/scientific events with national consequence (NASA missions, major tech failures with national impact)\n"
        "\n"
        "MEDIUM heroes — okay if nothing stronger is fresh, but typically belong as cards if a strong-tier story exists:\n"
        "- Routine regulatory proposals (SEC rule changes, FCC proposals, agency-level rulemaking) — these matter to specific industries and policy wonks but rarely lead general-audience newspapers\n"
        "- Single-state political news without broader implications\n"
        "- Minor policy clarifications or technical legal rulings\n"
        "\n"
        "Quick gut check: if a story would NOT be on the front page of CNN, NYT, WaPo, or AP right now, it probably shouldn't be your hero either. Court rulings about Trump, breaking legal decisions, major political fights, and significant policy shifts make general-audience front pages. Niche regulatory proposals usually don't.\n"
        "\n"
        "WEAK front-page heroes (these belong as cards, NOT as the lead):\n"
        "- Smaller-scale localized US tragedies — single bus/car crashes, single-building fires, industrial accidents, factory explosions, mine collapses, single-aircraft small plane crashes, local crime. These affect their region/industry, not the nation broadly.\n"
        "- Foreign tragedies without US connection (foreign domestic crime, regional conflicts not involving US allies/interests)\n"
        "- Single-company news (funding rounds, IPOs, executive shakeups, single-quarter earnings)\n"
        "- Executive opinions or statements about competitors \u2014 'CEO says X is too expensive', 'executive calls Y overrated' are cards, not heroes\n"
        "- Industry commentary, analyst takes, or opinion pieces without a concrete policy or market-moving event\n"
        "- Sports/entertainment — these are ALWAYS cards, never heroes, regardless of historic significance. A Grand Slam final, championship game, or record-breaking performance belongs in the Sports section as a card.\n"
        "- Celebrity deaths unless of major historical/cultural figures\n"
        "- Routine policy proposals without immediate broad impact\n"
        "\n"
        "Casualty/disaster events that DO warrant hero status are large in scale or national in reach:\n"
        "- Major commercial airline crashes (large passenger jets, dozens+ killed)\n"
        "- Mass shootings or terrorism at historic scale\n"
        "- Multi-state natural disasters (major hurricanes, large wildfires across regions, earthquakes affecting populated areas)\n"
        "- Bridge collapses or major infrastructure failures with national implications\n"
        "- Attacks on US military or significant US security events\n"
        "- Industrial disasters with broad consequences (e.g. nuclear incidents, chemical releases affecting large populations)\n"
        "\n"
        "Rule of thumb: if a tragedy is contained to one workplace, one road, one building, or one small town, it is a card, not a hero — even with multiple casualties. If it affects multiple states, a major industry, or hundreds of lives, it can be hero-worthy.\n"
        "\n"
        "Examples:\n"
        "- 'Trump delays Iran ceasefire' BEATS 'Nine dead in Oregon paper mill disaster' — the ceasefire decision is active US foreign policy reshaping a major conflict; the mill disaster, however tragic, is a regional industrial accident with no national policy consequence.\n"
        "- 'Russian drone strikes NATO ally Romania' BEATS 'Bus crash kills 5 in Virginia' — the drone strike has NATO/Article 5 implications affecting US foreign policy; the bus crash, however tragic, is regional.\n"
        "- 'Supreme Court rules on major case' BEATS 'Tech company raises $10B' — court rulings reshape US law for millions.\n"
        "- 'US bus crash kills 5' BEATS 'European train delay' — between two local stories, US readers care more about US events.\n"
        "\n"
        "IMPORTANT ON CASUALTY COUNT: A high death toll does NOT by itself make a story front-page-worthy. The question is REACH — how many people BEYOND those directly involved are affected, and whether anything changes nationally. A chemical spill that kills 11 workers INSIDE one mill is a contained workplace accident — its reach is that facility and that town, NOT the nation. That is a card. The 'chemical release affecting large populations' exception means events like a city-wide toxic cloud forcing mass evacuation — NOT a fatal accident confined to one workplace. Do not let the word 'chemical' or a double-digit death count override the reach test.\n"
        "\n"
        "THINK FIRST, THEN ANSWER. For each candidate, briefly assess in one short line: (a) how recent the actual event is, and (b) its national reach — does it change US policy/markets/security, or affect Americans beyond those directly involved? Then state your pick.\n"
        "\n"
        "Format your response EXACTLY like this:\n"
        "Reasoning: <one line per candidate, very brief>\n"
        "PICK: <number>\n"
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
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
    """If any other category's hero covers the same underlying story as the front page
    hero, promote that category's next non-duplicate card to be its hero instead.
    Uses Claude for reliable semantic matching (string matching is too brittle for
    rewritten headlines). Mutates all_categories in place."""
    fp_headline = top_cat["hero"].get("headline", "")
    fp_key      = top_cat["category_key"]
    others      = [c for c in all_categories if c["category_key"] != fp_key]
    if not others or not fp_headline:
        return

    listing = "\n".join(f"{i+1}. {c['hero'].get('headline','')}" for i, c in enumerate(others))
    prompt = (
        f"The lead front-page story is:\n\"{fp_headline}\"\n\n"
        f"Here are other section lead headlines:\n{listing}\n\n"
        "Which of these numbered headlines cover the SAME underlying event as the lead story? "
        "Same event means the same action by the same actors at the same time, even if worded "
        "completely differently (e.g. 'US strikes Iran' and 'US military hits Iranian launch site' "
        "are the same event).\n"
        "Return ONLY a JSON array of the numbers that are duplicates of the lead story. "
        "If none are duplicates, return []."
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        dupes = set(int(x) for x in json.loads(raw))
    except Exception as e:
        print(f"  Hero dedup failed ({e}), leaving heroes as-is")
        return

    for i, cat in enumerate(others):
        if (i + 1) in dupes:
            cards = cat.get("cards", [])
            if cards:
                promoted = cards[0]
                cat["hero"] = {
                    "headline":      promoted.get("headline", ""),
                    "body":          promoted.get("body", ""),
                    "teaser":        promoted.get("teaser", ""),
                    "urgency_score": promoted.get("urgency_score", 0),
                    "published":     promoted.get("published", ""),
                    "image_url":     promoted.get("image_url", ""),
                    "image_credit":  promoted.get("image_credit", ""),
                    "link":          promoted.get("link", ""),
                }
                cat["cards"] = cards[1:]
                print(f"  Promoted next card to hero for {cat['category_label']} (was duplicate of front page hero)")


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
        "from different angles or with different wording (e.g. 'US strikes Iran' and "
        "'US military shoots down Iranian drones, hits launch site' are the SAME event). "
        "Identify every cluster of stories about the same event and keep ONLY the single "
        "best version of each. Drop all the others entirely. Two stories are the same event "
        "if they describe the same action, by the same actors, at the same time — regardless "
        "of how differently they are phrased.\n"
        + dedupe_clause +
        "\n"
        "PRIMARY signal: consequence and US relevance combined.\n"
        "SECONDARY signal: recency — edited timestamps do not make old stories new.\n"
        "Apply this weighting:\n"
        "1. Major foreign policy events (military action, peace deals, sanctions, treaty changes), especially involving oil/trade routes or major allies: TOP TIER — these affect millions and reshape global affairs\n"
        "2. Direct US impact on millions of Americans (economy-wide policy, national security incidents, major Supreme Court rulings, mass casualties): very high\n"
        "3. Significant domestic political developments (major legislation, executive actions with broad impact, presidential decisions): high\n"
        "4. Major business stories that affect consumers/economy broadly (Fed decisions, major industry collapses, jobs reports): high\n"
        "5. Company-specific news (funding rounds, single-company earnings, executive changes, IPO plans): MEDIUM — even huge funding rounds for private companies rank BELOW major foreign policy or national news. A $10B Anthropic round is less important than a US-Iran de-escalation deal.\n"
        "5b. Foreign economic indicators (China factory/PMI data, foreign GDP, foreign central bank moves): LOWER for a US audience unless they trigger an immediate, named US market reaction. 'China factory activity contracts' is a routine indicator that interests economists but should NOT be a top card on a US front page — rank it well below US domestic news, US policy, and major US-relevant world events.\n"
        "6. International tragedies with no direct US connection: belong in World but should NOT lead. Rank below any US-relevant story.\n"
        "7. Follow-up stories: rank below genuinely new stories\n"
        "8. Sports, entertainment: rank below policy and crisis stories unless exceptionally significant\n"
        "When two stories seem equally important, use recency as a tiebreaker.\n\n"
        f"{stories_text}\n\n"
        "Return ONLY a JSON array of the original numbers, in ranked order, most important first, "
        "with all duplicates removed (only the best version of each distinct event included).\n"
        "Example: [4, 1, 12, 7]"
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
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
        preview    = hero.get("body", "")[:380].rstrip()
        paragraphs = make_paragraphs(hero.get("body", ""))
        img_url    = hero.get("image_url", "")
        img_credit = hero.get("image_credit", "")
        credit_html = f'<figcaption class="img-credit">Photo: {img_credit}</figcaption>' if img_url and img_credit else ""
        img_html    = f'<figure class="hero-image-wrap"><img class="hero-image" src="{img_url}" alt="" loading="lazy">{credit_html}</figure>' if img_url else ""
        pub_time    = hero.get("published", "")
        display     = "" if visible else ' style="display:none"'
        fade        = " fade-in" if visible else ""
        archive     = load_archive(OUTPUT_DIR / "archive.json")
        matched     = find_matching_entry(hero.get("headline",""), archive, hero.get("link",""))
        if matched:
            slug = matched["slug"]
        else:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            slug  = f"{today}-{slugify(hero.get('headline', ''))}"
        article_url = f"{SITE_URL}/articles/{slug}.html"
        section_label = ""
        if cat_key in SECTION_LABELS:
            seo_text  = SECTION_LABELS[cat_key]
            label_cls = "county-section-label" if cat_key in COUNTY_KEYS else "topic-section-label"
            section_label = f'<div class="{label_cls}"><h2 class="county-label-text">{seo_text}</h2></div>'
        hl_escaped = hero["headline"].replace('"', "&quot;")
        return f"""
    <section class="hero{fade}" data-cat-hero="{cat_key}"{display}>
      {section_label}
      <div class="hero-inner">
        {img_html}
        <span class="tag">{cat_label}</span>
        <h1>{hero["headline"]}</h1>
        <p class="hero-summary">{preview}...</p>
        <div class="hero-foot">
          <span class="meta">{pub_time}</span>
          <button class="expand-btn" onclick="toggleExpand(this)">Continue reading &darr;</button>
        </div>
        <div class="article-expand hero-expand">
          <div class="hero-expand-body">{paragraphs}</div>
          <div class="article-actions">
            <button class="share-btn" data-headline="{hl_escaped}" data-url="{article_url}" onclick="shareArticle(this)">Share &#8599;</button>
            <button class="collapse-btn" onclick="collapseThis(this)">Close &uarr;</button>
          </div>
        </div>
      </div>
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

    all_cards_pool.sort(key=lambda c: int(c.get("urgency_score", 0) or 0), reverse=True)
    topnews     = global_rank(all_cards_pool, dedupe_against=top_cat["hero"].get("headline", ""))
    topnews_ids = {id(c) for c in topnews}
    remaining   = [c for c in all_cards_pool if id(c) not in topnews_ids]
    all_cards_display = topnews + remaining

    support_card = """
      <div class="article-card support-card fade-in" data-cat="all" data-support-card="true">
        <span class="card-tag support-card-tag">Advertise</span>
        <h2 class="card-headline support-card-headline">Reach Treasure Coast readers every day.</h2>
        <p class="card-summary">Your business alongside local news for Martin, St. Lucie &amp; Indian River counties. No algorithms. Just local readers.</p>
        <div class="card-foot">
          <a href="/advertise.html" class="support-card-btn">Get in touch &rarr;</a>
        </div>
      </div>"""

    cards_html = ""
    for i, card in enumerate(all_cards_display):
        if i == 2:
            cards_html += support_card
        teaser          = card.get("teaser", card.get("summary", ""))
        body            = card.get("body", card.get("summary", ""))
        card_paragraphs = make_paragraphs(body)
        ck              = card.get("cat_key", "all")
        cl              = card.get("cat_label", "")
        card_time       = card.get("published", "")
        topnews_attr    = ' data-topnews="true"' if id(card) in topnews_ids else ""
        card_hl_esc = card["headline"].replace('"', "&quot;")
        card_link   = card.get("link", "")
        read_more   = f'<a href="{card_link}" target="_blank" rel="noopener" class="read-source-link">Read full story &#8599;</a>' if card_link else ""
        cards_html += f"""
      <div class="article-card fade-in" data-cat="{ck}"{topnews_attr}>
        <span class="card-tag">{cl}</span>
        <h2 class="card-headline">{card["headline"]}</h2>
        <p class="card-summary">{teaser}</p>
        <div class="card-foot">
          <span class="card-time">{card_time}</span>
          <button class="expand-btn" onclick="toggleExpand(this)">Continue reading &darr;</button>
        </div>
        <div class="article-expand">
          <div class="card-expand-body">{card_paragraphs}</div>
          <div class="article-actions">
            <button class="share-btn" data-headline="{card_hl_esc}" onclick="shareArticle(this)">Share &#8599;</button>
            {read_more}
            <button class="collapse-btn" onclick="collapseThis(this)">Close &uarr;</button>
          </div>
        </div>
      </div>"""

    # Header/nav should be stable even if a category fails to generate content in a run.
    # Build nav from the master CATEGORIES config, not all_categories.
    nav_buttons = "\n        ".join(
        ['<button class="cat-btn active" data-cat="all">Top News</button>'] +
        [
            f'<button class="cat-btn" data-cat="{cat_key}">{cat_config["label"]}</button>'
            for cat_key, cat_config in CATEGORIES.items()
        ]
    )

    _head   = _page_head(
        "Treasure Coast Today | Local News for Martin, St. Lucie & Indian River County",
        "Local news for the Treasure Coast. Updated 4 times daily.",
    )
    _footer = _page_footer()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{_head}
</head>
<body>
  <header>
    <div class="header-inner">
      <div class="header-top">
        <a href="/" class="wordmark">Treasure Coast Today</a>
      </div>
      <nav class="category-nav">
        {nav_buttons}
        <a href="/archive.html" class="cat-btn" style="text-decoration:none">Archive</a>
        <a href="/events.html" class="cat-btn" style="text-decoration:none">Events</a>
      </nav>
      <div class="header-actions">
        <a href="/advertise.html" class="support-btn" style="text-decoration:none">Advertise</a>
      </div>
    </div>
  </header>
  <main>
    {heroes_html}
    <div class="articles-grid" id="articlesGrid">
      {cards_html}
    </div>
  </main>
{_footer}
</body>
</html>"""


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:80].strip("-")


def load_archive(archive_path):
    try:
        if archive_path.exists():
            return json.loads(archive_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def render_article_page(hero, category_label, category_key, pub_date, slug):
    """Render a permanent article page for a single TCT story."""
    description = (hero.get("teaser") or hero.get("body", "")[:155]).replace('"', '')
    image_url   = hero.get("image_url") or f"{SITE_URL}/social-card.png"
    structured_data = {
        "@context": "https://schema.org",
        "@type":    "NewsArticle",
        "headline": hero.get("headline", ""),
        "description": description,
        "image":    image_url,
        "datePublished": pub_date,
        "author":    {"@type": "Organization", "name": SITE_NAME},
        "publisher": {
            "@type": "Organization",
            "name":  SITE_NAME,
            "logo":  {"@type": "ImageObject", "url": f"{SITE_URL}/favicon.svg"},
        },
        "mainEntityOfPage": f"{SITE_URL}/articles/{slug}.html",
    }
    import json as _json
    schema_tag = f'  <script type="application/ld+json">{_json.dumps(structured_data)}</script>'
    body       = make_paragraphs(hero.get("body", ""))
    img_html   = ""
    if hero.get("image_url"):
        credit   = f'<figcaption class="img-credit">Photo: {hero["image_credit"]}</figcaption>' if hero.get("image_credit") else ""
        img_html = f'<figure class="article-hero-image"><img src="{hero["image_url"]}" alt="{hero["headline"]}" loading="eager">{credit}</figure>'

    head   = _page_head(
        f"{hero['headline']} — Treasure Coast Today",
        description,
        f"/articles/{slug}.html",
        structured_data=structured_data,
    )
    header = _page_header(active=category_key)
    footer = _page_footer()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
  <style>
    .article-wrap {{ max-width: 740px; margin: 0 auto; padding: 40px 24px 80px; }}
    .article-meta {{ display: flex; align-items: center; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }}
    .article-category {{ font-size: 10px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--accent); }}
    .article-date {{ font-size: 11px; color: var(--text-muted); }}
    .article-headline {{ font-family: "Fraunces", serif; font-size: clamp(26px, 4vw, 42px); font-weight: 600; line-height: 1.15; letter-spacing: -.02em; color: var(--text); margin-bottom: 24px; }}
    .article-hero-image {{ margin: 0 0 28px; }}
    .article-hero-image img {{ width: 100%; max-height: 420px; object-fit: cover; border-radius: 10px; display: block; }}
    .article-body p {{ font-size: 17px; line-height: 1.8; color: var(--text-secondary); margin-bottom: 20px; }}
    .article-back {{ display: inline-block; font-size: 13px; color: var(--accent); text-decoration: none; margin-bottom: 32px; font-weight: 500; }}
    .article-back:hover {{ opacity: .7; }}
    .article-divider {{ border: none; border-top: 1px solid var(--border); margin: 40px 0; }}
    .article-more {{ font-family: "Fraunces", serif; font-size: 20px; font-weight: 500; color: var(--text); margin-bottom: 16px; }}
    .article-more-link {{ display: inline-block; color: var(--accent); font-size: 14px; font-weight: 500; text-decoration: none; }}
    .article-more-link:hover {{ opacity: .7; }}
  </style>
</head>
<body>
{header}
  <main>
    <div class="article-wrap">
      <a href="/" class="article-back">&larr; Back to Treasure Coast Today</a>
      <div class="article-meta">
        <span class="article-category">{category_label}</span>
        <span class="article-date">{pub_date}</span>
      </div>
      <h1 class="article-headline">{hero["headline"]}</h1>
      {img_html}
      <div class="article-body">{body}</div>
      <hr class="article-divider">
      <p class="article-more">More local news</p>
      <a href="/?cat={category_key}" class="article-more-link">More {category_label} &rarr;</a>
    </div>
  </main>
{footer}
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


def update_sitemap(archive_entries):
    now_str = datetime.utcnow().strftime("%Y-%m-%d")
    static = f"""  <url>
    <loc>{SITE_URL}/</loc>
    <changefreq>hourly</changefreq>
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
    <loc>{SITE_URL}/privacy.html</loc>
    <priority>0.3</priority>
  </url>
  <url>
    <loc>{SITE_URL}/terms.html</loc>
    <priority>0.3</priority>
  </url>"""
    article_urls = "".join(f"""
  <url>
    <loc>{SITE_URL}/articles/{e['slug']}.html</loc>
    <priority>0.7</priority>
    <lastmod>{e.get('lastmod') or e['date']}</lastmod>
  </url>""" for e in archive_entries)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{static}
{article_urls}
</urlset>"""


def update_news_sitemap(archive_entries):
    """Google News sitemap — only articles from last 2 days."""
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")
    recent = [e for e in archive_entries if e.get("date","") >= cutoff]
    news_urls = ""
    for e in recent:
        pub_date = f"{e['date']}T00:00:00Z"
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
                 "coast","martin","lucie","indian","river","beach","port","city","news"}

def _sig_tokens(text):
    return frozenset(w.lower().strip(".,;:()") for w in text.split()
                     if len(w) > 3 and w.lower() not in ARCHIVE_STOPS)

def _is_duplicate_headline(headline, existing_token_sets):
    new_tok = _sig_tokens(headline)
    if len(new_tok) < 3:
        return False
    for ex_tok in existing_token_sets:
        if len(new_tok & ex_tok) >= 4:
            return True
    return False


def find_matching_entry(headline, archive, source_url=""):
    """Find an existing archive entry for this story using two-tier matching:
    1. source_url exact match — only when URL has a specific article path
    2. fuzzy headline match — catches rewrites and same story from different feeds
    Returns the matching entry dict or None."""
    if source_url:
        def norm_url(u):
            return re.sub(r"[?#].*$", "", u.strip().rstrip("/").lower())
        norm_src = norm_url(source_url)
        path_part = re.sub(r"^https?://[^/]+", "", norm_src)
        if len(path_part) > 10:
            for entry in archive:
                if entry.get("source_url") and norm_url(entry["source_url"]) == norm_src:
                    return entry

    tok = _sig_tokens(headline)
    if len(tok) < 3:
        return None
    for entry in archive:
        if len(tok & _sig_tokens(entry["headline"])) >= 4:
            return entry
    return None



def _page_head(title, description, canonical_path="", structured_data=None):
    canonical = f"{SITE_URL}{canonical_path}" if canonical_path else SITE_URL
    schema = ""
    if structured_data:
        import json as _json
        schema = f'  <script type="application/ld+json">{_json.dumps(structured_data)}</script>'
    return f"""  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:type" content="website">
  <meta property="og:image" content="{SITE_URL}/og-image.png">
  <meta name="geo.region" content="US-FL">
  <meta name="geo.placename" content="Treasure Coast, Florida">
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/style.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,500;0,9..144,600;1,9..144,300&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500&display=swap" rel="stylesheet">
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
    return f"""  <header>
    <div class="header-inner">
      <div class="header-top">
        <a href="/" class="wordmark">Treasure Coast Today</a>
      </div>
      <nav class="category-nav">
        {cat_link("Top News", "/", "news")}
        {cat_link("Local Gov", "/?cat=local_gov", "local_gov")}
        {cat_link("Crime", "/?cat=crime", "crime")}
        {cat_link("Business", "/?cat=business", "business")}
        {cat_link("Sports", "/?cat=sports", "sports")}
        {cat_link("Things To Do", "/?cat=things_to_do", "things_to_do")}
        {cat_link("Florida", "/?cat=florida", "florida")}
        {cat_link("Martin Co.", "/?cat=martin", "martin")}
        {cat_link("St. Lucie Co.", "/?cat=st_lucie", "st_lucie")}
        {cat_link("Indian River Co.", "/?cat=indian_river", "indian_river")}
        {cat_link("Archive", "/archive.html", "archive")}
        {cat_link("Events", "/events.html", "events")}
      </nav>
      <div class="header-actions">
        <a href="/advertise.html" class="support-btn" style="text-decoration:none">Advertise</a>
      </div>
    </div>
  </header>"""


def _page_footer():
    return """  <footer>
    <div class="footer-inner">
      <span class="footer-wordmark">Treasure Coast Today</span>
      <span class="footer-tagline">Local news for Martin, St. Lucie &amp; Indian River counties.</span>
      <div class="footer-links">
        <a href="/about.html">About</a>
        <a href="/archive.html">Archive</a>
        <a href="/events.html">Events</a>
        <a href="/advertise.html">Advertise</a>
        <a href="/privacy.html">Privacy</a>
        <a href="mailto:hello@treasurecoast.today">Contact</a>
      </div>
    </div>
  </footer>
  <script src="/main.js"></script>"""


def render_about_page():
    head   = _page_head("About — Treasure Coast Today", "Treasure Coast Today delivers local news for Martin, St. Lucie, and Indian River counties four times a day.", "/about.html")
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
    .about-contact {{ display: inline-block; margin-top: 8px; color: var(--accent); font-weight: 500; }}
  </style>
</head>
<body>
{header}
  <main>
    <div class="about-wrap">
      <span class="about-eyebrow">About</span>
      <h1 class="about-headline">Local news for Florida's Treasure Coast.</h1>
      <div class="about-body">
        <p>Treasure Coast Today is a local news source covering Martin County, St. Lucie County, and Indian River County, Florida. We bring residents the stories that matter most close to home.</p>
        <p>Our focus is simple: the news that actually affects the people who live and work here. From county commission decisions in Stuart to development in Port St. Lucie, school district news in Vero Beach to public safety in Fort Pierce.</p>
        <h2>Coverage area</h2>
        <p><strong>Martin County</strong> — Stuart, Jensen Beach, Palm City, Hobe Sound, Port Salerno.</p>
        <p><strong>St. Lucie County</strong> — Port St. Lucie, Fort Pierce, St. Lucie West.</p>
        <p><strong>Indian River County</strong> — Vero Beach, Sebastian, Fellsmere.</p>
        <h2>Advertise with us</h2>
        <p>Connect your business with engaged local readers. <a href="/advertise.html" class="about-contact">Learn more &rarr;</a></p>
        <hr class="about-divider">
        <h2>Get in touch</h2>
        <p><a href="mailto:hello@treasurecoast.today" class="about-contact">hello@treasurecoast.today</a></p>
      </div>
    </div>
  </main>
{footer}
</body>
</html>"""


def render_events_page():
    head   = _page_head("Events — Treasure Coast Today", "Treasure Coast events coming soon.", "/events.html")
    header = _page_header(active="events")
    footer = _page_footer()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
  <style>
    .cs-wrap {{ max-width: 600px; margin: 80px auto; padding: 0 24px; text-align: center; }}
    .cs-eyebrow {{ font-size: 11px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: var(--accent); display: block; margin-bottom: 16px; }}
    .cs-headline {{ font-family: 'Fraunces', serif; font-size: clamp(28px, 5vw, 44px); font-weight: 600; line-height: 1.15; color: var(--text); margin: 0 0 20px; }}
    .cs-sub {{ font-size: 16px; color: var(--text-secondary); line-height: 1.65; margin: 0 0 40px; }}
    .cs-form {{ display: flex; gap: 10px; max-width: 440px; margin: 0 auto 16px; }}
    .cs-input {{ flex: 1; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 12px 16px; font-family: 'DM Sans', sans-serif; font-size: 14px; color: var(--text); outline: none; }}
    .cs-input:focus {{ border-color: var(--accent); }}
    .cs-btn {{ background: var(--accent); color: white; border: none; border-radius: 8px; padding: 12px 22px; font-family: 'DM Sans', sans-serif; font-size: 14px; font-weight: 600; cursor: pointer; }}
    .cs-fine {{ font-size: 12px; color: var(--text-secondary); }}
    .cs-success {{ display: none; color: var(--accent); font-size: 15px; font-weight: 500; margin-top: 12px; }}
  </style>
</head>
<body>
{header}
  <main>
    <div class="cs-wrap">
      <span class="cs-eyebrow">Coming Soon</span>
      <h1 class="cs-headline">List your Treasure Coast event for free.</h1>
      <p class="cs-sub">We're building a local events calendar. Leave your email and we'll notify you when it launches.</p>
      <form class="cs-form" id="csForm" action="https://formspree.io/f/mqejrpdv" method="POST">
        <input type="hidden" name="_subject" value="Events calendar interest">
        <input class="cs-input" type="email" name="email" placeholder="your@email.com" required>
        <button class="cs-btn" type="submit">Notify me</button>
      </form>
      <p class="cs-fine">No spam. Just a heads-up when the calendar is live.</p>
      <p class="cs-success" id="csSuccess">You're on the list!</p>
    </div>
  </main>
{footer}
  <script>
    const f=document.getElementById('csForm'),s=document.getElementById('csSuccess');
    f.addEventListener('submit',async(e)=>{{
      e.preventDefault();
      const r=await fetch(f.action,{{method:'POST',body:new FormData(f),headers:{{'Accept':'application/json'}}}});
      if(r.ok){{f.style.display='none';s.style.display='block';}}
    }});
  </script>
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
    .adv-check input[type="checkbox"] {{ width: 16px; height: 16px; min-width: 16px; accent-color: var(--accent); cursor: pointer; padding: 0; }}
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
      <p class="adv-sub">Treasure Coast Today delivers local news to Martin, St. Lucie, and Indian River County residents four times daily. Your business appears alongside stories they actually read.</p>
      <div class="adv-stats">
        <div class="adv-stat"><span class="adv-stat-num">706K+</span><span class="adv-stat-label">Residents across Martin, St. Lucie &amp; Indian River counties</span></div>
        <div class="adv-stat"><span class="adv-stat-num">100%</span><span class="adv-stat-label">No paywall — every reader sees your ad, every time</span></div>
        <div class="adv-stat"><span class="adv-stat-num">Top 5</span><span class="adv-stat-label">Fastest-growing metro in the U.S. — new residents every day</span></div>
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
            <label class="adv-check"><input type="checkbox" name="counties" value="Martin County"><span>Martin County (Stuart, Jensen Beach, Palm City, Hobe Sound)</span></label>
            <label class="adv-check"><input type="checkbox" name="counties" value="St. Lucie County"><span>St. Lucie County (Port St. Lucie, Fort Pierce)</span></label>
            <label class="adv-check"><input type="checkbox" name="counties" value="Indian River County"><span>Indian River County (Vero Beach, Sebastian)</span></label>
            <label class="adv-check"><input type="checkbox" name="counties" value="All three counties"><span>All three counties</span></label>
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


def write_archives(all_categories, top_cat):
    articles_dir = OUTPUT_DIR / "articles"
    archive_path = OUTPUT_DIR / "archive.json"
    articles_dir.mkdir(exist_ok=True)

    archive       = load_archive(archive_path)
    today         = datetime.utcnow().strftime("%Y-%m-%d")
    new_count     = 0
    updated_count = 0
    this_run_token_sets = []

    heroes = [(top_cat["category_key"], top_cat["category_label"], top_cat["hero"])]
    for cat in all_categories:
        if cat["category_key"] != top_cat["category_key"]:
            heroes.append((cat["category_key"], cat["category_label"], cat["hero"]))

    for cat_key, cat_label, hero in heroes:
        headline = hero.get("headline", "").strip()
        if not headline:
            continue

        source_url = hero.get("link", "")
        existing   = find_matching_entry(headline, archive, source_url)

        # Skip cross-category duplicates within the same run
        if not existing and _is_duplicate_headline(headline, this_run_token_sets):
            print(f"  Skipped cross-category duplicate: {headline[:60]}")
            continue

        this_run_token_sets.append(_sig_tokens(headline))

        if existing:
            # Same story — update existing page in place, keep original URL
            slug = existing["slug"]
            (articles_dir / f"{slug}.html").write_text(
                render_article_page(hero, cat_label, cat_key, today, slug), encoding="utf-8"
            )
            existing["headline"]  = headline
            existing["teaser"]    = hero.get("teaser","") or hero.get("body","")[:180]
            existing["image_url"] = hero.get("image_url","")
            existing["lastmod"]   = today
            if source_url:
                existing["source_url"] = source_url
            updated_count += 1
        else:
            # New story — create new page
            existing_slugs = {e["slug"] for e in archive}
            base_slug = f"{today}-{slugify(headline)}"
            slug = base_slug
            counter = 1
            while slug in existing_slugs:
                slug = f"{base_slug}-{counter}"; counter += 1
            (articles_dir / f"{slug}.html").write_text(
                render_article_page(hero, cat_label, cat_key, today, slug), encoding="utf-8"
            )
            archive.append({
                "slug": slug, "headline": headline,
                "teaser": hero.get("teaser","") or hero.get("body","")[:180],
                "category_key": cat_key, "category_label": cat_label,
                "date": today, "lastmod": today,
                "image_url": hero.get("image_url",""),
            })
            new_count += 1

    archive_path.write_text(json.dumps(archive, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "archive.html").write_text(render_archive_page(archive), encoding="utf-8")
    (OUTPUT_DIR / "sitemap.xml").write_text(update_sitemap(archive), encoding="utf-8")
    (OUTPUT_DIR / "news-sitemap.xml").write_text(update_news_sitemap(archive), encoding="utf-8")
    print(f"  Archived {new_count} new, updated {updated_count} existing ({len(archive)} total)")

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
        for fut in as_completed(futures, timeout=40):
            try:
                url, entries = fut.result(timeout=10)
                feed_cache[url] = entries
            except Exception as e:
                feed_cache[futures[fut]] = []
                print(f"  Feed timeout ({futures[fut][:60]}): {e}")

    print(f"  Feed cache: {sum(len(v) for v in feed_cache.values())} total entries across {len(feed_cache)} feeds")

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

        headlines = filter_category_headlines(cat_key, headlines, target=HEADLINES_PER_CATEGORY, min_keep=6)

        print(f"  {len(headlines)} headlines fetched")
        try:
            data = generate_category_content(cat_key, cat_config["label"], headlines)

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

            # Stale hero demotion
            from email.utils import parsedate_to_datetime as _parse_pub
            from datetime import timezone as _tz3
            _now3 = datetime.now(_tz3.utc)
            _raw_pub = data["hero"].get("published_raw","")
            if _raw_pub:
                try:
                    _dt  = _parse_pub(_raw_pub).astimezone(_tz3.utc)
                    _age = (_now3 - _dt).total_seconds() / 3600
                    if _age > 24 and data.get("cards"):
                        print(f"  Demoting stale hero ({_age:.0f}h old), promoting next card for {cat_config['label']}")
                        old_hero = data["hero"]
                        data["hero"]  = data["cards"][0]
                        data["cards"] = data["cards"][1:] + [old_hero]
                except Exception:
                    pass

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

        except Exception as e:
            import traceback
            print(f"  Error for {cat_config['label']}: {e}")
            print(traceback.format_exc())
            continue

    if not all_categories:
        print("No categories generated. Aborting.")
        return

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

    # Render and write all pages
    index_html = render_index(all_categories, top_cat)
    (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")

    # Archive
    write_archives(all_categories, top_cat)

    # data.json
    write_data_json(all_categories, top_cat)

    # Static pages
    (OUTPUT_DIR / "events.html").write_text(render_events_page(), encoding="utf-8")
    (OUTPUT_DIR / "about.html").write_text(render_about_page(), encoding="utf-8")
    (OUTPUT_DIR / "advertise.html").write_text(render_advertise_page(), encoding="utf-8")

    print(f"Done. {len(all_categories)} categories written.")


if __name__ == "__main__":
    main()
