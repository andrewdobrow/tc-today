from __future__ import annotations

import importlib
import os
import sys
import types


def _load_generate_module():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


class _HttpResponse:
    def __init__(self, *, text="", url="", status_code=200):
        self.text = text
        self.url = url
        self.status_code = status_code


def test_modern_google_news_wrapper_resolves_to_trusted_wptv(monkeypatch):
    generate = _load_generate_module()
    token = "CBMi-test-token"
    google_url = f"https://news.google.com/rss/articles/{token}?oc=5"
    landing = _HttpResponse(
        text='<c-wiz data-n-a-sg="signature123" data-n-a-ts="1720000000"></c-wiz>',
        url=google_url,
    )
    rpc = _HttpResponse(
        text='123\n[["wrb.fr","Fbv4je","[\\"garturlres\\",\\"https://www.wptv.com/news/region-martin-county/indiantown/indian-river-county-firefighter-paramedic-dies-following-off-duty-personal-tragedy\\"]",null,null,null,"generic"]]'
    )
    monkeypatch.setattr(generate.requests, "get", lambda *args, **kwargs: landing)
    monkeypatch.setattr(generate.requests, "post", lambda *args, **kwargs: rpc)
    monkeypatch.setattr(generate.GENERATION_CACHE, "get", lambda *args, **kwargs: generate._CACHE_MISS)
    monkeypatch.setattr(generate.GENERATION_CACHE, "put", lambda *args, **kwargs: None)

    resolved = generate.resolve_google_news_url(google_url, ("wptv.com",))

    assert resolved.startswith("https://www.wptv.com/news/")
    assert "indian-river-county-firefighter-paramedic" in resolved


def test_trusted_local_google_item_is_recovered_before_source_depth_gate(monkeypatch):
    generate = _load_generate_module()
    google_url = "https://news.google.com/rss/articles/CBMi-firefighter?oc=5"
    direct_url = (
        "https://www.wptv.com/news/region-martin-county/indiantown/"
        "indian-river-county-firefighter-paramedic-dies-following-off-duty-personal-tragedy"
    )
    entry = {
        "title": "Indian River County firefighter/paramedic dies following off-duty personal tragedy - WPTV",
        "summary": "Indian River County Fire Rescue says Geoffrey Lang died at his Sebastian home following an off-duty personal tragedy.",
        "link": google_url,
        "published": "Sun, 26 Jul 2026 18:00:00 GMT",
        "source": {"title": "WPTV", "href": "https://www.wptv.com"},
    }
    monkeypatch.setattr(generate.feedparser, "parse", lambda *args, **kwargs: types.SimpleNamespace(entries=[entry]))
    monkeypatch.setattr(generate, "resolve_google_news_url", lambda *args, **kwargs: direct_url)
    monkeypatch.setattr(
        generate,
        "fetch_article_text",
        lambda *args, **kwargs: " ".join(["verified"] * 120),
    )
    with generate.TRUSTED_SOURCE_RECOVERY_LOCK:
        generate.TRUSTED_SOURCE_RECOVERY_ROWS.clear()

    rows = generate.fetch_headlines(["https://news.google.com/rss/search?q=indian+river"], limit=10)

    assert len(rows) == 1
    recovered = rows[0]
    assert recovered["link"] == direct_url
    assert recovered["source_quality"] == "summary"
    assert recovered["source_recovery_status"] == "recovered"
    assert generate._source_candidate_publishable(recovered) is True
    assert generate._looks_like_obituary_listing(
        recovered["title"],
        recovered["article_text"] + " He is survived by his wife and children.",
    ) is False
    assert generate._hero_eligible("indian_river", recovered) is True
    assert generate.TRUSTED_SOURCE_RECOVERY_ROWS[-1]["result"] == "recovered"


def test_trusted_local_discovery_just_below_normal_cap_still_gets_recovery(monkeypatch):
    generate = _load_generate_module()
    ordinary = []
    for index in range(12):
        ordinary.append({
            "title": f"Ordinary statewide item {index}",
            "summary": "A short statewide brief.",
            "link": f"https://example.com/{index}",
            "published": f"Mon, 27 Jul 2026 {23-index:02d}:00:00 GMT",
        })
    firefighter = {
        "title": "Indian River County firefighter/paramedic dies following off-duty personal tragedy - WPTV",
        "summary": "Indian River County Fire Rescue says Geoffrey Lang died at his Sebastian home.",
        "link": "https://news.google.com/rss/articles/CBMi-firefighter?oc=5",
        "published": "Mon, 27 Jul 2026 05:00:00 GMT",
        "source": {"title": "WPTV", "href": "https://www.wptv.com"},
    }
    monkeypatch.setattr(
        generate.feedparser,
        "parse",
        lambda *args, **kwargs: types.SimpleNamespace(entries=ordinary + [firefighter]),
    )
    monkeypatch.setattr(
        generate,
        "resolve_google_news_url",
        lambda *args, **kwargs: "https://www.wptv.com/news/indian-river-firefighter",
    )
    monkeypatch.setattr(
        generate,
        "fetch_article_text",
        lambda url, **kwargs: " ".join(["verified"] * 100) if "wptv.com" in url else "",
    )

    rows = generate.fetch_headlines(["https://news.google.com/rss/search?q=local"], limit=12)

    recovered = [row for row in rows if "firefighter/paramedic" in row["title"]]
    assert len(recovered) == 1
    assert recovered[0]["source_quality"] == "summary"
