"""
Treasure Coast Today - news generation pipeline
Covers Martin, St. Lucie, and Indian River counties.
Runs 4x/day via cron-job.org -> GitHub Actions.
"""

import os
import json
import re
import feedparser
import requests
import anthropic
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# -- CONFIG --

SITE_NAME    = "Treasure Coast Today"
SITE_URL     = "https://treasurecoast.today"
SITE_TAGLINE = "Your Treasure Coast, every day."
ACCENT_LIGHT = "#0A7075"
ACCENT_DARK  = "#14969C"
BG_LIGHT     = "#F7FAFA"
BG_DARK      = "#090F0F"

# Topic categories + county categories
CATEGORIES = {
    "local_gov": {
        "label": "Local Government",
        "front_page_cap": 10,
        "feeds": [
            "https://www.wptv.com/news/political.rss",
            "https://www.wptv.com/news/local-news/investigations.rss",
            "https://news.google.com/rss/search?q=martin+county+florida+commission+budget+zoning+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=st+lucie+county+florida+commission+council+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=indian+river+county+florida+commission+council+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=stuart+florida+city+council+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=port+st+lucie+city+council+mayor+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=fort+pierce+city+commission+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=vero+beach+city+council+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
        ],
    },
    "crime": {
        "label": "Crime & Safety",
        "front_page_cap": 8,
        "feeds": [
            "https://www.wptv.com/news/local-news.rss",
            "https://news.google.com/rss/search?q=martin+county+florida+crime+arrest+sheriff+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=st+lucie+county+florida+crime+arrest+police+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=indian+river+county+florida+crime+arrest+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=treasure+coast+florida+crime+safety+shooting+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=port+st+lucie+police+arrest+crime+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=fort+pierce+police+crime+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
        ],
    },
    "business": {
        "label": "Business & Development",
        "front_page_cap": 8,
        "feeds": [
            "https://news.google.com/rss/search?q=martin+county+florida+business+development+real+estate+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=st+lucie+county+florida+business+jobs+development+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=indian+river+county+florida+business+development+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=treasure+coast+florida+new+business+restaurant+opening+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=port+st+lucie+real+estate+development+construction+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=stuart+florida+business+downtown+development+when:2d&hl=en-US&gl=US&ceid=US:en",
        ],
    },
    "schools": {
        "label": "Schools",
        "front_page_cap": 7,
        "feeds": [
            "https://news.google.com/rss/search?q=martin+county+school+district+florida+when:3d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=st+lucie+county+school+district+florida+when:3d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=indian+river+county+school+district+florida+when:3d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=treasure+coast+florida+school+education+when:3d&hl=en-US&gl=US&ceid=US:en",
        ],
    },
    "sports": {
        "label": "Sports",
        "front_page_cap": 6,
        "feeds": [
            "https://news.google.com/rss/search?q=martin+county+florida+high+school+sports+when:3d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=st+lucie+county+florida+sports+high+school+when:3d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=treasure+coast+florida+sports+when:3d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=st+lucie+mets+florida+when:7d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=vero+beach+dodgers+sports+florida+when:7d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=jensen+beach+south+fork+martin+county+sports+when:7d&hl=en-US&gl=US&ceid=US:en",
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
            "https://news.google.com/rss/search?q=florida+news+when:1d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=florida+legislature+governor+desantis+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=florida+economy+housing+insurance+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://feeds.sun-sentinel.com/sun-sentinel/news/florida",
            "https://www.miamiherald.com/news/state/florida/rss.xml",
            "https://floridapolitics.com/feed/",
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
            "https://news.google.com/rss/search?q=st+lucie+west+florida+when:3d&hl=en-US&gl=US&ceid=US:en",
        ],
    },
    "indian_river": {
        "label": "Indian River County",
        "front_page_hero": False,
        "feeds": [
            "https://www.wptv.com/news/region-indian-river-county.rss",
            "https://news.google.com/rss/search?q=indian+river+county+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=vero+beach+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=sebastian+florida+when:2d&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=fellsmere+florida+when:3d&hl=en-US&gl=US&ceid=US:en",
        ],
    },
}

HEADLINES_PER_CATEGORY = 12
CARDS_PER_CATEGORY     = 6
OUTPUT_DIR             = Path(__file__).parent.parent

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Image sources — local Florida outlets + broad aggregators
IMAGE_BANK_FEEDS = [
    "https://www.wptv.com/news/local-news.rss",
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

# -- UTILITIES --

def now_et():
    from datetime import timezone, timedelta
    utc = datetime.now(timezone.utc)
    et  = utc - timedelta(hours=5)  # approximation; DST ignored for display
    return et.strftime("%-I:%M %p ET")

def get_image_credit(source_url):
    if not source_url:
        return ""
    sl = source_url.lower()
    for domain, name in FEED_PUBLISHER_MAP.items():
        if domain in sl:
            return name
    return ""

def extract_image(entry):
    def valid(u):
        if not u or len(u) < 15: return False
        return not any(x in u.lower() for x in ["1x1","pixel","spacer","tracking","data:"])
    for t in (getattr(entry,"media_thumbnail",None) or []):
        if isinstance(t,dict) and valid(t.get("url","")): return t["url"]
    for m in (getattr(entry,"media_content",None) or []):
        if not isinstance(m,dict): continue
        u = m.get("url","")
        if valid(u) and ("image" in m.get("type","") or any(u.lower().endswith(e) for e in (".jpg",".jpeg",".png",".webp"))): return u
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
    for match in re.finditer(r'<img[^>]+src=["\']([^"\']{20,})["\']',html):
        u = match.group(1)
        if valid(u): return u
    return ""

# Category-appropriate Pexels search queries — used as a last-resort image so
# every hero has a clean, relevant, license-free image even when no real photo
# was found. These are intentionally generic and neutral.
PEXELS_QUERY_MAP = {
    "local_gov":    "florida city hall government building",
    "crime":        "police car lights night",
    "business":     "florida main street storefront",
    "schools":      "school classroom students",
    "sports":       "high school stadium field",
    "things_to_do": "florida beach palm trees",
    "florida":      "florida state capitol palm",
    "martin":       "stuart florida waterfront",
    "st_lucie":     "port st lucie florida",
    "indian_river": "vero beach florida coast",
    "all":          "treasure coast florida aerial",
}

_pexels_used = set()

def fetch_pexels_image(category_key):
    """Last-resort image: pull a relevant, license-free stock photo from Pexels
    so no hero is ever imageless. Returns (image_url, credit) or ("", "")."""
    api_key = os.environ.get("PEXELS_API_KEY", "qeDQdH5sqDXv44pAj80ePVC4XdPohwgOM2xczaCgDdLUD5DJbFHOZxYF")
    if not api_key:
        print(f"  Pexels: no API key")
        return "", ""
    query = PEXELS_QUERY_MAP.get(category_key, PEXELS_QUERY_MAP["all"])
    print(f"  Pexels query: '{query}'")
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            params={"query": query, "per_page": 15, "orientation": "landscape"},
            headers={"Authorization": api_key},
            timeout=10,
        )
        print(f"  Pexels status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"  Pexels error: {resp.text[:200]}")
            return "", ""
        photos = resp.json().get("photos", [])
        for p in photos:
            img = p.get("src", {}).get("large", "") or p.get("src", {}).get("medium", "")
            if img and img not in _pexels_used:
                _pexels_used.add(img)
                photographer = p.get("photographer", "Pexels")
                return img, f"{photographer} / Pexels"
        # If all were used already, just take the first
        if photos:
            img = photos[0].get("src", {}).get("large", "")
            if img:
                return img, f"{photos[0].get('photographer','Pexels')} / Pexels"
        return "", ""
    except Exception:
        return "", ""

def build_image_bank():
    bank = []
    for url in IMAGE_BANK_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:60]:
                img = extract_image(entry)
                if not img:
                    link = entry.get("link", "") or getattr(entry, "link", "")
                    if link and "news.google.com" not in link:
                        img = fetch_og_image(link)
                if img:
                    bank.append({
                        "title":     entry.get("title", ""),
                        "image_url": img,
                        "source":    url,
                    })
        except Exception:
            pass
    print(f"  Image bank: {len(bank)} entries")
    return bank

def tokens(text):
    stops = {"the","a","an","in","of","for","to","and","or","on","at","is","was","are",
             "were","that","this","with","from","have","been","after","over","into","says",
             "said","will","than","more","also","when","s",
             # Geographic/common terms that appear in nearly every Treasure Coast headline —
             # these carry no story-specific signal here, so matching on them produces
             # false positives (two unrelated stories both mention "Martin County Florida").
             "county","florida","treasure","coast","martin","lucie","indian","river",
             "beach","port","stuart","pierce","vero","jensen","palm","city","sebastian",
             "hobe","sound","salerno","fellsmere","news","area","local","new","report",
             "police","man","woman","year","years","day","week","county's"}
    return set(w.lower().strip(".,;:()") for w in text.split() if len(w)>3 and w.lower() not in stops)

def match_image(headline, image_bank, cat_key=None, used_images=None):
    """Conservative image-bank match.

    This is intentionally strict because a missing image is better than a wrong
    image. We only accept a bank image when the bank article title has a strong
    token overlap with the story headline/context. Previously this accepted loose
    two-token matches and could reuse the same unrelated image across multiple
    heroes.
    """
    used_images = used_images or set()
    hw = tokens(headline)
    # If the headline has almost no distinctive tokens left after filtering, don't
    # risk a match — there's nothing meaningful to match on.
    if len(hw) < 2:
        return "", ""
    best_score, best_img, best_credit = 0, "", ""

    for entry in image_bank:
        img = entry.get("image_url", "")
        if canonical_image_url(img) in used_images:
            continue
        et = tokens(entry.get("title", ""))
        overlap = len(hw & et)
        # Require at least 3 shared meaningful (non-geographic) words.
        if overlap > best_score and overlap >= 3:
            best_score  = overlap
            best_img    = img
            best_credit = get_image_credit(entry.get("source",""))

    # Distinctive-token fallback for specific names/places like Wawa, Macy's, etc.
    # Now requires 2 shared DISTINCTIVE words AND that they be genuinely distinctive
    # (7+ chars, proper-noun-like), since common 6-char words caused false matches.
    if not best_img:
        distinctive = {w for w in hw if len(w) >= 7}
        if len(distinctive) >= 2:
            for entry in image_bank:
                img = entry.get("image_url", "")
                if canonical_image_url(img) in used_images:
                    continue
                et = {w for w in tokens(entry.get("title", "")) if len(w) >= 7}
                overlap = len(distinctive & et)
                if overlap > best_score and overlap >= 2:
                    best_score  = overlap
                    best_img    = img
                    best_credit = get_image_credit(entry.get("source",""))
    return best_img, best_credit

def fetch_og_image(url):
    if not url: return ""
    try:
        resp = requests.get(url, timeout=12, allow_redirects=True, headers={"User-Agent":"Mozilla/5.0 (compatible; TCTBot/1.0)"})
        if resp.status_code != 200: return ""
        html = resp.text[:200000]
        patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                img = m.group(1).strip()
                if img.startswith("http"): return img
        return ""
    except Exception:
        return ""

def fetch_article_text(url, max_chars=2500):
    """Fetch the readable body text of an article page so the model writes from
    real content instead of a thin RSS summary. Returns plain text (truncated)
    or empty string on any failure. Skips Google News redirect URLs."""
    if not url or "news.google.com" in url.lower():
        return ""
    try:
        resp = requests.get(url, timeout=5, allow_redirects=True,
                            headers={"User-Agent":"Mozilla/5.0 (compatible; TCTBot/1.0)"})
        if resp.status_code != 200:
            return ""
        html = resp.text
        # Prefer text inside <article> if present, else <p> tags from the body
        article_match = re.search(r"<article[^>]*>(.*?)</article>", html, re.DOTALL | re.IGNORECASE)
        scope = article_match.group(1) if article_match else html
        # Collect paragraph text
        paras = re.findall(r"<p[^>]*>(.*?)</p>", scope, re.DOTALL | re.IGNORECASE)
        text_parts = []
        for p in paras:
            clean = re.sub(r"<[^>]+>", "", p)           # strip nested tags
            clean = re.sub(r"&[a-z]+;", " ", clean)     # strip entities
            clean = re.sub(r"\s+", " ", clean).strip()
            # Skip boilerplate / junk paragraphs
            if len(clean) < 40:
                continue
            low = clean.lower()
            if any(junk in low for junk in ["subscribe", "sign up", "cookie", "advertisement",
                                            "all rights reserved", "terms of service", "privacy policy",
                                            "follow us", "newsletter"]):
                continue
            text_parts.append(clean)
            if sum(len(t) for t in text_parts) > max_chars:
                break
        return " ".join(text_parts)[:max_chars]
    except Exception:
        return ""



def extract_publisher_url(entry):
    """Return the publisher URL for Google News RSS entries when possible.
    Google News often stores the real publisher link inside the description HTML.
    Using the publisher URL lets us fetch the article's own og:image instead of
    relying on loose RSS thumbnails or unrelated image-bank matches.
    """
    link = entry.get("link", "") or getattr(entry, "link", "")
    if "news.google.com" not in link:
        return link

    html = ""
    for field in ["summary", "description"]:
        val = entry.get(field, "") or getattr(entry, field, "")
        if isinstance(val, list) and val:
            html = val[0].get("value", "") if isinstance(val[0], dict) else str(val[0])
        elif isinstance(val, str):
            html = val
        if html:
            break

    matches = re.findall(r'href=["\'](https?://(?!news\.google)[^"\']+)["\']', html)
    if matches:
        return matches[0]
    # Some Google News entries expose the source link in a <source url="..."> element
    # or via the entry.source attribute
    src = entry.get("source", "")
    if isinstance(src, dict):
        src_url = src.get("href", "") or src.get("url", "")
        if src_url and "news.google" not in src_url:
            return src_url
    return link

def canonical_image_url(url):
    if not url:
        return ""
    return re.sub(r"[?#].*$", "", url.strip())

def format_age(raw_pub):
    if not raw_pub: return ""
    try:
        from email.utils import parsedate_to_datetime
        from datetime import timezone, timedelta
        dt  = parsedate_to_datetime(raw_pub).astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        diff_mins = (now - dt).total_seconds() / 60
        if diff_mins < 60:   return f"{int(diff_mins)} minutes ago"
        if diff_mins < 120:  return "1 hour ago"
        if diff_mins < 1440: return f"{int(diff_mins/60)} hours ago"
        if diff_mins < 2880: return f"Yesterday, {dt.strftime('%-I:%M %p')} ET"
        return dt.strftime("%b %-d")
    except Exception:
        return raw_pub[:30] if raw_pub else ""

def strip_absence_language(text):
    if not text: return text
    absence_patterns = [
        "no information was","no details were","details were not","details have not",
        "has not been confirmed","was not disclosed","it remains unclear","it is unclear",
        "officials have not","has not responded","not immediately available","could not be reached",
        "no official statement","reporting is ongoing","investigation is ongoing",
    ]
    sentences = text.replace("\n\n","<<PARA>>").split(".")
    cleaned = [s for s in sentences if not any(p in s.lower() for p in absence_patterns)]
    return ".".join(cleaned).replace("<<PARA>>","\n\n").strip()

def strip_markdown(text, headline=""):
    if not text: return text
    text = re.sub(r"#{1,6}\s*","",text)
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}",r"\1",text)
    text = re.sub(r"_([^_]+)_",r"\1",text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)",r"\1",text)
    text = re.sub(r"^[-*]\s+","",text,flags=re.MULTILINE)
    text = re.sub(r"\n{3,}","\n\n",text).strip()
    for g in ["good morning.","good afternoon.","good evening."]:
        if text.lower().startswith(g):
            text = text[len(g):].lstrip(); break
    if headline:
        paragraphs = text.split("\n\n")
        if paragraphs:
            first = paragraphs[0].strip()
            if len(first.split()) < 20:
                hl_words = set(re.sub(r"[^a-z0-9 ]"," ",headline.lower()).split())
                p_words  = set(re.sub(r"[^a-z0-9 ]"," ",first.lower()).split())
                if len(hl_words & p_words) >= min(4,len(hl_words)//2):
                    text = "\n\n".join(paragraphs[1:]).strip()
    return text

def make_paragraphs(text):
    if not text: return ""
    paragraphs = text.split("\n\n")
    if len(paragraphs) == 1:
        paragraphs = text.split("\n")
    return "".join(f"<p>{p.strip()}</p>" for p in paragraphs if p.strip())

def fetch_headlines(feeds, limit=HEADLINES_PER_CATEGORY):
    seen, headlines = set(), []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = (entry.get("title") or "").strip()
                if not title or title in seen: continue
                seen.add(title)
                # Prefer the richest available field. WPTV and many RSS feeds put
                # the full article body in content:encoded / content, while summary
                # is just a blurb. Grab content FIRST, fall back to summary.
                summary = ""
                best_len = 0
                for field in ["content", "summary", "description"]:
                    val = entry.get(field, "") or getattr(entry, field, "")
                    if isinstance(val, list) and val:
                        candidate = val[0].get("value", "") if isinstance(val[0], dict) else str(val[0])
                    elif isinstance(val, str):
                        candidate = val
                    else:
                        candidate = ""
                    candidate = re.sub(r"<[^>]+>", " ", candidate)
                    candidate = re.sub(r"&[a-z]+;", " ", candidate)
                    candidate = re.sub(r"\s+", " ", candidate).strip()
                    # Keep the longest field — that's the one with the real content
                    if len(candidate) > best_len:
                        summary  = candidate[:3000]
                        best_len = len(candidate)
                pub = ""
                if hasattr(entry,"published"): pub = entry.published
                elif hasattr(entry,"updated"):  pub = entry.updated
                raw_link = entry.get("link","") or getattr(entry,"link","")
                link = extract_publisher_url(entry)
                img  = extract_image(entry)
                headlines.append({
                    "title":   title,
                    "summary": summary,
                    "published": pub,
                    "link":    link,
                    "image_url": img,
                    "image_from_google": "news.google.com" in raw_link.lower(),
                })
        except Exception as e:
            pass
    # Filter to 48 hours — REJECT stories with missing/unparseable dates
    # (Google News search queries often return old articles; bad dates = old content)
    from email.utils import parsedate_to_datetime
    from datetime import timezone
    now_utc = datetime.now(timezone.utc)
    def is_fresh(h):
        pub = h.get("published", "").strip()
        if not pub:
            return False  # No date = reject (don't assume fresh)
        try:
            dt = parsedate_to_datetime(pub).astimezone(timezone.utc)
            age_hours = (now_utc - dt).total_seconds() / 3600
            return age_hours <= 48
        except Exception:
            return False  # Unparseable date = reject
    fresh = [h for h in headlines if is_fresh(h)]
    result = fresh if len(fresh) >= 1 else headlines
    result = result[:limit]
    # Note: article text fetching via HTTP is disabled — it adds significant
    # run time (up to 70 fetches × 5s timeout = 350s worst case) and provides
    # minimal benefit since WPTV's full content is already in the RSS content
    # field (captured above), and Google News URLs are skipped anyway.
    return result

# -- CATEGORY CONTENT GENERATION --

LOCAL_SYSTEM_PROMPT = """You write factual local news articles for Treasure Coast Today, covering Martin, St. Lucie, and Indian River counties in Florida. Your readers live here — they care about what's happening in their towns, schools, and county government far more than national news. Always prioritize genuinely local stories over state or national ones. Write in plain direct English — no em dashes, no fluff, no absence language. Every sentence must be a confirmed fact from the provided headlines and summaries. Name specific towns, streets, facilities, and local officials when available. Towns include: Stuart, Jensen Beach, Palm City, Hobe Sound, Port Salerno, Port St. Lucie, Fort Pierce, Vero Beach, Sebastian, Fellsmere, and surrounding communities. IMPORTANT: Base every factual claim on the provided source text. You may write naturally and provide helpful context and clear explanation, but do NOT fabricate specific names, numbers, dates, direct quotes, or outcomes that are not in the source. Never write phrases like 'no further details are available' or 'details were not disclosed' — if you lack a specific detail, simply write around it and focus on what IS known. Always produce a complete, readable article."""

FLORIDA_SYSTEM_PROMPT = """You write factual news articles for the Florida section of Treasure Coast Today. Your readers are Treasure Coast residents who want to stay informed about statewide Florida news that affects them as Floridians. This section covers the whole state — legislation, courts, economy, environment, politics, weather, and major events anywhere in Florida. Do NOT artificially narrow to the Treasure Coast; this is the statewide section. Write in plain direct English — no em dashes, no fluff, no absence language. Every sentence must be a confirmed fact from the provided headlines and summaries. IMPORTANT: Base every factual claim on the provided source text. You may write naturally and provide helpful context and clear explanation, but do NOT fabricate specific names, numbers, dates, direct quotes, or outcomes that are not in the source. Never write phrases like 'no further details are available' or 'details were not disclosed' — if you lack a specific detail, simply write around it and focus on what IS known. Always produce a complete, readable article."""

def generate_category_content(category_key, category_label, headlines):
    def sanitize(text):
        if not text: return ""
        text = text.replace("\\", " ").replace('"', "'").replace("\n"," ").replace("\r"," ").replace("\t"," ")
        text = "".join(c for c in text if c.isprintable())
        text = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def hl_line(i, h):
        pub     = sanitize(h.get("published",""))
        pub_str = f" [pub:{pub}]" if pub else ""
        # Use fuller article text when we managed to fetch it, else the RSS summary
        content = h.get("article_text", "") or h.get("summary", "")
        return f"{i+1}. {sanitize(h.get('title',''))}{pub_str}\n   {sanitize(content)[:2800]}"

    headlines_text = "\n".join(hl_line(i,h) for i,h in enumerate(headlines))
    headlines_text = headlines_text.replace("\\","").encode("ascii","ignore").decode("ascii")

    is_florida = (category_key == "florida")
    system_prompt = FLORIDA_SYSTEM_PROMPT if is_florida else LOCAL_SYSTEM_PROMPT

    if is_florida:
        prompt = f"""Florida news headlines:

{headlines_text}

Tasks:
1. Pick the single most important/urgent Florida statewide story. Prioritize stories with broad impact across Florida — major legislation, court rulings, economic news, environmental decisions, significant crimes or disasters anywhere in the state. Do NOT favor Treasure Coast stories here; this is the statewide section.
2. Write an accurate Florida-focused headline. Name the specific Florida city, region, or institution when relevant.
3. Write a 380-430 word factual article in FOUR full paragraphs. Cover what happened, who is affected across Florida, and what happens next statewide. Do NOT write only two paragraphs.
4. For the next {CARDS_PER_CATEGORY} most important Florida stories write a teaser (one to two sentences) and a body of two to three full paragraphs. Write a complete, readable article that covers what happened, who is affected, and the broader context. Ground all specific facts (names, numbers, dates, quotes) in the source, but write naturally and provide useful context and explanation. Never write 'no further details available' — always produce a substantive article. Include an urgency_score (1-10). Cards MUST be different stories from the hero.

URGENCY SCORING for Florida statewide news (1-10):
- 9-10: Major legislation signed/passed, significant court ruling, statewide emergency or disaster, major economic news affecting all Floridians
- 7-8: Legislative proposals with real chance of passing, significant state agency decision, major Florida crime or trial, statewide policy change
- 5-6: Regional Florida news, state politics, business news, environmental updates
- 3-4: Minor state agency news, local Florida stories outside the Treasure Coast
- 1-2: National news with no Florida angle

Return ONLY valid JSON:
{{
  "hero": {{
    "headline": "Florida-focused headline",
    "body": "full article with paragraph breaks",
    "urgency_score": <1-10>,
    "published": "copy the [pub:...] string from the chosen headline exactly",
    "source_index": <number>
  }},
  "cards": [
    {{"headline": "...", "teaser": "...", "body": "two to three full paragraphs, complete and readable...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}},
    {{"headline": "...", "teaser": "...", "body": "two to three full paragraphs, complete and readable...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}},
    {{"headline": "...", "teaser": "...", "body": "two to three full paragraphs, complete and readable...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}},
    {{"headline": "...", "teaser": "...", "body": "two to three full paragraphs, complete and readable...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}},
    {{"headline": "...", "teaser": "...", "body": "two to three full paragraphs, complete and readable...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}},
    {{"headline": "...", "teaser": "...", "body": "two to three full paragraphs, complete and readable...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}}
  ]
}}"""
    else:
        prompt = f"""Local Treasure Coast news headlines for {category_label}:

{headlines_text}

Tasks:
1. Pick the single most important/urgent story for Treasure Coast Florida residents. LOCAL stories affecting residents directly (county commission decisions, local crime, school district news, local business openings/closings, road/infrastructure, local sports) should be ranked ABOVE national or state stories unless the national story has a very direct local impact (e.g. a hurricane heading toward Martin County, a federal ruling on the Indian River Lagoon). A routine city council vote in Stuart is more relevant to this audience than a national political story.
2. Write an accurate, locally-framed headline. Name the specific county, city, or town (Stuart, Port St. Lucie, Fort Pierce, Vero Beach, Jensen Beach, Palm City, Hobe Sound, Sebastian, etc.) in the headline when relevant.
3. Write a complete, readable factual article of four full paragraphs covering what happened, who is affected locally, the context, and what happens next. Ground all specific facts (names, numbers, dates, quotes, locations) in the source text, but write naturally with useful context and clear explanation. Never write 'no further details available' or similar — always produce a substantive article.
4. For the next {CARDS_PER_CATEGORY} most important stories write a teaser (one to two sentences) and a body of two to three full paragraphs. Write a complete, readable article that covers what happened, who is affected locally, and what it means for the community. Ground all specific facts (names, numbers, dates, quotes) in the source, but write naturally and provide useful local context and explanation. Never write 'no further details available' — always produce a substantive article. Include an urgency_score (1-10). Cards MUST be different stories from the hero.

URGENCY SCORING for local news (1-10):
- 9-10: Major public safety event, significant government decision directly affecting residents, serious local crime with community impact, natural disaster or emergency
- 7-8: Local government vote or proposal, business opening/closing affecting jobs or services, school district news, local development approval
- 5-6: Regional sports, community events, local business news, follow-up stories
- 3-4: State or national news with indirect local connection
- 1-2: National/state news with no meaningful local angle — these should rarely appear

Return ONLY valid JSON:
{{
  "hero": {{
    "headline": "locally-framed headline",
    "body": "full article with paragraph breaks",
    "urgency_score": <1-10>,
    "published": "copy the [pub:...] string from the chosen headline exactly",
    "source_index": <number>
  }},
  "cards": [
    {{"headline": "...", "teaser": "...", "body": "two to three full paragraphs, complete and readable...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}},
    {{"headline": "...", "teaser": "...", "body": "two to three full paragraphs, complete and readable...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}},
    {{"headline": "...", "teaser": "...", "body": "two to three full paragraphs, complete and readable...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}},
    {{"headline": "...", "teaser": "...", "body": "two to three full paragraphs, complete and readable...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}},
    {{"headline": "...", "teaser": "...", "body": "two to three full paragraphs, complete and readable...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}},
    {{"headline": "...", "teaser": "...", "body": "two to three full paragraphs, complete and readable...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}}
  ]
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4000,
            system=[{"type":"text","text":system_prompt,"cache_control":{"type":"ephemeral"}}],
            messages=[{"role":"user","content":prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        # json-repair fallback
        try:
            import json_repair
            data = json_repair.loads(raw)
        except Exception:
            data = json.loads(raw)
        # Attach source to hero
        def attach_source(item):
            idx = item.get("source_index")
            if idx is not None:
                try:
                    source = headlines[int(idx)-1]
                    item["link"]      = source.get("link","")
                    item["image_url"] = source.get("image_url","")
                    item["image_from_google"] = source.get("image_from_google", False)
                except Exception:
                    item["link"] = ""; item["image_url"] = ""; item["image_from_google"] = False
            else:
                item["link"] = ""; item["image_url"] = ""; item["image_from_google"] = False
            raw_pub = item.get("published","").replace("pub:","").strip().strip("[]")
            item["published"] = format_age(raw_pub)
            return item
        data["hero"] = attach_source(data["hero"])
        data["hero"]["body"] = strip_absence_language(strip_markdown(data["hero"].get("body",""), data["hero"].get("headline","")))
        for card in data.get("cards",[]):
            attach_source(card)
            card["body"] = strip_absence_language(strip_markdown(card.get("body",""), card.get("headline","")))
        data["category_key"]   = category_key
        data["category_label"] = category_label
        return data
    except Exception as e:
        print(f"  Claude error for {category_label}: {e}")
        return None

# -- FRONT PAGE HERO SELECTION --

def select_front_page_hero(all_categories):
    """Pick the most locally-significant story across all topic category heroes."""
    from email.utils import parsedate_to_datetime
    from datetime import timezone, timedelta

    eligible = [c for c in all_categories
                if CATEGORIES.get(c["category_key"],{}).get("front_page_hero", True)]
    candidates = eligible if eligible else all_categories
    if len(candidates) == 1: return candidates[0]

    now_utc = datetime.now(timezone.utc)
    yesterday = (now_utc - timedelta(days=1)).strftime("%A").lower()
    two_days  = (now_utc - timedelta(days=2)).strftime("%A").lower()
    three_days = (now_utc - timedelta(days=3)).strftime("%A").lower()
    stale_days = {yesterday, two_days, three_days}
    fresh_override = ["today","this morning","this afternoon","just announced","breaking","hours ago","minutes ago","earlier today"]
    stale_phrases  = ["yesterday","two days ago","three days ago","earlier this week","last week","days ago"]

    def is_stale(cat):
        content = (cat["hero"].get("teaser","") + " " + cat["hero"].get("body","")[:600]).lower()
        if any(p in content for p in fresh_override): return False
        for day in stale_days:
            if f" {day} " in content or f" {day}," in content: return True
        if any(p in content for p in stale_phrases): return True
        return False

    fresh = [c for c in candidates if not is_stale(c)]
    candidates = fresh if fresh else candidates

    today_label   = now_utc.strftime("%A, %B %-d, %Y")
    yesterday_lbl = (now_utc - timedelta(days=1)).strftime("%A")
    two_days_lbl  = (now_utc - timedelta(days=2)).strftime("%A")

    def age_label(cat):
        pub = cat["hero"].get("published","")
        if not pub: return "unknown age"
        for phrase in ["minutes ago","hour ago","hours ago"]:
            if phrase in pub.lower(): return pub
        if "yesterday" in pub.lower(): return "yesterday"
        return pub

    listing = "\n\n".join(
        f"{i+1}. [{c['category_label']}] (timestamp: {age_label(c)}) {c['hero'].get('headline','')}\n"
        f"   Content: {(c['hero'].get('teaser','') + ' ' + c['hero'].get('body','')[:400]).strip()}"
        for i, c in enumerate(candidates)
    )

    prompt = (
        f"TODAY IS: {today_label}\n"
        f"Yesterday was {yesterday_lbl}. Two days ago was {two_days_lbl}.\n\n"
        "You are selecting the SINGLE most front-page-worthy story for Treasure Coast Today, "
        "a LOCAL news site covering Martin, St. Lucie, and Indian River counties in Florida.\n\n"
        f"{listing}\n\n"
        "AUDIENCE: Local Treasure Coast residents who want to know what's happening in their community.\n\n"
        "FRESHNESS IS CRITICAL: The hero must be CURRENT news happening now or today. "
        "Each candidate is labeled with its age. Strongly prefer stories from the past few hours. "
        "Stories more than 24 hours old should not lead unless they are ongoing major events "
        "still actively developing (a missing person case, an ongoing trial, a storm approaching).\n\n"
        "STRONG front-page heroes for a local site:\n"
        "1. Significant local government decisions directly affecting residents (major zoning approvals, "
        "budget votes, school board actions, commission decisions on development)\n"
        "2. Major public safety events affecting the community (serious crimes, accidents with casualties, "
        "emergencies, weather events hitting the area)\n"
        "3. Major local development or business news affecting jobs, housing, or daily life\n"
        "4. School district news with broad community impact\n"
        "5. Significant local sports victories (state championships, major tournament wins)\n"
        "6. National or state news with DIRECT local impact (a hurricane heading toward the TC, "
        "a federal ruling on the Indian River Lagoon, state legislation affecting local property taxes)\n\n"
        "WEAK front-page heroes:\n"
        "- National news with no local angle\n"
        "- Minor events or routine announcements\n"
        "- Things to do / event listings (these are cards, not heroes)\n"
        "- Old events being recapped with no new development\n\n"
        "THINK FIRST, THEN ANSWER. For each candidate briefly assess: (a) how current is it, "
        "(b) how directly does it affect Treasure Coast residents?\n\n"
        "Format your response EXACTLY like this:\n"
        "Reasoning: <one line per candidate, very brief>\n"
        "PICK: <number>\n"
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role":"user","content":prompt}]
        )
        raw  = resp.content[0].text.strip()
        pick = re.search(r"PICK:\s*(\d+)", raw, re.IGNORECASE)
        if pick:
            idx = int(pick.group(1)) - 1
            if 0 <= idx < len(candidates):
                chosen = candidates[idx]
                print(f"  Front page hero: [{chosen['category_label']}] {chosen['hero'].get('headline','')[:60]}")
                return chosen
    except Exception as e:
        print(f"  Hero selection failed: {e}")
    # Fallback: highest urgency_score
    return max(candidates, key=lambda c: int(c["hero"].get("urgency_score",0) or 0))

# -- GLOBAL RANK (front page card ordering + semantic dedup) --

def global_rank(all_cards, dedupe_against=None):
    if not all_cards: return all_cards
    stories = [f"{i+1}. [{c.get('cat_label','')}] {c.get('headline','')}" for i,c in enumerate(all_cards)]
    n = len(all_cards)
    dedupe_clause = ""
    if dedupe_against:
        dedupe_clause = (
            f"\nThe lead story already shown is: \"{dedupe_against}\"\n"
            "EXCLUDE any story covering this same underlying event.\n"
        )
    prompt = (
        f"Rank these {n} Treasure Coast local news stories by importance and relevance to LOCAL residents of Martin, St. Lucie, and Indian River counties.\n"
        f"{dedupe_clause}\n"
        "DEDUPLICATION: If multiple stories cover the same event, keep only the best version.\n\n"
        "RANKING PRIORITY — local relevance is everything:\n"
        "1. LOCAL government decisions directly affecting residents (county/city commission votes, zoning, budgets, school board actions)\n"
        "2. LOCAL public safety (serious crimes, accidents, emergencies affecting the Treasure Coast community)\n"
        "3. LOCAL business and development (jobs, new businesses, closings, real estate, major projects)\n"
        "4. LOCAL schools and education news\n"
        "5. State news with DIRECT local impact (a Florida law specifically affecting these counties, a state agency ruling on a local issue)\n"
        "6. LOCAL sports and community events\n"
        "7. National or state news with indirect/no local connection — rank these LOWEST. A national political story belongs at the bottom unless it has a named direct effect on Martin, St. Lucie, or Indian River County.\n\n"
        "The audience lives here. A county commission vote on a new development matters more to them than a national headline with no local angle.\n\n"
        + "\n".join(stories) + "\n\n"
        "Return ONLY a JSON array of numbers in ranked order, duplicates removed. Example: [3,1,7,2]"
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role":"user","content":prompt}]
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"): raw = raw.split("```")[1].lstrip("json").strip()
        indices = json.loads(raw)
        seen, ranked = set(), []
        for idx in indices:
            i = int(idx)-1
            if 0 <= i < n and i not in seen:
                seen.add(i); ranked.append(all_cards[i])
        if len(ranked) < max(3, n//3):
            for i,c in enumerate(all_cards):
                if i not in seen: ranked.append(c)
        print(f"  Global ranking: {len(ranked)} stories (from {n})")
        return ranked
    except Exception as e:
        print(f"  Global ranking failed ({e}), using fallback")
        return all_cards

# -- PROMOTE DUPLICATE HEROES --

def promote_duplicate_heroes(top_cat, all_categories):
    fp_headline = top_cat["hero"].get("headline","")
    fp_key      = top_cat["category_key"]
    others = [c for c in all_categories if c["category_key"] != fp_key]
    if not others or not fp_headline: return

    listing = "\n".join(f"{i+1}. {c['hero'].get('headline','')}" for i,c in enumerate(others))
    prompt = (
        f"The lead front-page story is:\n\"{fp_headline}\"\n\n"
        f"These are other section lead headlines:\n{listing}\n\n"
        "Which numbered headlines cover the SAME underlying event as the lead? "
        "Return ONLY a JSON array of matching numbers, e.g. [2,4]. If none match, return []."
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role":"user","content":prompt}]
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"): raw = raw.split("```")[1].lstrip("json").strip()
        dupes = set(int(x) for x in json.loads(raw))
    except Exception as e:
        print(f"  Hero dedup failed ({e})")
        return
    for i, cat in enumerate(others):
        if (i+1) in dupes:
            cards = cat.get("cards",[])
            if cards:
                promoted = cards[0]
                old_hero = cat["hero"]
                if not old_hero.get("teaser"):
                    body = old_hero.get("body","").strip()
                    first = body.split(". ")[0].strip()
                    old_hero["teaser"] = (first[:160]+".") if first else ""
                cat["hero"]  = promoted
                cat["cards"] = cards[1:] + [old_hero]
                print(f"  Promoted next card for {cat['category_label']} (was duplicate)")

# -- RENDER INDEX.HTML --

def render_index(all_categories, top_cat):

    # All categories get a section label — counties get "X County News", topics get "Treasure Coast X News"
    COUNTY_KEYS = {"martin", "st_lucie", "indian_river"}
    SECTION_LABELS = {
        "martin":       "Martin County News",
        "st_lucie":     "St. Lucie County News",
        "indian_river": "Indian River County News",
        "local_gov":    "Treasure Coast Local Government News",
        "crime":        "Treasure Coast Crime & Safety News",
        "business":     "Treasure Coast Business News",
        "schools":      "Treasure Coast Schools News",
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
        # Section label for SEO — all categories except Top News get one
        section_label = ""
        if cat_key in SECTION_LABELS:
            seo_text  = SECTION_LABELS[cat_key]
            label_cls = "county-section-label" if cat_key in COUNTY_KEYS else "topic-section-label"
            section_label = f'<div class="{label_cls}"><h2 class="county-label-text">{seo_text}</h2></div>'
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
            <button class="share-btn" data-headline="{hero["headline"].replace('"', "&quot;")}" onclick="shareArticle(this)">Share &#8599;</button>
            <button class="collapse-btn" onclick="collapseThis(this)">Close &uarr;</button>
          </div>
        </div>
      </div>
    </section>"""

    # Top News hero + all category heroes
    heroes_html = hero_section("all", top_cat["category_label"], top_cat["hero"], visible=True)
    for cat in all_categories:
        heroes_html += hero_section(cat["category_key"], cat["category_label"], cat["hero"], visible=False)

    # Build card pool
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
          <a href="advertise.html" class="support-card-btn">Get in touch &rarr;</a>
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
            <button class="share-btn" data-headline="{card["headline"].replace('"', "&quot;")}" onclick="shareArticle(this)">Share &#8599;</button>
            <button class="collapse-btn" onclick="collapseThis(this)">Close &uarr;</button>
          </div>
        </div>
      </div>"""

    nav_buttons = "\n        ".join(
        f'<button class="cat-btn{" active" if i==0 else ""}" data-cat="{"all" if i==0 else cat["category_key"]}">' +
        f'{"Top News" if i==0 else cat["category_label"]}</button>'
        for i, cat in enumerate([None] + all_categories)
    )

    _structured_data = {
        "@context": "https://schema.org",
        "@type": "NewsMediaOrganization",
        "name": "Treasure Coast Today",
        "url": SITE_URL,
        "logo": f"{SITE_URL}/favicon.svg",
        "description": "Local news for Martin County, St. Lucie County, and Indian River County, Florida.",
        "areaServed": [
            {"@type": "AdministrativeArea", "name": "Martin County, Florida"},
            {"@type": "AdministrativeArea", "name": "St. Lucie County, Florida"},
            {"@type": "AdministrativeArea", "name": "Indian River County, Florida"},
        ],
        "sameAs": [f"{SITE_URL}"]
    }
    _head   = _page_head(
        "Treasure Coast Today | Local News for Martin, St. Lucie & Indian River County",
        "Local news for the Treasure Coast — Martin County, Port St. Lucie, Fort Pierce, Stuart, Vero Beach, Jensen Beach and surrounding communities. Updated 4 times daily.",
        structured_data=_structured_data
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
        <a href="archive.html" class="cat-btn" style="text-decoration:none">Archive</a>
        <a href="events.html" class="cat-btn" style="text-decoration:none">Events</a>
      </nav>

      <div class="header-actions">
        <a href="https://treasurecoast.today/advertise.html" class="support-btn" style="text-decoration:none">Advertise</a>
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



def render_events_page():
    """Generate a coming-soon events.html page with email capture for organizers."""
    head   = _page_head("List Your Event — Treasure Coast Today",
                        "Coming soon: list your Treasure Coast event for free. Sign up to be notified when the events calendar launches.",
                        "/events.html")
    header = _page_header(active="events")
    footer = _page_footer()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
  <style>
    .cs-wrap {{ max-width: 600px; margin: 80px auto 80px; padding: 0 24px; text-align: center; }}
    .cs-eyebrow {{ font-size: 11px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: var(--accent); display: block; margin-bottom: 16px; }}
    .cs-headline {{ font-family: 'Fraunces', serif; font-size: clamp(28px, 5vw, 44px); font-weight: 600; line-height: 1.15; color: var(--text); margin: 0 0 20px; letter-spacing: -.02em; }}
    .cs-sub {{ font-size: 16px; color: var(--text-secondary); line-height: 1.65; margin: 0 0 40px; }}
    .cs-form {{ display: flex; gap: 10px; max-width: 440px; margin: 0 auto 16px; }}
    .cs-input {{ flex: 1; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 12px 16px; font-family: 'DM Sans', sans-serif; font-size: 14px; color: var(--text); outline: none; transition: border-color .15s; }}
    .cs-input:focus {{ border-color: var(--accent); }}
    .cs-input::placeholder {{ color: var(--text-secondary); opacity: .5; }}
    .cs-btn {{ background: var(--accent); color: white; border: none; border-radius: 8px; padding: 12px 22px; font-family: 'DM Sans', sans-serif; font-size: 14px; font-weight: 600; cursor: pointer; white-space: nowrap; transition: opacity .15s; }}
    .cs-btn:hover {{ opacity: .88; }}
    .cs-fine {{ font-size: 12px; color: var(--text-secondary); }}
    .cs-success {{ display: none; color: var(--accent); font-size: 15px; font-weight: 500; margin-top: 12px; }}
    .cs-divider {{ border: none; border-top: 1px solid var(--border); margin: 48px 0; }}
    .cs-also {{ font-size: 14px; color: var(--text-secondary); }}
    .cs-also a {{ color: var(--accent); text-decoration: none; font-weight: 500; }}
    @media(max-width:500px) {{ .cs-form {{ flex-direction: column; }} .cs-btn {{ width: 100%; }} }}
  </style>
</head>
<body>
{header}
  <main>
    <div class="cs-wrap">
      <span class="cs-eyebrow">Coming Soon</span>
      <h1 class="cs-headline">List your Treasure Coast event for free.</h1>
      <p class="cs-sub">We're building a local events calendar for Martin, St. Lucie, and Indian River counties. Leave your email and we'll let you know when you can submit your event.</p>
      <form class="cs-form" id="csForm" action="https://formspree.io/f/mqejrpdv" method="POST">
        <input type="hidden" name="_subject" value="Events calendar interest — Treasure Coast Today">
        <input class="cs-input" type="email" name="email" placeholder="your@email.com" required>
        <button class="cs-btn" type="submit">Notify me</button>
      </form>
      <p class="cs-fine">No spam. Just a heads-up when the calendar is live.</p>
      <p class="cs-success" id="csSuccess">&#10003; You're on the list — we'll be in touch!</p>
      <hr class="cs-divider">
      <p class="cs-also">In the meantime, check out <a href="/?cat=things_to_do">Things To Do</a> for local event coverage, or <a href="advertise.html">advertise with us</a> to reach Treasure Coast readers.</p>
    </div>
  </main>
{footer}
  <script>
    const f=document.getElementById('csForm'),s=document.getElementById('csSuccess');
    f.addEventListener('submit',async(e)=>{{
      e.preventDefault();
      try{{
        const r=await fetch(f.action,{{method:'POST',body:new FormData(f),headers:{{'Accept':'application/json'}}}});
        if(r.ok){{f.style.display='none';s.style.display='block';}}
        else alert('Something went wrong. Please try again.');
      }}catch(err){{alert('Something went wrong. Please try again.');}}
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

    # Build front page cards pool
    _all = []
    for cat in all_categories:
        hero = cat["hero"]
        _all.append({**hero, "cat_label": cat["category_label"], "is_hero": True})
        for card in cat.get("cards", []):
            _all.append({**card, "cat_label": cat["category_label"], "is_hero": False})
    _all.sort(key=lambda c: int(c.get("urgency_score", 0) or 0), reverse=True)

    _fp_headline = top_cat["hero"].get("headline", "")
    _seen = set()
    _deduped = []
    for c in _all:
        h   = c.get("headline", "")
        key = re.sub(r"[^a-z0-9 ]", "", h.lower())[:60]
        fp_key = re.sub(r"[^a-z0-9 ]", "", _fp_headline.lower())[:60]
        if key != fp_key and key not in _seen:
            _seen.add(key)
            _deduped.append(c)

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
            "cards": [card_to_dict(c) for c in _deduped[:6]],
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
    (OUTPUT_DIR / "data.json").write_text(
        json.dumps(app_data, indent=2), encoding="utf-8"
    )
    print("  data.json written")


def _page_head(title, description, canonical_path="", structured_data=None):
    """Shared HTML head used by every generated page."""
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
  <meta property="og:site_name" content="Treasure Coast Today">
  <meta property="og:image" content="{SITE_URL}/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:image" content="{SITE_URL}/og-image.png">
  <meta name="geo.region" content="US-FL">
  <meta name="geo.placename" content="Treasure Coast, Florida">
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="style.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,500;0,9..144,600;1,9..144,300&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500&display=swap" rel="stylesheet">
{schema}
  <!-- Google Analytics -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-GLJY7M6F3G"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-GLJY7M6F3G');
  </script>"""


def _page_header(active=""):
    """Shared site header — two rows on mobile: logo+advertise, then scrollable nav."""
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
        {cat_link("Schools", "/?cat=schools", "schools")}
        {cat_link("Sports", "/?cat=sports", "sports")}
        {cat_link("Things To Do", "/?cat=things_to_do", "things_to_do")}
        {cat_link("Florida", "/?cat=florida", "florida")}
        {cat_link("Martin Co.", "/?cat=martin", "martin")}
        {cat_link("St. Lucie Co.", "/?cat=st_lucie", "st_lucie")}
        {cat_link("Indian River Co.", "/?cat=indian_river", "indian_river")}
        {cat_link("Archive", "archive.html", "archive")}
        {cat_link("Events", "events.html", "events")}
      </nav>

      <div class="header-actions">
        <a href="https://treasurecoast.today/advertise.html" class="support-btn" style="text-decoration:none">Advertise</a>
      </div>
    </div>
  </header>"""


def _page_footer():
    """Shared footer used by every generated page."""
    return """  <footer>
    <div class="footer-inner">
      <span class="footer-wordmark">Treasure Coast Today</span>
      <span class="footer-tagline">Local news for Martin, St. Lucie &amp; Indian River counties.</span>
      <div class="footer-links">
        <a href="about.html">About</a>
        <a href="archive.html">Archive</a>
        <a href="events.html">Events</a>
        <a href="advertise.html">Advertise</a>
        <a href="privacy.html">Privacy</a>
        <a href="mailto:hello@treasurecoast.today">Contact</a>
      </div>
    </div>
  </footer>
  <script src="main.js"></script>"""


def render_about_page():
    """Generate about.html — static, only regenerated if this function changes."""
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
        <p>Treasure Coast Today is a local news source covering Martin County, St. Lucie County, and Indian River County, Florida. We bring residents the stories that matter most close to home — local government, public safety, business and development, schools, sports, and things to do across the Treasure Coast.</p>

        <p>Our focus is simple: the news that actually affects the people who live and work here. From county commission decisions in Stuart to development in Port St. Lucie, school district news in Vero Beach to public safety in Fort Pierce, we keep the community informed about what's happening in their own backyard.</p>

        <h2>Our coverage area</h2>
        <p>We cover all three Treasure Coast counties with equal dedication:</p>
        <p><strong>Martin County</strong> — Stuart, Jensen Beach, Palm City, Hobe Sound, Port Salerno, and surrounding communities.</p>
        <p><strong>St. Lucie County</strong> — Port St. Lucie, Fort Pierce, St. Lucie West, and the surrounding area.</p>
        <p><strong>Indian River County</strong> — Vero Beach, Sebastian, Fellsmere, and nearby communities.</p>
        <p>We also cover statewide Florida news that affects Treasure Coast residents, from legislation in Tallahassee to issues touching the entire region. Stories are organized by both topic and county, so readers can quickly find the local news most relevant to them.</p>

        <h2>Our mission</h2>
        <p>Local news strengthens communities. When residents know what's happening in their towns, they make better decisions, get more involved, and hold their institutions accountable. Treasure Coast Today exists to make staying informed about local news effortless for everyone on the Treasure Coast.</p>

        <h2>Advertise with us</h2>
        <p>Treasure Coast Today connects local businesses with engaged readers across Martin, St. Lucie, and Indian River counties. If your business serves the Treasure Coast community, we'd love to help you reach them. <a href="advertise.html" class="about-contact">Learn more about advertising &rarr;</a></p>

        <hr class="about-divider">

        <h2>Get in touch</h2>
        <p>Have a news tip, question, or correction? We'd love to hear from you at <a href="mailto:hello@treasurecoast.today" class="about-contact">hello@treasurecoast.today</a></p>
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
        <div class="adv-stat"><span class="adv-stat-num">4&times;</span><span class="adv-stat-label">Daily updates keeping readers coming back</span></div>
        <div class="adv-stat"><span class="adv-stat-num">3</span><span class="adv-stat-label">Counties covered equally</span></div>
        <div class="adv-stat"><span class="adv-stat-num">Local</span><span class="adv-stat-label">Readers who live, work, and spend here</span></div>
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


def slugify(text):
    """Convert a headline to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:80].strip("-")


def load_archive(archive_path):
    """Load the existing archive metadata or return empty list."""
    try:
        if archive_path.exists():
            return json.loads(archive_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def render_article_page(hero, category_label, category_key, pub_date, slug):
    """Render a permanent article page for a single hero story."""
    head   = _page_head(
        f"{hero['headline']} — Treasure Coast Today",
        (hero.get("teaser") or hero.get("body","")[:155]).replace('"',''),
        f"/articles/{slug}.html"
    )
    header = _page_header()
    footer = _page_footer()
    body   = make_paragraphs(hero.get("body",""))
    img_html = ""
    if hero.get("image_url"):
        credit = f'<figcaption class="img-credit">Photo: {hero["image_credit"]}</figcaption>' if hero.get("image_credit") else ""
        img_html = f'<figure class="article-hero-image"><img src="{hero["image_url"]}" alt="{hero["headline"]}" loading="eager">{credit}</figure>'

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
    """Render a browsable archive index page."""
    head   = _page_head(
        "Article Archive — Treasure Coast Today",
        "Browse all local news articles from Treasure Coast Today covering Martin, St. Lucie, and Indian River counties.",
        "/archive.html"
    )
    header = _page_header()
    footer = _page_footer()

    # Group entries by month
    by_month = defaultdict(list)
    for e in sorted(archive_entries, key=lambda x: x.get("date",""), reverse=True):
        try:
            month = e["date"][:7]  # YYYY-MM
            label = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
        except Exception:
            label = "Recent"
            month = "recent"
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
    .archive-link {{ display: flex; align-items: baseline; gap: 10px; padding: 12px 0; text-decoration: none; color: inherit; flex-wrap: wrap; transition: background .1s; }}
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
    """Regenerate sitemap.xml including all archived article URLs."""
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
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>
  <url>
    <loc>{SITE_URL}/advertise.html</loc>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>"""

    article_urls = ""
    for e in archive_entries:
        article_urls += f"""
  <url>
    <loc>{SITE_URL}/articles/{e['slug']}.html</loc>
    <changefreq>never</changefreq>
    <priority>0.7</priority>
    <lastmod>{e['date']}</lastmod>
  </url>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{static_urls}
{article_urls}
</urlset>"""


def write_archives(all_categories, top_cat):
    """Write individual article pages, update archive.json, archive.html, sitemap.xml."""
    articles_dir  = OUTPUT_DIR / "articles"
    archive_path  = OUTPUT_DIR / "archive.json"
    articles_dir.mkdir(exist_ok=True)

    archive = load_archive(archive_path)
    existing_slugs = {e["slug"] for e in archive}
    new_count = 0

    # Use today's date for all articles in this run
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Write a page for every category hero (including top_cat)
    heroes_to_archive = [(top_cat["category_key"], top_cat["category_label"], top_cat["hero"])]
    for cat in all_categories:
        if cat["category_key"] != top_cat["category_key"]:
            heroes_to_archive.append((cat["category_key"], cat["category_label"], cat["hero"]))

    for cat_key, cat_label, hero in heroes_to_archive:
        headline = hero.get("headline","").strip()
        if not headline:
            continue

        # Build slug — date prefix ensures uniqueness across runs
        base_slug = f"{today}-{slugify(headline)}"
        slug = base_slug
        # Handle rare slug collision (same headline picked twice)
        counter = 1
        while slug in existing_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1

        # Write article HTML
        article_html = render_article_page(hero, cat_label, cat_key, today, slug)
        (articles_dir / f"{slug}.html").write_text(article_html, encoding="utf-8")

        # Add to archive metadata
        entry = {
            "slug":           slug,
            "headline":       headline,
            "teaser":         hero.get("teaser","") or hero.get("body","")[:180],
            "category_key":   cat_key,
            "category_label": cat_label,
            "date":           today,
            "image_url":      hero.get("image_url",""),
        }
        archive.append(entry)
        existing_slugs.add(slug)
        new_count += 1

    # Save updated archive.json
    archive_path.write_text(json.dumps(archive, indent=2), encoding="utf-8")

    # Render archive index page
    (OUTPUT_DIR / "archive.html").write_text(render_archive_page(archive), encoding="utf-8")

    # Update sitemap
    (OUTPUT_DIR / "sitemap.xml").write_text(update_sitemap(archive), encoding="utf-8")

    print(f"  Archived {new_count} new articles ({len(archive)} total)")


def main():
    print("Treasure Coast Today — building site...")
    image_bank = build_image_bank()
    used_bank_images = set()
    all_categories = []

    for cat_key, cat_config in CATEGORIES.items():
        print(f"Processing: {cat_config['label']}...")
        headlines = fetch_headlines(cat_config["feeds"])
        if not headlines:
            print(f"  No headlines found, skipping.")
            continue

        print(f"  {len(headlines)} headlines fetched")
        data = generate_category_content(cat_key, cat_config["label"], headlines)
        if not data:
            continue

        # Attach image to hero
        hero_headline = data["hero"].get("headline","")
        src_idx       = data["hero"].get("source_index")
        original_title = ""
        if src_idx is not None:
            try:
                original_title = headlines[int(src_idx)-1].get("title","")
            except Exception:
                pass

        # Conservative hero-image priority:
        # 1) article RSS image, but only when it did not come from a Google News thumbnail
        # 2) article's own og:image from the publisher page
        # 3) strict image-bank match as a last resort
        # 4) no image if confidence is low
        img = ""
        image_credit = ""
        source_img = data["hero"].get("image_url","")
        source_is_google_thumb = data["hero"].get("image_from_google", False)
        link = data["hero"].get("link","")

        if source_img and not source_is_google_thumb:
            img = source_img
            image_credit = get_image_credit(link)

        if not img and link and "news.google.com" not in link.lower():
            og = fetch_og_image(link)
            if og:
                img = og
                image_credit = get_image_credit(link)
                print(f"  Hero image via og:image")

        bank_img, bank_credit = ("", "")
        if not img:
            if original_title:
                bank_img, bank_credit = match_image(original_title, image_bank, cat_key, used_bank_images)
            if not bank_img:
                bank_img, bank_credit = match_image(hero_headline, image_bank, cat_key, used_bank_images)
            if not bank_img:
                body_ctx = (original_title or hero_headline) + " " + data["hero"].get("body","")[:250]
                bank_img, bank_credit = match_image(body_ctx, image_bank, cat_key, used_bank_images)
            if bank_img:
                img = bank_img
                image_credit = bank_credit
                used_bank_images.add(canonical_image_url(bank_img))
                print(f"  Hero image via strict image-bank match")

        # Final fallback: license-free Pexels stock image so no hero is ever imageless
        if not img:
            print(f"  Trying Pexels for {cat_key}...")
            px_img, px_credit = fetch_pexels_image(cat_key)
            print(f"  Pexels result: {'found' if px_img else 'empty'}")
            if px_img:
                img = px_img
                image_credit = px_credit
                print(f"  Hero image via Pexels fallback")

        data["hero"]["image_url"]    = img
        data["hero"]["image_credit"] = image_credit

        all_categories.append(data)
        print(f"  Hero: {data['hero']['headline'][:60]}... (urgency: {data['hero'].get('urgency_score')}, image: {'yes' if img else 'no'})")

    if not all_categories:
        print("No categories generated. Aborting.")
        return

    # Select front page hero
    top_cat = select_front_page_hero(all_categories)

    # Ensure no other category hero duplicates the front page hero
    promote_duplicate_heroes(top_cat, all_categories)

    # Render and write all pages
    index_html = render_index(all_categories, top_cat)
    (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
    write_data_json(all_categories, top_cat)

    # Archive — write permanent article pages and update archive.json + sitemap
    write_archives(all_categories, top_cat)

    # Events coming-soon page
    (OUTPUT_DIR / "events.html").write_text(render_events_page(), encoding="utf-8")

    # Static pages
    (OUTPUT_DIR / "about.html").write_text(render_about_page(), encoding="utf-8")
    (OUTPUT_DIR / "advertise.html").write_text(render_advertise_page(), encoding="utf-8")

    print(f"Done. {len(all_categories)} categories written.")

if __name__ == "__main__":
    main()
