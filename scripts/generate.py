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

def build_image_bank():
    bank = []
    for url in IMAGE_BANK_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:60]:
                img = extract_image(entry)
                if img:
                    bank.append({
                        "title":     entry.get("title",""),
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
             "said","will","than","more","also","when","s"}
    return set(w.lower().strip(".,;:()") for w in text.split() if len(w)>3 and w.lower() not in stops)

def match_image(headline, image_bank, cat_key=None):
    hw = tokens(headline)
    best_score, best_img, best_credit = 0, "", ""
    for entry in image_bank:
        et = tokens(entry["title"])
        overlap = len(hw & et)
        if overlap > best_score and overlap >= 2:
            best_score  = overlap
            best_img    = entry["image_url"]
            best_credit = get_image_credit(entry.get("source",""))
    # Distinctive-token fallback
    if not best_img:
        distinctive = {w for w in hw if len(w) >= 6}
        if distinctive:
            for entry in image_bank:
                et = {w for w in tokens(entry["title"]) if len(w) >= 6}
                overlap = len(distinctive & et)
                if overlap > best_score and overlap >= 2:
                    best_score  = overlap
                    best_img    = entry["image_url"]
                    best_credit = get_image_credit(entry.get("source",""))
    return best_img, best_credit

def fetch_og_image(url):
    if not url: return ""
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0 PlainBot/1.0"})
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
                summary = ""
                for field in ["summary","description","content"]:
                    val = entry.get(field,"") or getattr(entry,field,"")
                    if isinstance(val,list) and val:
                        summary = val[0].get("value","") if isinstance(val[0],dict) else str(val[0])
                    elif isinstance(val,str):
                        summary = val
                    if summary: break
                summary = re.sub(r"<[^>]+>","",summary).strip()[:500]
                pub = ""
                if hasattr(entry,"published"): pub = entry.published
                elif hasattr(entry,"updated"):  pub = entry.updated
                link = entry.get("link","") or getattr(entry,"link","")
                img  = extract_image(entry)
                headlines.append({
                    "title":   title,
                    "summary": summary,
                    "published": pub,
                    "link":    link,
                    "image_url": img,
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
    return result[:limit]

# -- CATEGORY CONTENT GENERATION --

LOCAL_SYSTEM_PROMPT = """You write factual local news articles for Treasure Coast Today, covering Martin, St. Lucie, and Indian River counties in Florida. Write in plain direct English — no em dashes, no fluff, no absence language. Every sentence must be a confirmed fact from the provided headlines and summaries. Name specific towns, streets, facilities, and local officials when available."""

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
        return f"{i+1}. {sanitize(h.get('title',''))}{pub_str}\n   {sanitize(h.get('summary',''))[:550]}"

    headlines_text = "\n".join(hl_line(i,h) for i,h in enumerate(headlines))
    headlines_text = headlines_text.replace("\\","").encode("ascii","ignore").decode("ascii")

    prompt = f"""Local Treasure Coast news headlines for {category_label}:

{headlines_text}

Tasks:
1. Pick the single most important/urgent story relevant to Treasure Coast Florida residents.
2. Write an accurate, locally-framed headline. Name the specific county or town in the headline if relevant.
3. Write a 380-430 word factual article in FOUR full paragraphs. Use only confirmed facts. Name specific places, officials, and addresses when available. Cover what happened, who is affected, and what happens next. Do NOT write only two paragraphs.
4. For the next {CARDS_PER_CATEGORY} most important stories write a teaser (one sentence), body (two short paragraphs ~100 words), and urgency_score (1-10). Cards MUST be different stories from the hero.

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
    {{"headline": "...", "teaser": "...", "body": "two paragraphs...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}},
    {{"headline": "...", "teaser": "...", "body": "two paragraphs...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}},
    {{"headline": "...", "teaser": "...", "body": "two paragraphs...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}},
    {{"headline": "...", "teaser": "...", "body": "two paragraphs...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}},
    {{"headline": "...", "teaser": "...", "body": "two paragraphs...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}},
    {{"headline": "...", "teaser": "...", "body": "two paragraphs...", "urgency_score": <1-10>, "published": "copy timestamp", "source_index": <number>}}
  ]
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1800,
            system=[{"type":"text","text":LOCAL_SYSTEM_PROMPT,"cache_control":{"type":"ephemeral"}}],
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
                except Exception:
                    item["link"] = ""; item["image_url"] = ""
            else:
                item["link"] = ""; item["image_url"] = ""
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
        f"Rank these {n} Treasure Coast local news stories by importance and relevance to local residents.\n"
        f"{dedupe_clause}\n"
        "DEDUPLICATION: If multiple stories cover the same event, keep only the best version.\n"
        "RANKING PRIORITY:\n"
        "1. Stories with direct impact on residents (government decisions, public safety, major development)\n"
        "2. County-wide or multi-county stories over single-town stories\n"
        "3. Breaking news over follow-up coverage\n"
        "4. Sports and things to do rank lowest unless exceptional\n\n"
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
        return f"""
    <section class="hero{fade}" data-cat-hero="{cat_key}"{display}>
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
          <button class="collapse-btn" onclick="collapseThis(this)">Close &uarr;</button>
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
        <div class="support-inner">
          <div class="support-logo">tct</div>
          <p class="support-text">Reach thousands of Treasure Coast readers every day. Advertise with Treasure Coast Today.</p>
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
          <button class="collapse-btn" onclick="collapseThis(this)">Close &uarr;</button>
        </div>
      </div>"""

    nav_buttons = "\n        ".join(
        f'<button class="cat-btn{" active" if i==0 else ""}" data-cat="{"all" if i==0 else cat["category_key"]}">' +
        f'{"Top News" if i==0 else cat["category_label"]}</button>'
        for i, cat in enumerate([None] + all_categories)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Treasure Coast Today — Your Treasure Coast, every day.</title>
  <meta name="description" content="Local news for Martin, St. Lucie, and Indian River counties.">
  <meta property="og:title" content="Treasure Coast Today">
  <meta property="og:description" content="Your Treasure Coast, every day.">
  <meta property="og:url" content="{SITE_URL}">
  <link rel="stylesheet" href="style.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,500;0,9..144,600;1,9..144,300&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500&display=swap" rel="stylesheet">
</head>
<body>
  <header>
    <div class="header-inner">
      <a href="/" class="wordmark">Treasure Coast Today</a>
      <nav class="category-nav">
        {nav_buttons}
        <a href="events.html" class="cat-btn" style="text-decoration:none">Events</a>
      </nav>
      <div class="header-actions">
        <button class="theme-toggle" id="themeToggle" aria-label="Toggle theme">&#9790;</button>
        <a href="advertise.html" class="support-btn" style="text-decoration:none">Advertise</a>
      </div>
    </div>
  </header>

  <main>
    {heroes_html}
    <div class="articles-grid" id="articlesGrid">
      {cards_html}
    </div>
  </main>

  <footer>
    <div class="footer-inner">
      <span class="footer-wordmark">Treasure Coast Today</span>
      <span class="footer-tagline">Local news for Martin, St. Lucie &amp; Indian River counties.</span>
      <div class="footer-links">
        <a href="about.html">About</a>
        <a href="events.html">Events</a>
        <a href="privacy.html">Privacy</a>
        <a href="mailto:hello@treasurecoast.today">Contact</a>
      </div>
    </div>
  </footer>

  <script src="main.js"></script>
</body>
</html>"""


def fetch_eventbrite_events():
    """Fetch upcoming local events from Eventbrite API. Returns list of event dicts."""
    api_key = os.environ.get("EVENTBRITE_API_KEY", "")
    if not api_key:
        print("  Eventbrite: no API key, skipping events page")
        return []
    try:
        # Search for events in the Treasure Coast area
        # lat/lng center point between Stuart and Port St. Lucie
        params = {
            "token":          api_key,
            "location.latitude":  27.1975,
            "location.longitude": -80.2520,
            "location.within":    "30mi",
            "expand":             "venue,logo",
            "sort_by":            "date",
            "start_date.range_start": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        resp = requests.get(
            "https://www.eventbriteapi.com/v3/events/search/",
            params=params, timeout=15
        )
        if resp.status_code != 200:
            print(f"  Eventbrite API error: {resp.status_code}")
            return []
        data = resp.json()
        events = []
        for e in data.get("events", [])[:30]:
            venue    = e.get("venue") or {}
            logo     = e.get("logo") or {}
            name     = (e.get("name") or {}).get("text", "")
            desc     = (e.get("description") or {}).get("text", "")[:300]
            start    = (e.get("start") or {}).get("local", "")
            url      = e.get("url", "")
            city     = venue.get("city", "")
            address  = (venue.get("address") or {}).get("localized_address_display", "")
            img      = logo.get("url", "") or logo.get("original", {}).get("url", "")
            is_free  = e.get("is_free", False)
            # Parse date for display
            try:
                from datetime import datetime as dt
                d = dt.strptime(start[:16], "%Y-%m-%dT%H:%M")
                date_display = d.strftime("%a, %b %-d")
                time_display = d.strftime("%-I:%M %p")
            except Exception:
                date_display = start[:10]
                time_display = ""
            events.append({
                "name":         name,
                "description":  desc,
                "date":         date_display,
                "time":         time_display,
                "city":         city,
                "address":      address,
                "url":          url,
                "image":        img,
                "is_free":      is_free,
            })
        print(f"  Eventbrite: {len(events)} events fetched")
        return events
    except Exception as e:
        print(f"  Eventbrite fetch failed: {e}")
        return []


def render_events_page(events):
    """Generate a standalone events.html page."""
    ts = now_et()

    if not events:
        events_html = '<p class="no-events">No upcoming events found. Check back soon.</p>'
    else:
        events_html = ""
        for ev in events:
            img_html  = f'<img src="{ev["image"]}" alt="" class="event-img" loading="lazy">' if ev.get("image") else '<div class="event-img-placeholder"></div>'
            free_badge = '<span class="event-free">Free</span>' if ev.get("is_free") else ""
            city_str  = f' &middot; {ev["city"]}' if ev.get("city") else ""
            time_str  = f' at {ev["time"]}' if ev.get("time") else ""
            events_html += f"""
    <a href="{ev['url']}" target="_blank" rel="noopener" class="event-card">
      <div class="event-img-wrap">{img_html}</div>
      <div class="event-info">
        <div class="event-date-row">
          <span class="event-date">{ev['date']}{time_str}</span>
          {free_badge}
        </div>
        <h2 class="event-name">{ev['name']}</h2>
        <p class="event-location">{ev.get('address','') or ev.get('city','')}{city_str}</p>
        <p class="event-desc">{ev.get('description','')}</p>
      </div>
    </a>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Events — Treasure Coast Today</title>
  <meta name="description" content="Upcoming events on the Treasure Coast — Martin, St. Lucie, and Indian River counties.">
  <link rel="stylesheet" href="style.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:wght@700;900&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    .events-header {{ max-width: 900px; margin: 40px auto 8px; padding: 0 24px; }}
    .events-header h1 {{ font-family: 'Fraunces', serif; font-size: 32px; color: var(--text); margin: 0 0 4px; }}
    .events-header p {{ color: var(--text-sub); font-size: 14px; margin: 0 0 32px; }}
    .events-grid {{ max-width: 900px; margin: 0 auto; padding: 0 24px 64px; display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }}
    .event-card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; text-decoration: none; color: inherit; display: flex; flex-direction: column; transition: box-shadow .15s; }}
    .event-card:hover {{ box-shadow: 0 4px 20px rgba(0,0,0,.12); }}
    .event-img-wrap {{ height: 160px; overflow: hidden; background: var(--border); }}
    .event-img {{ width: 100%; height: 100%; object-fit: cover; }}
    .event-img-placeholder {{ width: 100%; height: 100%; background: var(--border); }}
    .event-info {{ padding: 16px; flex: 1; display: flex; flex-direction: column; gap: 6px; }}
    .event-date-row {{ display: flex; align-items: center; gap: 8px; }}
    .event-date {{ font-size: 12px; font-weight: 600; color: var(--accent); text-transform: uppercase; letter-spacing: .5px; }}
    .event-free {{ font-size: 11px; background: var(--accent); color: white; padding: 2px 7px; border-radius: 20px; font-weight: 600; }}
    .event-name {{ font-size: 16px; font-weight: 600; color: var(--text); line-height: 1.35; margin: 0; }}
    .event-location {{ font-size: 12px; color: var(--text-sub); margin: 0; }}
    .event-desc {{ font-size: 13px; color: var(--text-sub); line-height: 1.5; margin: 0; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }}
    .no-events {{ text-align: center; color: var(--text-sub); padding: 64px 24px; font-size: 16px; }}
    @media(max-width:600px) {{ .events-grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <a href="/" class="wordmark">Treasure Coast Today</a>
      <nav class="category-nav">
        <a href="/" class="cat-btn" style="text-decoration:none">News</a>
        <span class="cat-btn active">Events</span>
      </nav>
      <div class="header-actions">
        <button class="theme-toggle" id="themeToggle" aria-label="Toggle theme">&#9790;</button>
        <a href="advertise.html" class="support-btn" style="text-decoration:none">Advertise</a>
      </div>
    </div>
  </header>

  <main>
    <div class="events-header">
      <h1>Upcoming Events</h1>
      <p>Things to do across Martin, St. Lucie &amp; Indian River counties &middot; Updated {ts}</p>
    </div>
    <div class="events-grid">
      {events_html}
    </div>
  </main>

  <footer>
    <div class="footer-inner">
      <span class="footer-wordmark">Treasure Coast Today</span>
      <span class="footer-tagline">Local news for Martin, St. Lucie &amp; Indian River counties.</span>
      <div class="footer-links">
        <a href="about.html">About</a>
        <a href="events.html">Events</a>
        <a href="privacy.html">Privacy</a>
        <a href="mailto:hello@treasurecoast.today">Contact</a>
      </div>
    </div>
  </footer>

  <script src="main.js"></script>
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


def main():
    print("Treasure Coast Today — building site...")
    image_bank = build_image_bank()
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

        source_img = data["hero"].get("image_url","")
        bank_img, bank_credit = ("","")
        if original_title:
            bank_img, bank_credit = match_image(original_title, image_bank, cat_key)
        if not bank_img:
            bank_img, bank_credit = match_image(hero_headline, image_bank, cat_key)
        if not bank_img:
            body_ctx = (original_title or hero_headline) + " " + data["hero"].get("body","")[:250]
            bank_img, bank_credit = match_image(body_ctx, image_bank, cat_key)

        img = source_img or bank_img
        if not img:
            link = data["hero"].get("link","")
            og   = fetch_og_image(link)
            if og:
                img = og
                bank_credit = get_image_credit(link)
                print(f"  Hero image via og:image")

        data["hero"]["image_url"]    = img
        data["hero"]["image_credit"] = bank_credit

        all_categories.append(data)
        print(f"  Hero: {data['hero']['headline'][:60]}... (urgency: {data['hero'].get('urgency_score')}, image: {'yes' if img else 'no'})")

    if not all_categories:
        print("No categories generated. Aborting.")
        return

    # Select front page hero
    top_cat = select_front_page_hero(all_categories)

    # Ensure no other category hero duplicates the front page hero
    promote_duplicate_heroes(top_cat, all_categories)

    # Render and write
    index_html = render_index(all_categories, top_cat)
    (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
    write_data_json(all_categories, top_cat)

    # Events page
    print("Fetching Eventbrite events...")
    events = fetch_eventbrite_events()
    events_html = render_events_page(events)
    (OUTPUT_DIR / "events.html").write_text(events_html, encoding="utf-8")
    print(f"Done. {len(all_categories)} categories, {len(events)} events written.")

if __name__ == "__main__":
    main()
