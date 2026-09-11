#!/usr/bin/env python3
"""Build TCT owned-audience, discovery, recirculation and local SEO features.

Runs after the core newsroom generator and event refresh.  This module deliberately
stays out of publication identity and article generation: it operates only on final
public presentation surfaces and deterministic archive/event metadata.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SITE_URL = "https://treasurecoast.today"
NEWSLETTER_URL = "https://treasure-coast-today.kit.com/cb848255f8"
PREFERRED_SOURCE_URL = "https://www.google.com/preferences/source?q=treasurecoast.today"
PREFERRED_SOURCE_SCRIPT = "https://news.google.com/swg/js/v1/publisher.js"
ASSET_VERSION = "1.13.8.6"

MEDIAVINE_SCRIPT_SRC = "//scripts.mediavine.com/tags/31bba1e2-0cf0-4381-8d83-ea54f9aa3bbf.js"
MEDIAVINE_SCRIPT_TAG = (
    '<script type="text/javascript" async="async" data-noptimize="1" data-cfasync="false" '
    f'src="{MEDIAVINE_SCRIPT_SRC}"></script>'
)


def _page_head(title: str, description: str, canonical_path: str = "", structured_data=None) -> str:
    canonical = f"{SITE_URL}{canonical_path}" if canonical_path else SITE_URL
    schema = ""
    if structured_data:
        schema = '<script type="application/ld+json">' + json.dumps(
            structured_data, ensure_ascii=False, separators=(",", ":")
        ) + '</script>'
    esc = html_lib.escape
    return f'''<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description, quote=True)}">
<link rel="canonical" href="{esc(canonical, quote=True)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title, quote=True)}">
<meta property="og:description" content="{esc(description, quote=True)}">
<meta property="og:url" content="{esc(canonical, quote=True)}">
<meta property="og:image" content="{SITE_URL}/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{SITE_URL}/og-image.png">
<meta name="geo.region" content="US-FL">
<meta name="geo.placename" content="Treasure Coast, Florida">
<meta name="google-adsense-account" content="ca-pub-9679836198092378">
<link rel="icon" href="/favicon.png" type="image/png">
<link rel="stylesheet" href="/style.css?v={ASSET_VERSION}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,500;0,9..144,600;1,9..144,300&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700;9..40,800&display=swap" rel="stylesheet">
{schema}
<script async src="https://www.googletagmanager.com/gtag/js?id=G-GLJY7M6F3G"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-GLJY7M6F3G');</script>'''


def _chrome_source() -> str:
    for name in ("about.html", "newsroom.html", "contact.html", "index.html"):
        path = ROOT / name
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "site-masthead" in text and "<footer" in text:
                return text
    raise RuntimeError("No current TCT chrome page is available")


def _page_header(active: str = "") -> str:
    text = _chrome_source()
    match = re.search(
        r'<header\b[^>]*class=["\'][^"\']*site-masthead[^"\']*["\'][^>]*>.*?</header>',
        text,
        re.I | re.S,
    )
    if not match:
        raise RuntimeError("Current TCT masthead could not be extracted")
    header = match.group(0)
    header = re.sub(r'\s+active(?=["\'])', '', header)
    header = re.sub(r'\s+aria-current=["\']page["\']', '', header)
    if active:
        href = f'/?cat={active}'
        header = header.replace(
            f'href="{href}" class="cat-btn"',
            f'href="{href}" class="cat-btn active"',
            1,
        )
        header = header.replace(
            f'href="{href}" class="mobile-nav-link"',
            f'href="{href}" class="mobile-nav-link active"',
            1,
        )
    return header


def _page_footer() -> str:
    text = _chrome_source()
    match = re.search(
        r'<footer\b.*?</footer>\s*(?:<script\s+src=["\']/main\.js[^>]*></script>)?',
        text,
        re.I | re.S,
    )
    if not match:
        raise RuntimeError("Current TCT footer could not be extracted")
    footer = match.group(0)
    if '/main.js' not in footer:
        footer += f'\n<script src="/main.js?v={ASSET_VERSION}"></script>'
    return footer


def _normalize_mediavine_script(text: str) -> str:
    pattern = re.compile(
        r'<script\b[^>]*src=["\'](?:https?:)?//scripts\.mediavine\.com/'
        r'tags/31bba1e2-0cf0-4381-8d83-ea54f9aa3bbf\.js["\'][^>]*>\s*</script>\s*',
        re.I,
    )
    text = pattern.sub('', text)
    close = re.search(r'</head\s*>', text, re.I)
    if not close:
        return text
    return text[:close.start()] + MEDIAVINE_SCRIPT_TAG + '\n' + text[close.start():]


def _apply_mediavine_sitewide(root: Path) -> dict:
    scanned = updated = 0
    for path in root.rglob('*.html'):
        original = path.read_text(encoding='utf-8', errors='ignore')
        if '</head' not in original.lower():
            continue
        scanned += 1
        text = _normalize_mediavine_script(original)
        if text != original:
            path.write_text(text, encoding='utf-8')
            updated += 1
    return {"scanned": scanned, "updated": updated}


CITY_CONFIG = [
    {"name": "Stuart", "slug": "stuart", "county": "Martin", "county_key": "martin", "aliases": ["stuart"]},
    {"name": "Jensen Beach", "slug": "jensen-beach", "county": "Martin", "county_key": "martin", "aliases": ["jensen beach"]},
    {"name": "Palm City", "slug": "palm-city", "county": "Martin", "county_key": "martin", "aliases": ["palm city"]},
    {"name": "Hobe Sound", "slug": "hobe-sound", "county": "Martin", "county_key": "martin", "aliases": ["hobe sound"]},
    {"name": "Port St. Lucie", "slug": "port-st-lucie", "county": "St. Lucie", "county_key": "st_lucie", "aliases": ["port st. lucie", "port st lucie", "port saint lucie"]},
    {"name": "Fort Pierce", "slug": "fort-pierce", "county": "St. Lucie", "county_key": "st_lucie", "aliases": ["fort pierce"]},
    {"name": "Vero Beach", "slug": "vero-beach", "county": "Indian River", "county_key": "indian_river", "aliases": ["vero beach"]},
    {"name": "Sebastian", "slug": "sebastian", "county": "Indian River", "county_key": "indian_river", "aliases": ["sebastian"]},
    {"name": "Fellsmere", "slug": "fellsmere", "county": "Indian River", "county_key": "indian_river", "aliases": ["fellsmere"]},
]
CITY_BY_SLUG = {row["slug"]: row for row in CITY_CONFIG}
COUNTY_KEY_LABEL = {"martin": "Martin County", "st_lucie": "St. Lucie County", "indian_river": "Indian River County"}
COUNTY_LABEL_KEY = {v: k for k, v in COUNTY_KEY_LABEL.items()}

STOPWORDS = {
    "the","a","an","and","or","but","of","for","to","in","on","at","by","with","from","after","before","over","under","as","is","are","was","were","be","been","being","this","that","these","those","its","it","their","his","her","they","he","she","will","would","could","should","new","news","florida","county","treasure","coast","today","says","said"
}

PREFERRED_MARKER_START = "<!-- TCT_PREFERRED_SOURCE_START -->"
PREFERRED_MARKER_END = "<!-- TCT_PREFERRED_SOURCE_END -->"
BREADCRUMB_MARKER_START = "<!-- TCT_BREADCRUMB_START -->"
BREADCRUMB_MARKER_END = "<!-- TCT_BREADCRUMB_END -->"
BREADCRUMB_JSONLD_START = "<!-- TCT_BREADCRUMB_JSONLD_START -->"
BREADCRUMB_JSONLD_END = "<!-- TCT_BREADCRUMB_JSONLD_END -->"
MOST_READ_HOME_START = "<!-- TCT_MOST_READ_HOME_START -->"
MOST_READ_HOME_END = "<!-- TCT_MOST_READ_HOME_END -->"
LEGACY_RECIRC_START = "<!-- TCT_LEGACY_RECIRC_START -->"
LEGACY_RECIRC_END = "<!-- TCT_LEGACY_RECIRC_END -->"


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.write_text(text, encoding="utf-8")


def _replace_marker(text: str, start: str, end: str, replacement: str) -> str:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.I | re.S)
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1)
    return text


def _clean_text(value) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(str(value or ""))).strip()


def _entry_county_keys(entry: dict) -> set[str]:
    keys: set[str] = set()
    for field in ("county_keys", "category_keys"):
        value = entry.get(field)
        if isinstance(value, list):
            keys.update(str(x).strip() for x in value if str(x).strip() in COUNTY_KEY_LABEL)
        elif isinstance(value, str):
            keys.update(x for x in re.split(r"[\s,]+", value) if x in COUNTY_KEY_LABEL)
    category_key = str(entry.get("category_key") or "")
    if category_key in COUNTY_KEY_LABEL:
        keys.add(category_key)
    category_label = str(entry.get("category_label") or "")
    if category_label in COUNTY_LABEL_KEY:
        keys.add(COUNTY_LABEL_KEY[category_label])
    return keys


def _word_match(text: str, alias: str) -> bool:
    pattern = r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])"
    return bool(re.search(pattern, text, re.I))


def _entry_cities(entry: dict) -> list[dict]:
    text = " ".join([_clean_text(entry.get("headline")), _clean_text(entry.get("teaser"))])
    county_keys = _entry_county_keys(entry)
    found: list[dict] = []
    for city in CITY_CONFIG:
        if county_keys and city["county_key"] not in county_keys:
            # Avoid place-name false positives across counties, while still allowing
            # records that predate county metadata to be discovered by text.
            continue
        if any(_word_match(text, alias) for alias in city["aliases"]):
            found.append(city)
    return found


def _primary_city(entry: dict) -> dict | None:
    cities = _entry_cities(entry)
    if not cities:
        return None
    headline = _clean_text(entry.get("headline"))
    for city in cities:
        if any(_word_match(headline, alias) for alias in city["aliases"]):
            return city
    return cities[0]


def _entry_url(entry: dict) -> str:
    slug = str(entry.get("canonical_slug") or entry.get("slug") or "").strip()
    return f"/articles/{slug}.html" if slug else "#"


def _entry_date(entry: dict) -> str:
    return str(entry.get("date") or entry.get("first_published") or "")[:10]


def _date_label(raw: str) -> str:
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").strftime("%b %-d, %Y")
    except Exception:
        return raw[:10]


def _render_story_card(entry: dict, *, compact: bool = False) -> str:
    esc = html_lib.escape
    image = str(entry.get("image_url") or "").strip()
    image_html = f'<img src="{esc(image, quote=True)}" alt="" loading="lazy">' if image else ""
    cls = "city-story-card city-story-card--compact" if compact else "city-story-card"
    return f'''<article class="{cls}">
  <a class="city-story-link" href="{esc(_entry_url(entry), quote=True)}">
    <div class="city-story-image">{image_html}</div>
    <div class="city-story-copy"><span class="city-story-category">{esc(str(entry.get("category_label") or "Local News"))}</span><h2>{esc(str(entry.get("headline") or ""))}</h2><p>{esc(_clean_text(entry.get("teaser")))}</p><time>{esc(_date_label(_entry_date(entry)))}</time></div>
  </a>
</article>'''


def render_city_pages(archive: list[dict]) -> dict:
    rendered = 0
    skipped = 0
    counts = {}
    for city in CITY_CONFIG:
        matches = [e for e in archive if city["slug"] in {c["slug"] for c in _entry_cities(e)} and str(e.get("slug") or "")]
        matches.sort(key=lambda e: (_entry_date(e), str(e.get("lastmod") or "")), reverse=True)
        counts[city["slug"]] = len(matches)
        if len(matches) < 3:
            skipped += 1
            continue
        latest = matches[:30]
        schema = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": f"{city['name']} News | Treasure Coast Today",
            "url": f"{SITE_URL}/{city['slug']}/",
            "description": f"Latest local news and updates from {city['name']}, Florida, from Treasure Coast Today.",
            "about": {"@type": "Place", "name": f"{city['name']}, Florida"},
            "mainEntity": {
                "@type": "ItemList",
                "itemListElement": [
                    {"@type": "ListItem", "position": i + 1, "url": f"{SITE_URL}{_entry_url(row)}", "name": row.get("headline", "")}
                    for i, row in enumerate(latest[:20])
                ],
            },
        }
        head = _page_head(
            f"{city['name']} News | Treasure Coast Today",
            f"Latest breaking news, government, crime, business, community and events coverage for {city['name']}, Florida.",
            f"/{city['slug']}/",
            structured_data=schema,
        )
        header = _page_header(active=city["county_key"])
        footer = _page_footer()
        sibling_links = " · ".join(
            f'<a href="/{other["slug"]}/">{html_lib.escape(other["name"])}</a>'
            for other in CITY_CONFIG if other["county_key"] == city["county_key"] and other["slug"] != city["slug"] and counts.get(other["slug"], 3) >= 3
        )
        cards = "\n".join(_render_story_card(row) for row in latest)
        page = f'''<!DOCTYPE html>
<html lang="en"><head>
{head}
</head><body>
{header}
<main class="city-page">
  <nav class="tct-breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a><span aria-hidden="true">›</span><a href="/?cat={city['county_key']}">{city['county']} County</a><span aria-hidden="true">›</span><span aria-current="page">{html_lib.escape(city['name'])}</span></nav>
  <header class="city-page-hero"><span class="city-page-eyebrow">{city['county']} County</span><h1>{html_lib.escape(city['name'])} News</h1><p>Latest reporting and updates from {html_lib.escape(city['name'])}, Florida.</p></header>
  <div class="city-page-grid">{cards}</div>
  <nav class="city-sibling-links" aria-label="More {city['county']} County communities"><strong>More {city['county']} County:</strong> {sibling_links}</nav>
  <a class="city-county-more" href="/?cat={city['county_key']}">View all {city['county']} County news →</a>
</main>
{footer}
</body></html>'''
        out = ROOT / city["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
        rendered += 1
    return {"rendered": rendered, "skipped": skipped, "counts": counts}


def render_searchable_archive(archive: list[dict]) -> dict:
    by_month: dict[tuple[str, str], list[dict]] = defaultdict(list)
    rows = []
    for e in sorted(archive, key=lambda x: _entry_date(x), reverse=True):
        if not str(e.get("slug") or "").strip():
            continue
        date = _entry_date(e)
        try:
            key = date[:7]
            label = datetime.strptime(key, "%Y-%m").strftime("%B %Y")
        except Exception:
            key, label = "recent", "Recent"
        cities = _entry_cities(e)
        city_slugs = " ".join(c["slug"] for c in cities)
        county_keys = " ".join(sorted(_entry_county_keys(e)))
        record = dict(e)
        record["_city_slugs"] = city_slugs
        record["_county_keys"] = county_keys
        by_month[(key, label)].append(record)
        rows.append(record)
    month_html = []
    for (_, label), entries in sorted(by_month.items(), reverse=True):
        items = []
        for e in entries:
            search = _clean_text(" ".join([str(e.get("headline") or ""), str(e.get("teaser") or ""), e.get("_city_slugs", ""), e.get("_county_keys", "")])).lower()
            items.append(f'''<li class="archive-item" data-archive-item data-search="{html_lib.escape(search, quote=True)}" data-category="{html_lib.escape(str(e.get('category_key') or ''), quote=True)}" data-counties="{html_lib.escape(e.get('_county_keys',''), quote=True)}" data-cities="{html_lib.escape(e.get('_city_slugs',''), quote=True)}" data-date="{html_lib.escape(_entry_date(e), quote=True)}">
<a href="{html_lib.escape(_entry_url(e), quote=True)}" class="archive-link"><span class="archive-cat">{html_lib.escape(str(e.get('category_label') or 'Local News'))}</span><span class="archive-story-headline">{html_lib.escape(str(e.get('headline') or ''))}</span><span class="archive-date">{html_lib.escape(_entry_date(e))}</span></a></li>''')
        month_html.append(f'<section class="archive-month" data-archive-month><h2 class="archive-month-label">{html_lib.escape(label)}</h2><ul class="archive-list">{"".join(items)}</ul></section>')

    category_options = sorted({(str(e.get("category_key") or ""), str(e.get("category_label") or "")) for e in rows if e.get("category_key") and e.get("category_label")})
    city_options = "".join(f'<option value="{c["slug"]}">{html_lib.escape(c["name"])}</option>' for c in CITY_CONFIG)
    category_option_html = "".join(f'<option value="{html_lib.escape(k, quote=True)}">{html_lib.escape(v)}</option>' for k,v in category_options)
    head = _page_head("Article Archive | Treasure Coast Today", "Search and browse Treasure Coast Today local news by keyword, county, city, category and date.", "/archive.html")
    page = f'''<!DOCTYPE html><html lang="en"><head>{head}</head><body>
{_page_header(active='archive')}
<main><div class="archive-wrap archive-wrap--searchable">
<span class="archive-eyebrow">Archive</span><h1 class="archive-page-title">Search TCT News</h1><p class="archive-sub">Search every published Treasure Coast Today story, or browse chronologically below.</p>
<form class="archive-search-panel" data-archive-form onsubmit="return false">
<label class="archive-search-keyword"><span>Keyword</span><input type="search" data-archive-query placeholder="Search headlines and story summaries" autocomplete="off"></label>
<label><span>County</span><select data-archive-county><option value="">All counties</option><option value="martin">Martin County</option><option value="st_lucie">St. Lucie County</option><option value="indian_river">Indian River County</option></select></label>
<label><span>City</span><select data-archive-city><option value="">All cities</option>{city_options}</select></label>
<label><span>Category</span><select data-archive-category><option value="">All categories</option>{category_option_html}</select></label>
<label><span>From</span><input type="date" data-archive-from></label><label><span>To</span><input type="date" data-archive-to></label>
<div class="archive-search-actions"><strong><span data-archive-count>{len(rows)}</span> stories</strong><button type="button" data-archive-reset>Reset</button></div>
</form>
<div class="archive-no-results" data-archive-empty hidden>No stories match those filters.</div>
<div data-archive-results>{''.join(month_html)}</div>
</div></main>
{_page_footer()}
<script data-tct-archive-search>
(() => {{
 const q=document.querySelector('[data-archive-query]'), county=document.querySelector('[data-archive-county]'), city=document.querySelector('[data-archive-city]'), cat=document.querySelector('[data-archive-category]'), from=document.querySelector('[data-archive-from]'), to=document.querySelector('[data-archive-to]'), count=document.querySelector('[data-archive-count]'), empty=document.querySelector('[data-archive-empty]'), reset=document.querySelector('[data-archive-reset]');
 const items=[...document.querySelectorAll('[data-archive-item]')], months=[...document.querySelectorAll('[data-archive-month]')];
 function apply() {{ const needle=(q.value||'').trim().toLowerCase(); let visible=0; items.forEach(item=>{{ const ok=(!needle||item.dataset.search.includes(needle))&&(!county.value||(item.dataset.counties||'').split(/\\s+/).includes(county.value))&&(!city.value||(item.dataset.cities||'').split(/\\s+/).includes(city.value))&&(!cat.value||item.dataset.category===cat.value)&&(!from.value||item.dataset.date>=from.value)&&(!to.value||item.dataset.date<=to.value); item.hidden=!ok; if(ok) visible++; }}); months.forEach(m=>m.hidden=!m.querySelector('[data-archive-item]:not([hidden])')); count.textContent=String(visible); empty.hidden=visible!==0; }}
 [q,county,city,cat,from,to].forEach(el=>el.addEventListener(el===q?'input':'change',apply)); reset.addEventListener('click',()=>{{q.value='';county.value='';city.value='';cat.value='';from.value='';to.value='';apply();q.focus();}}); apply();
}})();
</script>
</body></html>'''
    (ROOT / "archive.html").write_text(page, encoding="utf-8")
    return {"stories": len(rows), "months": len(by_month)}


def render_news_tip_page() -> None:
    schema = {"@context": "https://schema.org", "@type": "ContactPage", "name": "Send a News Tip | Treasure Coast Today", "url": f"{SITE_URL}/news-tip.html", "description": "Contact the Treasure Coast Today newsroom with a local news tip."}
    head = _page_head("Send a News Tip | Treasure Coast Today", "Contact the Treasure Coast Today newsroom about a local story, issue, document, photo or event we should investigate.", "/news-tip.html", structured_data=schema)
    page = f'''<!DOCTYPE html><html lang="en"><head>{head}</head><body>
{_page_header(active='')}
<main class="news-tip-page"><div class="news-tip-shell">
<nav class="tct-breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a><span aria-hidden="true">›</span><a href="/newsroom.html">Newsroom</a><span aria-hidden="true">›</span><span aria-current="page">Send a News Tip</span></nav>
<header class="news-tip-hero"><span class="news-tip-eyebrow">TCT Newsroom</span><h1>Send us a news tip</h1><p>Know something happening in Martin, St. Lucie or Indian River County that we should look into? Contact the newsroom directly.</p></header>
<div class="news-tip-layout"><section class="news-tip-contact-card">
<h2>Email the TCT newsroom</h2>
<p>Tell us what happened, where and when it happened, why it matters, and how you know about it. You can attach supporting photos or documents in your email.</p>
<a class="news-tip-email-button" href="mailto:hello@treasurecoast.today?subject=News%20tip%20for%20Treasure%20Coast%20Today">Email a news tip</a>
<p class="news-tip-email-address"><a href="mailto:hello@treasurecoast.today">hello@treasurecoast.today</a></p>
<p class="news-tip-privacy">There is currently no web submission form on this page. Your email is sent through your own email provider directly to Treasure Coast Today.</p>
</section><aside class="news-tip-aside"><h2>What makes a useful tip?</h2><p>Specific details help: names, dates, locations, public documents, photos and how you learned about the situation.</p><h2>Emergency?</h2><p>Do not use email for emergencies. Call 911 or the appropriate local agency.</p><p class="news-tip-privacy">Avoid sending sensitive personal information unless it is necessary to understand the tip. Sending a tip does not guarantee publication.</p></aside></div>
</div></main>
{_page_footer()}
</body></html>'''
    (ROOT / "news-tip.html").write_text(page, encoding="utf-8")


def _token_set(entry: dict) -> set[str]:
    text = _clean_text(" ".join([str(entry.get("headline") or ""), str(entry.get("teaser") or "")])).lower()
    return {t for t in re.findall(r"[a-z0-9']+", text) if len(t) >= 4 and t not in STOPWORDS}


def _related_entries(entry: dict, candidates: list[dict], limit: int = 5) -> tuple[str, list[dict]]:
    current_slug = str(entry.get("canonical_slug") or entry.get("slug") or "")
    current_tokens = entry.get("_tct_tokens") or _token_set(entry)
    current_cities = entry.get("_tct_cities") or {c["slug"] for c in _entry_cities(entry)}
    current_counties = entry.get("_tct_counties") or _entry_county_keys(entry)
    event_key = str(entry.get("editorial_event_key") or "").strip()
    anchor_key = str(entry.get("incident_anchor_key") or "").strip()
    series_key = str(entry.get("custom_series_key") or "").strip()
    scored = []
    for candidate in candidates:
        slug = str(candidate.get("canonical_slug") or candidate.get("slug") or "")
        if not slug or slug == current_slug:
            continue
        score = 0.0
        candidate_event = str(candidate.get("editorial_event_key") or "").strip()
        candidate_anchor = str(candidate.get("incident_anchor_key") or "").strip()
        candidate_series = str(candidate.get("custom_series_key") or "").strip()
        exact_identity = False
        if event_key and candidate_event == event_key:
            score += 500; exact_identity = True
        if anchor_key and candidate_anchor == anchor_key:
            score += 450; exact_identity = True
        if series_key and candidate_series == series_key:
            score += 300; exact_identity = True
        cities = candidate.get("_tct_cities") or set()
        if current_cities & cities:
            score += 120
        if current_counties & (candidate.get("_tct_counties") or set()):
            score += 60
        if candidate.get("category_key") == entry.get("category_key"):
            score += 45
        tokens = candidate.get("_tct_tokens") or set()
        if current_tokens and tokens:
            overlap = len(current_tokens & tokens)
            union = len(current_tokens | tokens)
            score += 100 * (overlap / union if union else 0)
            score += min(30, overlap * 6)
        current_dt = entry.get("_tct_date_dt")
        candidate_dt = candidate.get("_tct_date_dt")
        if current_dt and candidate_dt:
            age = abs((current_dt - candidate_dt).days)
            score += max(0, 30 - min(30, age))
        if score >= 50:
            scored.append((score, _entry_date(candidate), exact_identity, candidate))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    picked = [row[3] for row in scored[:limit]]
    identity_hit = any(row[2] for row in scored[:limit])
    return ("More on this story" if identity_hit else "Related Coverage", picked)

def _render_related_section(title: str, rows: list[dict]) -> str:
    items = "".join(
        f'<li class="related-item"><a class="related-link" href="{html_lib.escape(_entry_url(row), quote=True)}"><span class="related-headline">{html_lib.escape(str(row.get("headline") or ""))}</span><span class="related-date">{html_lib.escape(_entry_date(row))}</span></a></li>'
        for row in rows
    )
    if not items:
        items = '<li class="related-item related-empty">More local reporting is on the way.</li>'
    return f'<section class="related-section related-section--smart"><h2 class="related-title">{html_lib.escape(title)}</h2><ul class="related-list">{items}</ul><a class="related-more-link" href="/archive.html">Search all TCT stories →</a></section>'


def _preferred_source_module(compact: bool = True) -> str:
    cls = "preferred-source-card preferred-source-card--compact" if compact else "preferred-source-card"
    return f'''{PREFERRED_MARKER_START}<section class="{cls}" aria-label="Follow Treasure Coast Today in Google"><span class="preferred-source-kicker">Google News</span><h2>See more TCT in Google</h2><p>Choose Treasure Coast Today as a preferred source for local coverage.</p><div google-add-preferred-source-btn data-lang="en"></div><a class="preferred-source-fallback" href="{PREFERRED_SOURCE_URL}" target="_blank" rel="noopener">Manage preferred sources →</a></section>{PREFERRED_MARKER_END}'''


def _most_read_module(compact: bool = True) -> str:
    cls = "most-read-module most-read-module--compact" if compact else "most-read-module"
    return f'<section class="{cls}" data-tct-most-read hidden><div class="most-read-head"><span>Trending</span><h2>Most Read</h2></div><ol data-tct-most-read-list></ol><p class="most-read-window">Most-read TCT stories over the past 24 hours.</p></section>'


def _ensure_preferred_script(text: str) -> str:
    if PREFERRED_SOURCE_SCRIPT in text:
        return text
    close = re.search(r"</head\s*>", text, re.I)
    if not close:
        return text
    tag = f'<script async src="{PREFERRED_SOURCE_SCRIPT}"></script>\n'
    return text[:close.start()] + tag + text[close.start():]


def _breadcrumb_for(entry: dict) -> tuple[str, dict]:
    city = _primary_city(entry)
    counties = _entry_county_keys(entry)
    category_key = str(entry.get("category_key") or "")
    category_label = str(entry.get("category_label") or "Local News")
    items = [("Home", "/")]
    if city:
        items.append((f"{city['county']} County", f"/?cat={city['county_key']}"))
        items.append((city["name"], f"/{city['slug']}/"))
    elif category_key in COUNTY_KEY_LABEL:
        items.append((COUNTY_KEY_LABEL[category_key], f"/?cat={category_key}"))
    else:
        items.append((category_label, f"/?cat={category_key}" if category_key else "/"))
    visible = BREADCRUMB_MARKER_START + '<nav class="tct-breadcrumb tct-breadcrumb--article" aria-label="Breadcrumb">' + ''.join(
        f'<a href="{html_lib.escape(url, quote=True)}">{html_lib.escape(label)}</a><span aria-hidden="true">›</span>' for label,url in items
    ) + f'<span class="tct-breadcrumb-current" aria-current="page">{html_lib.escape(str(entry.get("headline") or "Story"))}</span></nav>' + BREADCRUMB_MARKER_END
    schema_items = []
    for pos, (label, url) in enumerate(items, 1):
        schema_items.append({"@type": "ListItem", "position": pos, "name": label, "item": f"{SITE_URL}{url}"})
    schema_items.append({"@type": "ListItem", "position": len(schema_items)+1, "name": str(entry.get("headline") or "Story"), "item": f"{SITE_URL}{_entry_url(entry)}"})
    schema = {"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":schema_items}
    return visible, schema


def _ensure_newsarticle_schema(text: str, entry: dict) -> str:
    pattern = re.compile(r'(<script\s+type=["\']application/ld\+json["\'][^>]*>)(.*?)(</script>)', re.I | re.S)
    desired_author = {"@type":"Person","name":"Andrew Dobrow","url":f"{SITE_URL}/author/andrew-dobrow.html"}
    slug = str(entry.get("canonical_slug") or entry.get("slug") or "").strip()
    url = f"{SITE_URL}/articles/{slug}.html"
    published = str(entry.get("canonical_first_published_at") or entry.get("first_published") or entry.get("date") or "").strip()
    modified = str(entry.get("canonical_last_material_update_at") or entry.get("lastmod") or published or entry.get("date") or "").strip()
    paywalled = bool(re.search(r'(?<![\w-])data-tct-paywall(?![\w-])|tct-paywalled-content', text, re.I))
    found = False
    for match in list(pattern.finditer(text)):
        try:
            data = json.loads(match.group(2).strip())
        except Exception:
            continue
        objects = data if isinstance(data, list) else [data]
        target = next((obj for obj in objects if isinstance(obj, dict) and obj.get("@type") in {"NewsArticle","Article"}), None)
        if target is None:
            continue
        found = True
        target["@context"] = target.get("@context") or "https://schema.org"
        target["@type"] = "NewsArticle"
        target["headline"] = str(entry.get("headline") or target.get("headline") or "")
        target["description"] = _clean_text(entry.get("teaser")) or target.get("description") or ""
        image = str(entry.get("image_url") or "").strip()
        if image and not target.get("image"):
            target["image"] = [image]
        target["datePublished"] = target.get("datePublished") or published or _entry_date(entry)
        target["dateModified"] = target.get("dateModified") or modified or target.get("datePublished")
        target["author"] = desired_author
        target["publisher"] = target.get("publisher") or {"@type":"Organization","name":"Treasure Coast Today","url":SITE_URL,"logo":{"@type":"ImageObject","url":f"{SITE_URL}/logo.png","width":1200,"height":120}}
        target["articleSection"] = target.get("articleSection") or str(entry.get("category_label") or "Local News")
        target["url"] = url
        target["mainEntityOfPage"] = {"@type":"WebPage","@id":url}
        if paywalled:
            target["isAccessibleForFree"] = False
            target["hasPart"] = {"@type":"WebPageElement","isAccessibleForFree":False,"cssSelector":".tct-paywalled-content"}
        elif "isAccessibleForFree" not in target:
            target["isAccessibleForFree"] = True
        rendered = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        text = text[:match.start()] + match.group(1) + rendered + match.group(3) + text[match.end():]
        break
    if found:
        return text
    data = {
        "@context":"https://schema.org","@type":"NewsArticle","headline":str(entry.get("headline") or ""),
        "description":_clean_text(entry.get("teaser")),"datePublished":published or _entry_date(entry),
        "dateModified":modified or published or _entry_date(entry),"author":desired_author,
        "publisher":{"@type":"Organization","name":"Treasure Coast Today","url":SITE_URL,"logo":{"@type":"ImageObject","url":f"{SITE_URL}/logo.png","width":1200,"height":120}},
        "articleSection":str(entry.get("category_label") or "Local News"),"url":url,
        "mainEntityOfPage":{"@type":"WebPage","@id":url},"isAccessibleForFree":not paywalled,
    }
    image = str(entry.get("image_url") or "").strip()
    if image:
        data["image"] = [image]
    if paywalled:
        data["hasPart"] = {"@type":"WebPageElement","isAccessibleForFree":False,"cssSelector":".tct-paywalled-content"}
    tag = '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + '</script>'
    close = re.search(r'</head\s*>', text, re.I)
    return text[:close.start()] + tag + '\n' + text[close.start():] if close else text

def enhance_articles(archive: list[dict]) -> dict:
    # Related-story scoring is intentionally presentation-only. Precompute the
    # expensive text/geography features once, then score against a bounded recent
    # pool so this postprocessor stays fast even as the archive grows.
    for e in archive:
        e["_tct_tokens"] = _token_set(e)
        e["_tct_cities"] = {c["slug"] for c in _entry_cities(e)}
        e["_tct_counties"] = _entry_county_keys(e)
        try:
            e["_tct_date_dt"] = datetime.strptime(_entry_date(e), "%Y-%m-%d")
        except Exception:
            e["_tct_date_dt"] = None
    candidates = sorted(archive, key=lambda e: _entry_date(e), reverse=True)[:300]
    index = {str(e.get("slug") or ""): e for e in archive if str(e.get("slug") or "")}
    # Canonical slugs can differ from retained row slugs after historical migrations.
    for e in archive:
        canonical = str(e.get("canonical_slug") or "")
        if canonical:
            index.setdefault(canonical, e)
    scanned = updated = skipped = 0
    for path in sorted((ROOT / "articles").glob("*.html")):
        slug = path.stem
        entry = index.get(slug)
        if not entry:
            skipped += 1; continue
        original = path.read_text(encoding="utf-8", errors="ignore")
        # Skip pure redirect shells and other non-article retained pages.
        if "article-headline" not in original or "article-meta" not in original:
            skipped += 1; continue
        scanned += 1
        text = original
        # Article pages should not inherit the generic page-level top padding;
        # the article wrapper owns its spacing. Normalize retained shells too.
        text = re.sub(r'<main(?![^>]*\bclass=)([^>]*)>', r'<main class="article-page-main"\1>', text, count=1, flags=re.I)
        text = re.sub(
            r'<main\b([^>]*\bclass=["\'])([^"\']*)(["\'][^>]*)>',
            lambda m: m.group(0) if "article-page-main" in m.group(2).split() else '<main' + m.group(1) + (m.group(2) + ' article-page-main').strip() + m.group(3) + '>',
            text, count=1, flags=re.I,
        )
        visible_breadcrumb, breadcrumb_schema = _breadcrumb_for(entry)
        text = _replace_marker(text, BREADCRUMB_MARKER_START, BREADCRUMB_MARKER_END, visible_breadcrumb)
        if BREADCRUMB_MARKER_START not in text:
            marker = re.search(r'<div\s+class=["\']article-meta["\']', text, re.I)
            if marker:
                text = text[:marker.start()] + visible_breadcrumb + "\n      " + text[marker.start():]
        breadcrumb_json = BREADCRUMB_JSONLD_START + '<script type="application/ld+json" data-tct-breadcrumb-jsonld>' + json.dumps(breadcrumb_schema, ensure_ascii=False, separators=(",", ":")) + '</script>' + BREADCRUMB_JSONLD_END
        text = _replace_marker(text, BREADCRUMB_JSONLD_START, BREADCRUMB_JSONLD_END, breadcrumb_json)
        if BREADCRUMB_JSONLD_START not in text:
            close = re.search(r"</head\s*>", text, re.I)
            if close:
                text = text[:close.start()] + breadcrumb_json + "\n" + text[close.start():]
        text = _ensure_newsarticle_schema(text, entry)
        title, related = _related_entries(entry, candidates)
        side = '<aside class="article-side-rail">' + _render_related_section(title, related) + _most_read_module(True) + _preferred_source_module(True) + '</aside>'
        text, side_replacements = re.subn(r'<aside\s+class=["\']article-side-rail["\']>.*?</aside>', side, text, count=1, flags=re.I | re.S)
        if side_replacements == 0:
            # Earliest retained article shells predate the editorial two-column rail.
            # Normalize any prior unmarked rollout copies, then keep exactly one
            # marker-bounded recirculation block so reruns are fixed-point stable.
            # Remove only pre-marker rollout copies. Marker-bounded copies are
            # replaced in place below so whitespace cannot accumulate across runs.
            text = re.sub(
                r'(?<!TCT_LEGACY_RECIRC_START -->)<div\s+class=["\']legacy-article-recirculation["\']>.*?'
                + re.escape(PREFERRED_MARKER_END) + r'\s*</div>(?!<!-- TCT_LEGACY_RECIRC_END -->)',
                '', text, flags=re.I | re.S,
            )
            legacy_module = LEGACY_RECIRC_START + '<div class="legacy-article-recirculation">' + _render_related_section(title, related) + _most_read_module(True) + _preferred_source_module(True) + '</div>' + LEGACY_RECIRC_END
            if LEGACY_RECIRC_START in text:
                text = _replace_marker(text, LEGACY_RECIRC_START, LEGACY_RECIRC_END, legacy_module)
            else:
                main_close = re.search(r'</div>\s*</main>', text, re.I)
                if main_close:
                    text = text[:main_close.start()] + '\n      ' + legacy_module + text[main_close.start():]
        # Older page shells can have a second generic related list after the editorial grid.
        # Keep one authoritative smart module in the side rail and remove only that duplicate.
        grid_end = re.search(r'</div>\s*<a href=["\'][^"\']+["\'] class=["\']article-more-link["\']', text, re.I)
        if grid_end:
            tail = text[grid_end.end():]
            tail2 = re.sub(r'\s*<section\s+class=["\']related-section["\']>.*?</section>', '', tail, count=1, flags=re.I | re.S)
            text = text[:grid_end.end()] + tail2
        text = _ensure_preferred_script(text)
        if text != original:
            path.write_text(text, encoding="utf-8")
            updated += 1
    return {"scanned": scanned, "updated": updated, "skipped": skipped}


def write_story_index(archive: list[dict]) -> int:
    rows = {}
    for e in archive:
        slug = str(e.get("canonical_slug") or e.get("slug") or "").strip()
        if not slug:
            continue
        cities = [city["name"] for city in _entry_cities(e)]
        counties = [COUNTY_KEY_LABEL[key] for key in sorted(_entry_county_keys(e)) if key in COUNTY_KEY_LABEL]
        rows[slug] = {
            "url": f"/articles/{slug}.html",
            "headline": str(e.get("headline") or ""),
            "teaser": _clean_text(e.get("teaser") or e.get("summary") or ""),
            "category": str(e.get("category_label") or "Local News"),
            "date": _entry_date(e),
            "cities": cities,
            "counties": counties,
        }
    _write_json(ROOT / "data" / "story-index.json", {"schema_version":2,"stories":rows})
    return len(rows)


EVENT_DETAIL_GRACE_DAYS = 30
EVENT_TZ = ZoneInfo("America/New_York")
def _event_now() -> datetime:
    forced = str(os.environ.get("TCT_EVENTS_NOW", "")).strip()
    if forced:
        parsed = datetime.fromisoformat(forced.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=EVENT_TZ)
        return parsed.astimezone(EVENT_TZ)
    return datetime.now(EVENT_TZ)


def _parse_event_datetime(raw: object) -> datetime | None:
    value = _clean_text(raw)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=EVENT_TZ)
    return parsed.astimezone(EVENT_TZ)


def _event_effective_end(event: dict) -> datetime | None:
    start = _parse_event_datetime(event.get("starts_at"))
    end = _parse_event_datetime(event.get("ends_at"))
    if end is not None and (start is None or end >= start):
        return end
    if start is not None:
        return start + timedelta(hours=4)
    return None


def _event_slug(title: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", _clean_text(title).lower()).strip("-")
    return value[:70].rstrip("-") or "event"


def _event_detail_path(event: dict) -> str:
    return f"/events/{event['id']}-{_event_slug(str(event.get('title') or 'event'))}.html"


def _event_detail_eligible(event: dict) -> bool:
    if not (_clean_text(event.get("title")) and _clean_text(event.get("starts_at"))):
        return False
    if not (_clean_text(event.get("venue")) or _clean_text(event.get("city"))):
        return False
    substantive = any(_clean_text(event.get(field)) for field in ("description","price","ticket_url","address"))
    event_url = _clean_text(event.get("event_url")); source_url = _clean_text(event.get("source_url"))
    if event_url and source_url and event_url != source_url:
        substantive = True
    return substantive


def _format_event_datetime(raw: str) -> str:
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%A, %B %-d, %Y at %-I:%M %p")
    except Exception:
        return raw


def _event_retention_overrides() -> tuple[set[str], set[str]]:
    payload = _read_json(ROOT / "data" / "events-retention.json", {})
    if not isinstance(payload, dict):
        return set(), set()
    ids = {_clean_text(value) for value in payload.get("retain_ids", []) if _clean_text(value)}
    paths = set()
    for value in payload.get("retain_paths", []):
        value = _clean_text(value)
        if not value:
            continue
        if not value.startswith("/"):
            value = "/" + value
        if value.startswith("/events/") and value.endswith(".html"):
            paths.add(value)
    return ids, paths


def _event_page_id(path: Path, text: str) -> str:
    meta = re.search(r'<meta\s+name=["\']tct-event-id["\']\s+content=["\']([^"\']+)["\']\s*/?>', text, re.I)
    if meta:
        return _clean_text(meta.group(1))
    match = re.match(r"([a-f0-9]{18,})-", path.name, re.I)
    return match.group(1) if match else ""


def _event_page_lifecycle_end(text: str) -> datetime | None:
    meta = re.search(r'<meta\s+name=["\']tct-event-lifecycle-end["\']\s+content=["\']([^"\']+)["\']\s*/?>', text, re.I)
    if meta:
        parsed = _parse_event_datetime(meta.group(1))
        if parsed is not None:
            return parsed
    for match in re.finditer(r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', text, re.I | re.S):
        try:
            payload = json.loads(html_lib.unescape(match.group(1)).strip())
        except Exception:
            continue
        candidates = payload.get("@graph", []) if isinstance(payload, dict) and isinstance(payload.get("@graph"), list) else [payload]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            kinds = candidate.get("@type")
            kinds = kinds if isinstance(kinds, list) else [kinds]
            if "Event" not in kinds:
                continue
            parsed_end = _parse_event_datetime(candidate.get("endDate"))
            if parsed_end is not None:
                return parsed_end
            parsed_start = _parse_event_datetime(candidate.get("startDate"))
            if parsed_start is not None:
                return parsed_start + timedelta(hours=4)
    return None


def _remove_event_jsonld(text: str) -> str:
    pattern = re.compile(r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)

    def repl(match: re.Match) -> str:
        try:
            payload = json.loads(html_lib.unescape(match.group(1)).strip())
        except Exception:
            return match.group(0)
        candidates = payload.get("@graph", []) if isinstance(payload, dict) and isinstance(payload.get("@graph"), list) else [payload]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            kinds = candidate.get("@type")
            kinds = kinds if isinstance(kinds, list) else [kinds]
            if "Event" in kinds:
                return ""
        return match.group(0)

    return pattern.sub(repl, text)


def _mark_event_page_ended(text: str, end_at: datetime, *, retained: bool) -> str:
    text = _remove_event_jsonld(text)
    text = re.sub(r'\s*<meta\s+name=["\']robots["\'][^>]*>', '', text, flags=re.I)
    lifecycle = end_at.isoformat(timespec="seconds")
    if not re.search(r'name=["\']tct-event-lifecycle-end["\']', text, re.I):
        text = text.replace('</head>', f'<meta name="tct-event-lifecycle-end" content="{html_lib.escape(lifecycle, quote=True)}">\n</head>', 1)
    if not retained:
        text = text.replace('</head>', '<meta name="robots" content="noindex,follow">\n</head>', 1)
    if 'data-tct-event-ended' not in text:
        notice = '<p class="event-detail-ended" data-tct-event-ended><strong>This event has ended.</strong> Browse current Treasure Coast events below.</p>'
        text, count = re.subn(r'(<p\s+class="event-detail-when"[^>]*>.*?</p>)', r'\1' + notice, text, count=1, flags=re.I | re.S)
        if count == 0:
            text = text.replace('</header>', notice + '</header>', 1)
    return text


def _retained_event_paths() -> set[str]:
    retain_ids, retain_paths = _event_retention_overrides()
    event_dir = ROOT / "events"
    if event_dir.exists() and retain_ids:
        for path in event_dir.glob("*.html"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if _event_page_id(path, text) in retain_ids:
                retain_paths.add("/" + path.relative_to(ROOT).as_posix())
    return retain_paths


def render_event_detail_pages() -> dict:
    path = ROOT / "data" / "events.json"
    payload = _read_json(path, {})
    events = payload.get("events") if isinstance(payload, dict) else []
    if not isinstance(events, list):
        return {"rendered":0,"eligible":0,"recently_ended":0,"removed":0,"retained":0}
    event_dir = ROOT / "events"
    event_dir.mkdir(exist_ok=True)
    expected_paths: set[Path] = set()
    rendered = 0
    now = _event_now()
    retain_ids, retain_paths = _event_retention_overrides()
    for event in events:
        if not isinstance(event, dict) or not _event_detail_eligible(event):
            event.pop("detail_url", None)
            continue
        detail_path = _event_detail_path(event)
        event["detail_url"] = detail_path
        expected_paths.add((ROOT / detail_path.lstrip("/")).resolve())
        start = _format_event_datetime(str(event.get("starts_at") or ""))
        end = _format_event_datetime(str(event.get("ends_at") or ""))
        location = ", ".join(x for x in [_clean_text(event.get("venue")), _clean_text(event.get("address")), _clean_text(event.get("city"))] if x)
        title = _clean_text(event.get("title"))
        description = _clean_text(event.get("description")) or f"Event details for {title} on the Treasure Coast."
        schema = {"@context":"https://schema.org","@type":"Event","name":title,"startDate":event.get("starts_at"),"url":f"{SITE_URL}{detail_path}","eventStatus":"https://schema.org/EventScheduled","eventAttendanceMode":"https://schema.org/OfflineEventAttendanceMode"}
        if event.get("ends_at"): schema["endDate"] = event.get("ends_at")
        if description: schema["description"] = description
        if event.get("venue") or event.get("city"):
            schema["location"]={"@type":"Place","name":event.get("venue") or event.get("city"),"address":{"@type":"PostalAddress","streetAddress":event.get("address", ""),"addressLocality":event.get("city", ""),"addressRegion":"FL"}}
        if event.get("event_url"): schema["sameAs"] = event.get("event_url")
        lifecycle_end = _event_effective_end(event)
        lifecycle_meta = ''
        if lifecycle_end is not None:
            lifecycle_meta += f'\n<meta name="tct-event-lifecycle-end" content="{html_lib.escape(lifecycle_end.isoformat(timespec="seconds"), quote=True)}">'
        lifecycle_meta += f'\n<meta name="tct-event-id" content="{html_lib.escape(_clean_text(event.get("id")), quote=True)}">'
        head = _page_head(f"{title} | Treasure Coast Events", description[:155], detail_path, structured_data=schema) + lifecycle_meta
        source_url = _clean_text(event.get("source_url")); event_url = _clean_text(event.get("event_url")); ticket_url = _clean_text(event.get("ticket_url"))
        source_link = f'<a href="{html_lib.escape(source_url, quote=True)}" target="_blank" rel="noopener noreferrer external">{html_lib.escape(_clean_text(event.get("source_name")) or "Official source")}</a>' if source_url else "Official source"
        official = event_url or source_url
        official_link = f'<a class="event-detail-primary" href="{html_lib.escape(official, quote=True)}" target="_blank" rel="noopener noreferrer external">Official event page →</a>' if official else ""
        tickets = f'<a class="event-detail-secondary" href="{html_lib.escape(ticket_url, quote=True)}" target="_blank" rel="noopener noreferrer external">Tickets →</a>' if ticket_url and ticket_url != official else ""
        page = f'''<!DOCTYPE html><html lang="en"><head>{head}</head><body data-tct-event-detail data-event-id="{html_lib.escape(_clean_text(event.get('id')), quote=True)}">
{_page_header(active='events')}
<main class="event-detail-page"><div class="event-detail-shell">
<nav class="tct-breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a><span aria-hidden="true">›</span><a href="/events.html">Events</a><span aria-hidden="true">›</span><span aria-current="page">{html_lib.escape(title)}</span></nav>
<header class="event-detail-hero"><span class="event-detail-category">{html_lib.escape(_clean_text(event.get('category')))}</span><h1>{html_lib.escape(title)}</h1><p class="event-detail-when">{html_lib.escape(start)}</p></header>
<div class="event-detail-grid"><article class="event-detail-main">
<dl class="event-detail-facts"><div><dt>When</dt><dd>{html_lib.escape(start)}{(' – ' + html_lib.escape(end)) if end and end != start else ''}</dd></div><div><dt>Where</dt><dd>{html_lib.escape(location or _clean_text(event.get('county')) + ' County')}</dd></div>{f'<div><dt>Price</dt><dd>{html_lib.escape(_clean_text(event.get("price")))}</dd></div>' if event.get('price') else ''}</dl>
<p class="event-detail-description">{html_lib.escape(description)}</p><div class="event-detail-actions">{official_link}{tickets}</div>
<p class="event-detail-source">Event information from {source_link}. Details can change; verify with the organizer before attending.</p>
</article><aside class="event-detail-aside"><h2>More Treasure Coast events</h2><p>Browse concerts, community events, family activities, arts, markets and more across Martin, St. Lucie and Indian River counties.</p><a href="/events.html">Browse the full calendar →</a></aside></div>
</div></main>
{_page_footer()}
</body></html>'''
        out = ROOT / detail_path.lstrip("/")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
        rendered += 1

    recently_ended = 0
    removed = 0
    retained = 0
    future_orphans = 0
    unknown_legacy = 0
    grace = timedelta(days=EVENT_DETAIL_GRACE_DAYS)
    for out in sorted(event_dir.glob("*.html")):
        if out.resolve() in expected_paths:
            continue
        text = out.read_text(encoding="utf-8", errors="ignore")
        detail_path = "/" + out.relative_to(ROOT).as_posix()
        event_id = _event_page_id(out, text)
        keep_forever = detail_path in retain_paths or event_id in retain_ids
        end_at = _event_page_lifecycle_end(text)
        if end_at is None:
            unknown_legacy += 1
            continue
        if end_at > now:
            future_orphans += 1
            continue
        if keep_forever:
            updated = _mark_event_page_ended(text, end_at, retained=True)
            if updated != text:
                out.write_text(updated, encoding="utf-8")
            retained += 1
            continue
        if now - end_at <= grace:
            updated = _mark_event_page_ended(text, end_at, retained=False)
            if updated != text:
                out.write_text(updated, encoding="utf-8")
            recently_ended += 1
            continue
        out.unlink()
        removed += 1

    payload["events"] = events
    _write_json(path, payload)
    _rewrite_event_listing_links(events)
    return {
        "rendered": rendered,
        "eligible": rendered,
        "total": len(events),
        "recently_ended": recently_ended,
        "removed": removed,
        "retained": retained,
        "future_orphans": future_orphans,
        "unknown_legacy": unknown_legacy,
        "grace_days": EVENT_DETAIL_GRACE_DAYS,
    }


def _rewrite_event_listing_links(events: list[dict]) -> None:
    page_path = ROOT / "events.html"
    if not page_path.exists():
        return
    text = page_path.read_text(encoding="utf-8", errors="ignore")
    detail_by_id = {str(e.get("id")): str(e.get("detail_url")) for e in events if e.get("detail_url")}
    # Server-rendered first page cards.
    for event_id, detail in detail_by_id.items():
        pattern = re.compile(r'(<article\s+class="event-card"[^>]*data-event-id="' + re.escape(event_id) + r'".*?</article>)', re.S)
        m = pattern.search(text)
        if not m:
            continue
        card = m.group(1)
        # Replace the title link and the Event details action, leaving source/ticket links external.
        card = re.sub(r'(<h2\s+class="event-title"><a\s+)href="[^"]+"[^>]*>', r'\1href="' + detail + r'">', card, count=1)
        card = re.sub(r'<a\s+href="[^"]+"\s+target="_blank"\s+rel="noopener noreferrer external">Event details →</a>', f'<a href="{detail}">Event details →</a>', card, count=1)
        text = text[:m.start()] + card + text[m.end():]
    # Progressive-rendering JS. Keep this exact transformation idempotent.
    text = text.replace(
        "const detailsUrl = safeUrl(event.event_url || event.source_url);",
        "const detailsUrl = event.detail_url ? String(event.detail_url) : safeUrl(event.event_url || event.source_url);\n      const detailAttrs = detailsUrl.startsWith('/') ? '' : ' target=\"_blank\" rel=\"noopener noreferrer external\"';",
    )
    text = text.replace(
        '<h2 class="event-title"><a href="${escapeHtml(detailsUrl)}" target="_blank" rel="noopener noreferrer external">${escapeHtml(event.title)}</a></h2>',
        '<h2 class="event-title"><a href="${escapeHtml(detailsUrl)}"${detailAttrs}>${escapeHtml(event.title)}</a></h2>',
    )
    text = text.replace(
        '<div class="event-card-footer"><span>Source: <a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer external">${escapeHtml(event.source_name)}</a></span><div class="event-actions"><a href="${escapeHtml(detailsUrl)}" target="_blank" rel="noopener noreferrer external">Event details →</a>${tickets}</div></div>',
        '<div class="event-card-footer"><span>Source: <a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer external">${escapeHtml(event.source_name)}</a></span><div class="event-actions"><a href="${escapeHtml(detailsUrl)}"${detailAttrs}>Event details →</a>${tickets}</div></div>',
    )
    # Point the listing ItemList at TCT's unique event leaf URLs where available.
    items = []
    for event in events[:10]:
        item = {
            "@type":"Event", "name":event.get("title", ""),
            "startDate":event.get("starts_at", ""),
            "url":f"{SITE_URL}{event.get('detail_url')}" if event.get("detail_url") else event.get("event_url") or event.get("source_url"),
            "eventStatus":"https://schema.org/EventScheduled",
            "eventAttendanceMode":"https://schema.org/OfflineEventAttendanceMode",
        }
        if event.get("ends_at"): item["endDate"] = event.get("ends_at")
        if event.get("description"): item["description"] = _clean_text(event.get("description"))
        if event.get("venue") or event.get("city"):
            item["location"] = {"@type":"Place","name":event.get("venue") or event.get("city"),"address":{"@type":"PostalAddress","streetAddress":event.get("address", ""),"addressLocality":event.get("city", ""),"addressRegion":"FL","addressCountry":"US"}}
        items.append({"@type":"ListItem","position":len(items)+1,"item":item})
    listing_schema = {"@context":"https://schema.org","@type":"ItemList","name":"Treasure Coast Events","itemListElement":items}
    marker_pattern = re.compile(r'<!-- TCT_EVENTS_JSONLD_START -->.*?<!-- TCT_EVENTS_JSONLD_END -->', re.I | re.S)
    listing_json = '<!-- TCT_EVENTS_JSONLD_START -->\n<script type="application/ld+json" data-tct-events-jsonld>' + json.dumps(listing_schema, ensure_ascii=False, separators=(",", ":")) + '</script>\n<!-- TCT_EVENTS_JSONLD_END -->'
    text = marker_pattern.sub(listing_json, text, count=1)
    page_path.write_text(text, encoding="utf-8")


def _site_search_button(placement: str = "universal") -> str:
    placement = placement if placement in {"desktop", "mobile", "universal"} else "universal"
    return f'''<button type="button" class="tct-search-toggle tct-search-toggle--{placement}" data-tct-search-toggle aria-label="Search Treasure Coast Today" aria-controls="tct-site-search" aria-expanded="false">
  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="11" cy="11" r="6.5"></circle><path d="m16 16 5 5"></path></svg>
</button>'''


def _site_search_overlay() -> str:
    return '''<div id="tct-site-search" class="tct-search-overlay" data-tct-search-overlay hidden>
  <button type="button" class="tct-search-backdrop" data-tct-search-close aria-label="Close search"></button>
  <section class="tct-search-dialog" role="dialog" aria-modal="true" aria-labelledby="tct-search-title">
    <div class="tct-search-dialog-head">
      <div><span class="tct-search-kicker">Treasure Coast Today</span><h2 id="tct-search-title">Search TCT News</h2></div>
      <button type="button" class="tct-search-close" data-tct-search-close aria-label="Close search">&times;</button>
    </div>
    <form class="tct-search-form" data-tct-search-form action="/search.html" method="get" role="search">
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="11" cy="11" r="6.5"></circle><path d="m16 16 5 5"></path></svg>
      <input type="search" name="q" data-tct-search-input placeholder="Search local news, cities, people and topics" autocomplete="off" spellcheck="false" aria-label="Search Treasure Coast Today articles">
      <button type="submit">Search</button>
    </form>
    <div class="tct-search-status" data-tct-search-status>Start typing to search TCT articles.</div>
    <div class="tct-search-results" data-tct-search-results></div>
    <div class="tct-search-dialog-foot"><a href="/archive.html">Browse the full archive</a></div>
  </section>
</div>'''


def render_article_search_page() -> None:
    head = _page_head(
        "Search TCT News | Treasure Coast Today",
        "Search Treasure Coast Today articles covering Martin, St. Lucie and Indian River counties.",
        "/search.html",
    )
    head += '\n<meta name="robots" content="noindex,follow">'
    page = f'''<!DOCTYPE html><html lang="en"><head>{head}</head><body>
{_page_header(active='')}
<main class="site-search-page"><div class="site-search-page-shell">
<nav class="tct-breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a><span aria-hidden="true">›</span><span aria-current="page">Search</span></nav>
<header class="site-search-page-hero"><span class="archive-eyebrow">Search</span><h1>Search TCT News</h1><p>Find reporting from across Martin, St. Lucie and Indian River counties.</p></header>
<form class="tct-search-page-form" data-tct-search-page-form role="search" action="/search.html" method="get">
  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="11" cy="11" r="6.5"></circle><path d="m16 16 5 5"></path></svg>
  <input type="search" name="q" data-tct-search-page-input placeholder="Search headlines, places, people or topics" autocomplete="off" spellcheck="false" aria-label="Search Treasure Coast Today articles">
  <button type="submit">Search</button>
</form>
<div class="tct-search-page-status" data-tct-search-page-status>Enter a search above, or <a href="/archive.html">browse the full archive</a>.</div>
<div class="tct-search-page-results" data-tct-search-page-results></div>
</div></main>
{_page_footer()}
</body></html>'''
    (ROOT / "search.html").write_text(page, encoding="utf-8")


def _normalize_quick_links_columns(text: str) -> str:
    """Split the modern Quick Links footer group into two real columns.

    Older retained pages may still have one flat footer-links list.  Migrate only
    the footer-v2 Quick Links group and leave unrelated legacy/simple footers alone.
    """
    if "footer-v2" not in text or "Quick Links" not in text or "footer-links-column" in text:
        return text
    pattern = re.compile(
        r'(<div\b[^>]*class=["\'][^"\']*\bfooter-column\b[^"\']*["\'][^>]*>\s*'
        r'<strong>\s*Quick Links\s*</strong>\s*'
        r'<div\b[^>]*class=["\'][^"\']*\bfooter-links\b[^"\']*["\'][^>]*>)'
        r'(.*?)'
        r'(</div>\s*</div>)',
        re.I | re.S,
    )
    match = pattern.search(text)
    if not match:
        return text
    links = re.findall(r'<a\b[^>]*>.*?</a>', match.group(2), re.I | re.S)
    if len(links) < 2:
        return text
    split = (len(links) + 1) // 2
    left = "\n".join(f"          {link.strip()}" for link in links[:split])
    right = "\n".join(f"          {link.strip()}" for link in links[split:])
    replacement = (
        match.group(1)
        + '\n        <div class="footer-links-column">\n' + left + '\n        </div>'
        + '\n        <div class="footer-links-column">\n' + right + '\n        </div>\n      '
        + match.group(3)
    )
    return text[:match.start()] + replacement + text[match.end():]


def inject_site_navigation() -> dict:
    updated = scanned = 0
    for path in ROOT.rglob("*.html"):
        # Generated event/detail/search pages are included and should receive the same chrome.
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "site-masthead" not in text and "<footer" not in text:
            continue
        scanned += 1
        original = text
        if '/news-tip.html' not in text:
            # Mobile More menu: place before Contact.
            text = text.replace('<a href="/contact.html" class="mobile-nav-link">Contact</a>', '<a href="/news-tip.html" class="mobile-nav-link">News Tip</a>\n          <a href="/contact.html" class="mobile-nav-link">Contact</a>')
            # Desktop More menu: place after Archive.
            text = text.replace('<a href="/archive.html" class="nav-section-link">Archive</a>', '<a href="/archive.html" class="nav-section-link">Archive</a>\n              <a href="/news-tip.html" class="nav-section-link">News Tip</a>')
            # Common footer variants.
            text = text.replace('<a href="/contact.html">Contact</a>', '<a href="/news-tip.html">News Tip</a>\n        <a href="/contact.html">Contact</a>')
            text = text.replace('<a href="contact.html">Contact</a>', '<a href="/news-tip.html">News Tip</a>\n        <a href="contact.html">Contact</a>')
        if '/news-tip.html' not in text:
            footer_links = re.search(r'(<div\b[^>]*class=["\'][^"\']*footer-links[^"\']*["\'][^>]*>)(.*?)(</div>)', text, re.I | re.S)
            if footer_links:
                inner = footer_links.group(2) + '\n        <a href="/news-tip.html">News Tip</a>'
                text = text[:footer_links.start()] + footer_links.group(1) + inner + footer_links.group(3) + text[footer_links.end():]

        text = _normalize_quick_links_columns(text)

        # Sitewide article search: keep a desktop trigger with account controls
        # and a separate mobile trigger beside the hamburger. Both target the
        # same accessible overlay. Rebuild the trigger pair every run so pages
        # from the previous one-button rollout migrate cleanly and idempotently.
        if 'site-masthead' in text:
            text = re.sub(
                r'\s*<button\b(?=[^>]*\bclass=["\'][^"\']*\btct-search-toggle\b[^"\']*["\'])[^>]*>.*?</button>',
                '', text, flags=re.I | re.S,
            )
            # Previous fallback markup wraps its trigger; removing the button
            # can leave an empty wrapper, so normalize that before reinserting.
            text = re.sub(
                r'\s*<div\b[^>]*class=["\'][^"\']*\btct-search-legacy-slot\b[^"\']*["\'][^>]*>\s*</div>',
                '', text, flags=re.I | re.S,
            )
            actions = re.search(r'(<div\b[^>]*class=["\'][^"\']*header-actions[^"\']*["\'][^>]*>)', text, re.I)
            hamburger = re.search(
                r'(<button\b(?=[^>]*\bclass=["\'][^"\']*\bmobile-nav-toggle-button\b[^"\']*["\'])[^>]*>.*?</button>)',
                text, re.I | re.S,
            )
            if actions:
                desktop_button = _site_search_button("desktop" if hamburger else "universal")
                text = text[:actions.end()] + '\n          ' + desktop_button + text[actions.end():]
            else:
                weather = re.search(r'<a\b[^>]*class=["\'][^"\']*masthead-live-weather[^"\']*["\']', text, re.I)
                if weather:
                    text = text[:weather.start()] + _site_search_button("universal") + '\n        ' + text[weather.start():]
                else:
                    masthead_open = re.search(r'<header\b[^>]*class=["\'][^"\']*site-masthead[^"\']*["\'][^>]*>', text, re.I)
                    if masthead_open:
                        text = text[:masthead_open.end()] + '\n    <div class="tct-search-legacy-slot">' + _site_search_button("universal") + '</div>' + text[masthead_open.end():]
            if hamburger:
                # Re-find after the desktop insertion because string offsets changed.
                hamburger = re.search(
                    r'(<button\b(?=[^>]*\bclass=["\'][^"\']*\bmobile-nav-toggle-button\b[^"\']*["\'])[^>]*>.*?</button>)',
                    text, re.I | re.S,
                )
                if hamburger:
                    text = text[:hamburger.end()] + '\n          ' + _site_search_button("mobile") + text[hamburger.end():]
        if 'data-tct-search-overlay' not in text and 'site-masthead' in text:
            masthead = re.search(r'<header\b[^>]*class=["\'][^"\']*site-masthead[^"\']*["\'][^>]*>.*?</header>', text, re.I | re.S)
            if masthead:
                text = text[:masthead.end()] + '\n  ' + _site_search_overlay() + text[masthead.end():]

        if text != original:
            path.write_text(text, encoding="utf-8"); updated += 1
    return {"scanned": scanned, "updated": updated}


def enhance_homepage() -> dict:
    path = ROOT / "index.html"
    if not path.exists(): return {"updated":False}
    original = path.read_text(encoding="utf-8")
    text = original
    replacements = {
        "Stuart · Jensen Beach · Palm City · Hobe Sound": '<a href="/stuart/">Stuart</a> · <a href="/jensen-beach/">Jensen Beach</a> · <a href="/palm-city/">Palm City</a> · <a href="/hobe-sound/">Hobe Sound</a>',
        "Port St. Lucie · Fort Pierce": '<a href="/port-st-lucie/">Port St. Lucie</a> · <a href="/fort-pierce/">Fort Pierce</a>',
        "Vero Beach · Sebastian · Fellsmere": '<a href="/vero-beach/">Vero Beach</a> · <a href="/sebastian/">Sebastian</a> · <a href="/fellsmere/">Fellsmere</a>',
    }
    for old,new in replacements.items(): text = text.replace(old,new)
    module = MOST_READ_HOME_START + _most_read_module(False) + MOST_READ_HOME_END
    text = _replace_marker(text, MOST_READ_HOME_START, MOST_READ_HOME_END, module)
    if MOST_READ_HOME_START not in text:
        county = re.search(r'<div\s+class="county-panels-grid">', text, re.I)
        if county:
            text = text[:county.start()] + module + "\n    " + text[county.start():]
    if text != original:
        path.write_text(text, encoding="utf-8")
    return {"updated": text != original}


def inject_preferred_source_static_pages() -> dict:
    updated = 0
    for name in ("about.html", "newsroom.html"):
        path = ROOT / name
        if not path.exists(): continue
        original = path.read_text(encoding="utf-8")
        text = _replace_marker(original, PREFERRED_MARKER_START, PREFERRED_MARKER_END, _preferred_source_module(False))
        if PREFERRED_MARKER_START not in text:
            close = re.search(r"</main\s*>", text, re.I)
            if close: text = text[:close.start()] + _preferred_source_module(False) + "\n" + text[close.start():]
        text = _ensure_preferred_script(text)
        if text != original:
            path.write_text(text, encoding="utf-8"); updated += 1
    return {"updated":updated}


def _upsert_meta(text: str, name: str, content: str) -> str:
    tag = f'<meta name="{name}" content="{html_lib.escape(content, quote=True)}">'
    pattern = re.compile(r'<meta\s+name=["\']' + re.escape(name) + r'["\'][^>]*>', re.I)
    if pattern.search(text): return pattern.sub(tag, text, count=1)
    close = re.search(r"</head\s*>", text, re.I)
    return text[:close.start()] + tag + "\n" + text[close.start():] if close else text


def normalize_assets_and_analytics() -> dict:
    supabase_url = os.getenv("TCT_SUPABASE_URL", "").strip().rstrip("/")
    endpoint = f"{supabase_url}/functions/v1/story-analytics" if supabase_url else ""
    updated = scanned = 0
    for path in ROOT.rglob("*.html"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "</head" not in text.lower(): continue
        scanned += 1; original = text
        text = re.sub(r'/style\.css\?v=[^"\']+', f'/style.css?v={ASSET_VERSION}', text)
        text = re.sub(r'/main\.js\?v=[^"\']+', f'/main.js?v={ASSET_VERSION}', text)
        # Migrate retained/static pages from the old SVG favicon to the current PNG.
        text = re.sub(
            r'<link\b(?=[^>]*\brel=["\'][^"\']*\bicon\b[^"\']*["\'])'
            r'(?=[^>]*\bhref=["\'](?:https://treasurecoast\.today)?/favicon\.svg(?:\?[^"\']*)?["\'])[^>]*>',
            '<link rel="icon" href="/favicon.png" type="image/png">',
            text,
            flags=re.I,
        )
        if endpoint:
            text = _upsert_meta(text, "tct-story-analytics-endpoint", endpoint)
        if text != original:
            path.write_text(text, encoding="utf-8"); updated += 1
    # New pages and postprocessed pages must keep the Mediavine loader contract.
    mv = _apply_mediavine_sitewide(ROOT)
    return {"scanned": scanned, "updated": updated, "mediavine": mv}


def update_sitemap() -> dict:
    path = ROOT / "sitemap.xml"
    if not path.exists(): return {"added":0,"removed_event_urls":0}
    ET.register_namespace("", "http://www.sitemaps.org/schemas/sitemap/0.9")
    tree = ET.parse(path); root = tree.getroot(); ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"

    # Event leaf URLs are workflow-owned and temporary. Reconcile them instead of
    # append-only growth so ended events leave the sitemap immediately and a page
    # deleted after the grace period cannot remain advertised to crawlers.
    removed_event_urls = 0
    event_prefix = f"{SITE_URL}/events/"
    for node in list(root.findall(f"{ns}url")):
        loc = node.find(f"{ns}loc")
        value = loc.text if loc is not None else ""
        if value and value.startswith(event_prefix) and value.endswith(".html"):
            root.remove(node); removed_event_urls += 1

    existing = {node.text for node in root.findall(f"{ns}url/{ns}loc") if node.text}
    additions = []
    for static, priority, change in [("/events.html","0.8","daily"),("/news-tip.html","0.6","monthly")]:
        additions.append((f"{SITE_URL}{static}", priority, change, ""))
    for city in CITY_CONFIG:
        if (ROOT / city["slug"] / "index.html").exists(): additions.append((f"{SITE_URL}/{city['slug']}/","0.8","daily",""))
    events = _read_json(ROOT / "data" / "events.json", {}).get("events", [])
    for e in events if isinstance(events,list) else []:
        detail = e.get("detail_url") if isinstance(e,dict) else None
        if detail: additions.append((f"{SITE_URL}{detail}","0.5","weekly",str(e.get("starts_at") or "")[:10]))
    for retained in sorted(_retained_event_paths()):
        if (ROOT / retained.lstrip("/")).exists():
            additions.append((f"{SITE_URL}{retained}","0.3","monthly",""))

    added = 0
    for loc, priority, change, lastmod in additions:
        if loc in existing: continue
        u=ET.SubElement(root,f"{ns}url"); ET.SubElement(u,f"{ns}loc").text=loc
        ET.SubElement(u,f"{ns}changefreq").text=change; ET.SubElement(u,f"{ns}priority").text=priority
        if lastmod: ET.SubElement(u,f"{ns}lastmod").text=lastmod
        existing.add(loc); added += 1
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return {"added":added,"removed_event_urls":removed_event_urls,"total":len(existing)}


def validate_event_detail_lifecycle() -> dict:
    failures: list[str] = []
    now = _event_now()
    grace = timedelta(days=EVENT_DETAIL_GRACE_DAYS)
    events_payload = _read_json(ROOT / "data" / "events.json", {})
    events = events_payload.get("events", []) if isinstance(events_payload, dict) else []
    active_paths = {
        str(event.get("detail_url"))
        for event in events if isinstance(event, dict) and event.get("detail_url")
    }
    retained_paths = _retained_event_paths()

    sitemap_path = ROOT / "sitemap.xml"
    sitemap_locs: set[str] = set()
    if sitemap_path.exists():
        try:
            tree = ET.parse(sitemap_path); root = tree.getroot(); ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
            sitemap_locs = {node.text for node in root.findall(f"{ns}url/{ns}loc") if node.text}
        except Exception as exc:
            failures.append(f"sitemap parse: {exc}")

    for detail in sorted(active_paths):
        path = ROOT / detail.lstrip("/")
        if not path.exists():
            failures.append(f"active event page missing {detail}")
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if '"@type":"Event"' not in text:
            failures.append(f"active event schema missing {detail}")
        if "data-tct-event-ended" in text:
            failures.append(f"active event marked ended {detail}")
        if f"{SITE_URL}{detail}" not in sitemap_locs:
            failures.append(f"active event missing sitemap {detail}")

    checked = 0
    event_dir = ROOT / "events"
    if event_dir.exists():
        for path in sorted(event_dir.glob("*.html")):
            detail = "/" + path.relative_to(ROOT).as_posix()
            if detail in active_paths:
                continue
            checked += 1
            text = path.read_text(encoding="utf-8", errors="ignore")
            end_at = _event_page_lifecycle_end(text)
            retained = detail in retained_paths
            if end_at is None:
                # Legacy pages without machine-readable lifecycle data are preserved
                # fail-closed rather than guessed/deleted.
                continue
            if end_at > now:
                if f"{SITE_URL}{detail}" in sitemap_locs and not retained:
                    failures.append(f"orphan future event remains in sitemap {detail}")
                continue
            if retained:
                if '"@type":"Event"' in text:
                    failures.append(f"retained ended event still exposes Event schema {detail}")
                if "data-tct-event-ended" not in text:
                    failures.append(f"retained ended event missing ended notice {detail}")
                if f"{SITE_URL}{detail}" not in sitemap_locs:
                    failures.append(f"retained event missing sitemap {detail}")
                continue
            age = now - end_at
            if age <= grace:
                if "data-tct-event-ended" not in text:
                    failures.append(f"recently ended event missing ended notice {detail}")
                if '"@type":"Event"' in text:
                    failures.append(f"recently ended event still exposes Event schema {detail}")
                if '<meta name="robots" content="noindex,follow">' not in text:
                    failures.append(f"recently ended event missing noindex {detail}")
                if f"{SITE_URL}{detail}" in sitemap_locs:
                    failures.append(f"recently ended event remains in sitemap {detail}")
            else:
                failures.append(f"expired event page still exists after grace period {detail}")

    allowed_sitemap = active_paths | retained_paths
    for loc in sitemap_locs:
        if loc.startswith(f"{SITE_URL}/events/") and loc.endswith(".html"):
            detail = loc[len(SITE_URL):]
            if detail not in allowed_sitemap:
                failures.append(f"unmanaged event sitemap URL {detail}")

    if failures:
        raise RuntimeError("Event detail lifecycle contract FAILED: " + "; ".join(failures[:20]))
    return {"active":len(active_paths),"checked_inactive":checked,"retained":len(retained_paths),"failures":0,"grace_days":EVENT_DETAIL_GRACE_DAYS}


def validate_features(archive: list[dict]) -> dict:
    failures=[]
    # City hubs must be substantive and crawlable.
    for city in CITY_CONFIG:
        p=ROOT/city["slug"]/"index.html"
        count=sum(1 for e in archive if city["slug"] in {c["slug"] for c in _entry_cities(e)})
        if count >= 3:
            if not p.exists(): failures.append(f"missing city page {city['slug']}")
            else:
                text=p.read_text(encoding="utf-8")
                if f'<link rel="canonical" href="{SITE_URL}/{city["slug"]}/">' not in text: failures.append(f"city canonical {city['slug']}")
                if text.count('class="city-story-card') < min(3,count): failures.append(f"thin city page {city['slug']}")
    archive_text=(ROOT/"archive.html").read_text(encoding="utf-8")
    for token in ("data-archive-query","data-archive-county","data-archive-city","data-archive-category","data-archive-from","data-archive-to"):
        if token not in archive_text: failures.append(f"archive missing {token}")
    tip=(ROOT/"news-tip.html").read_text(encoding="utf-8")
    if 'mailto:hello@treasurecoast.today' not in tip:
        failures.append("news tip missing newsroom email link")
    for forbidden in ('news-tip-form', 'formspree.io', 'multipart/form-data', 'name="attachment"', 'name="form_type"'):
        if forbidden.lower() in tip.lower(): failures.append(f"news tip contains forbidden form token {forbidden}")
    story_index=_read_json(ROOT/"data"/"story-index.json",{})
    stories = story_index.get("stories",{}) if isinstance(story_index,dict) else {}
    if len(stories) < 10: failures.append("story-index too small")
    elif not all(key in next(iter(stories.values())) for key in ("headline","teaser","category","date","cities","counties")): failures.append("story-index missing search fields")
    search_path=ROOT/"search.html"
    if not search_path.exists(): failures.append("missing search page")
    else:
        search_text=search_path.read_text(encoding="utf-8",errors="ignore")
        for token in ('data-tct-search-page-input','data-tct-search-page-results','name="robots" content="noindex,follow"'):
            if token not in search_text: failures.append(f"search page missing {token}")
    chrome_text=(ROOT/"about.html").read_text(encoding="utf-8",errors="ignore") if (ROOT/"about.html").exists() else ""
    if 'data-tct-search-toggle' not in chrome_text or 'data-tct-search-overlay' not in chrome_text: failures.append("sitewide search chrome missing")
    # Check a representative sample plus every current-month article.
    current_articles=[]
    for row in archive:
        p=ROOT/_entry_url(row).lstrip("/")
        if p.exists() and (_entry_date(row).startswith("2026-09") or len(current_articles)<20): current_articles.append((row,p))
    for row,p in current_articles[:160]:
        text=p.read_text(encoding="utf-8",errors="ignore")
        if "article-headline" not in text: continue
        if BREADCRUMB_MARKER_START not in text or "data-tct-breadcrumb-jsonld" not in text: failures.append(f"breadcrumb {p.name}")
        if PREFERRED_SOURCE_SCRIPT not in text or "google-add-preferred-source-btn" not in text: failures.append(f"preferred source {p.name}")
        if "data-tct-most-read" not in text: failures.append(f"most read slot {p.name}")
    if failures:
        raise RuntimeError("Audience/SEO feature contract FAILED: " + "; ".join(failures[:20]))
    return {"checked_articles":min(160,len(current_articles)),"failures":0}


def build() -> dict:
    archive = _read_json(ROOT / "archive.json", [])
    if not isinstance(archive, list):
        raise RuntimeError("archive.json must be a top-level array")
    report = {}
    report["city_pages"] = render_city_pages(archive)
    report["archive"] = render_searchable_archive(archive)
    render_article_search_page(); report["article_search"] = True
    render_news_tip_page(); report["news_tip"] = True
    report["events"] = render_event_detail_pages()
    report["story_index"] = write_story_index(archive)
    report["articles"] = enhance_articles(archive)
    report["preferred_static"] = inject_preferred_source_static_pages()
    report["homepage"] = enhance_homepage()
    report["navigation"] = inject_site_navigation()
    report["sitemap"] = update_sitemap()
    report["event_lifecycle"] = validate_event_detail_lifecycle()
    report["assets"] = normalize_assets_and_analytics()
    report["validation"] = validate_features(archive)
    _write_json(ROOT / "data" / "audience-features-report.json", report)
    print("Audience/SEO features built:", json.dumps(report, ensure_ascii=False))
    return report


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--events-only", action="store_true", help="Render and retire event detail pages, reconcile event sitemap URLs, and validate the event lifecycle.")
    parser.add_argument("--validate-events-only", action="store_true", help="Validate only the event-detail lifecycle contract.")
    args=parser.parse_args(argv)
    archive=_read_json(ROOT/"archive.json",[])
    if args.validate_events_only:
        report = validate_event_detail_lifecycle()
        print("Event detail lifecycle validation PASSED:", json.dumps(report, ensure_ascii=False)); return 0
    if args.events_only:
        report = {"events": render_event_detail_pages(), "sitemap": update_sitemap()}
        report["validation"] = validate_event_detail_lifecycle()
        print("Event detail pages built:", json.dumps(report, ensure_ascii=False)); return 0
    if args.validate_only:
        validate_features(archive); validate_event_detail_lifecycle(); print("Audience/SEO feature validation PASSED"); return 0
    build(); return 0


if __name__ == "__main__":
    raise SystemExit(main())
