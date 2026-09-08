#!/usr/bin/env python3
"""Validate final rendered TCT Article/Paywall/Breadcrumb/Event SEO contracts."""
from __future__ import annotations
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://treasurecoast.today"
CITY_SLUGS = ["stuart","jensen-beach","palm-city","hobe-sound","port-st-lucie","fort-pierce","vero-beach","sebastian","fellsmere"]


def _jsonld(soup: BeautifulSoup):
    for node in soup.find_all("script", attrs={"type":"application/ld+json"}):
        try:
            data=json.loads(node.string or node.get_text() or "")
        except Exception:
            continue
        if isinstance(data,list):
            yield from [x for x in data if isinstance(x,dict)]
        elif isinstance(data,dict):
            yield data


def validate() -> dict:
    failures=[]; articles=0; paywalled=0; events=0; cities=0
    archive=json.loads((ROOT/"archive.json").read_text(encoding="utf-8"))
    slugs={str(r.get("canonical_slug") or r.get("slug") or "") for r in archive if isinstance(r,dict)}
    for slug in sorted(slugs):
        if not slug: continue
        path=ROOT/"articles"/f"{slug}.html"
        if not path.exists(): continue
        text=path.read_text(encoding="utf-8",errors="ignore")
        if "article-headline" not in text: continue
        articles += 1
        soup=BeautifulSoup(text,"html.parser")
        canonical=soup.find("link",rel="canonical")
        expected=f"{SITE}/articles/{slug}.html"
        if canonical is None or canonical.get("href") != expected:
            failures.append(f"article canonical:{slug}")
        objs=list(_jsonld(soup))
        article=next((o for o in objs if o.get("@type") in {"NewsArticle","Article"}),None)
        if not article:
            failures.append(f"NewsArticle missing:{slug}")
        else:
            author=article.get("author")
            if not isinstance(author,dict) or author.get("@type")!="Person" or author.get("url")!=f"{SITE}/author/andrew-dobrow.html":
                failures.append(f"article author:{slug}")
            if not article.get("datePublished"):
                failures.append(f"datePublished:{slug}")
            if not article.get("dateModified"):
                failures.append(f"dateModified:{slug}")
        breadcrumb=next((o for o in objs if o.get("@type")=="BreadcrumbList"),None)
        if breadcrumb is None or len(breadcrumb.get("itemListElement") or []) < 2 or soup.select_one(".tct-breadcrumb--article") is None:
            failures.append(f"breadcrumb:{slug}")
        is_paywalled=soup.select_one(".tct-paywall") is not None or soup.select_one(".tct-paywalled-content") is not None
        if is_paywalled:
            paywalled += 1
            if not article or article.get("isAccessibleForFree") is not False:
                failures.append(f"paywall accessible flag:{slug}")
            haspart=(article or {}).get("hasPart") if article else None
            if not isinstance(haspart,dict) or haspart.get("cssSelector")!=".tct-paywalled-content" or haspart.get("isAccessibleForFree") is not False:
                failures.append(f"paywall hasPart:{slug}")
        if text.count("https://news.google.com/swg/js/v1/publisher.js") != 1 or soup.select_one("[google-add-preferred-source-btn]") is None:
            failures.append(f"preferred source:{slug}")
    for slug in CITY_SLUGS:
        path=ROOT/slug/"index.html"
        if not path.exists(): continue
        cities += 1
        soup=BeautifulSoup(path.read_text(encoding="utf-8",errors="ignore"),"html.parser")
        objs=list(_jsonld(soup))
        if not any(o.get("@type")=="CollectionPage" for o in objs): failures.append(f"city schema:{slug}")
        canonical=soup.find("link",rel="canonical")
        if canonical is None or canonical.get("href")!=f"{SITE}/{slug}/": failures.append(f"city canonical:{slug}")
        if len(soup.select(".city-story-card")) < 3: failures.append(f"city stories:{slug}")
    for path in sorted((ROOT/"events").glob("*.html")):
        if not re.match(r"^[0-9a-f]{18}-",path.name): continue
        events += 1
        soup=BeautifulSoup(path.read_text(encoding="utf-8",errors="ignore"),"html.parser")
        objs=list(_jsonld(soup))
        if not any(o.get("@type")=="Event" for o in objs): failures.append(f"event schema:{path.name}")
        if soup.select_one(".event-detail-primary") is None and soup.select_one(".event-detail-secondary") is None: failures.append(f"event source link:{path.name}")
    if failures:
        raise RuntimeError("Final SEO contract FAILED: " + "; ".join(failures[:30]))
    print(f"Final SEO contract PASSED: {articles} articles ({paywalled} paywalled), {cities} city hubs, {events} event detail pages")
    return {"articles":articles,"paywalled":paywalled,"cities":cities,"events":events}

if __name__ == "__main__":
    validate()
