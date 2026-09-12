import json
from pathlib import Path

from scripts import build_audience_features as features
from scripts import validate_seo_contracts as seo_contracts
from tct_engine.membership_paywall import paywall_section_html


def _chrome():
    return '''<!doctype html><html><head><title>Chrome</title></head><body>
<header class="site-masthead"><nav><a href="/?cat=martin" class="cat-btn">Martin County</a><a href="/?cat=st_lucie" class="cat-btn">St. Lucie County</a><a href="/?cat=indian_river" class="cat-btn">Indian River County</a><div class="nav-sections-links"><a href="/archive.html" class="nav-section-link">Archive</a><a href="/contact.html" class="nav-section-link">Contact</a></div><div class="mobile-nav-links"><a href="/contact.html" class="mobile-nav-link">Contact</a></div></nav></header>
<main></main><footer><div class="footer-links"><a href="/about.html">About</a><a href="/archive.html">Archive</a><a href="/contact.html">Contact</a></div></footer><script src="/main.js?v=old"></script></body></html>'''


def _archive_rows():
    base = [
        ("stuart-one", "Stuart approves waterfront plan", "martin", "Martin County", "2026-09-08"),
        ("stuart-two", "New restaurant opens in Stuart", "business", "Business & Development", "2026-09-07"),
        ("stuart-three", "Stuart police announce road closure", "crime", "Crime & Safety", "2026-09-06"),
        ("psl-one", "Port St. Lucie council approves project", "st_lucie", "St. Lucie County", "2026-09-08"),
        ("psl-two", "Port St. Lucie police investigate crash", "crime", "Crime & Safety", "2026-09-07"),
        ("psl-three", "Business opens in Port St. Lucie", "business", "Business & Development", "2026-09-06"),
    ]
    rows=[]
    for slug,headline,key,label,date in base:
        county_keys=["martin"] if "stuart" in slug else ["st_lucie"]
        rows.append({"slug":slug,"headline":headline,"teaser":headline+" details.","category_key":key,"category_label":label,"county_keys":county_keys,"date":date,"lastmod":date,"first_published":date,"image_url":"https://example.com/image.jpg"})
    return rows


def _setup_root(tmp_path, monkeypatch):
    (tmp_path / "about.html").write_text(_chrome(), encoding="utf-8")
    (tmp_path / "articles").mkdir(exist_ok=True)
    (tmp_path / "data").mkdir(exist_ok=True)
    monkeypatch.setattr(features, "ROOT", tmp_path)


def test_city_matching_respects_county_metadata():
    row={"headline":"Stuart officials act", "teaser":"", "county_keys":["martin"]}
    assert [c["slug"] for c in features._entry_cities(row)] == ["stuart"]
    wrong={"headline":"Stuart officials act", "teaser":"", "county_keys":["st_lucie"]}
    assert features._entry_cities(wrong) == []


def test_city_pages_are_real_story_hubs(tmp_path, monkeypatch):
    _setup_root(tmp_path, monkeypatch)
    rows=_archive_rows()
    report=features.render_city_pages(rows)
    assert report["counts"]["stuart"] == 3
    page=(tmp_path/"stuart"/"index.html").read_text(encoding="utf-8")
    assert '<link rel="canonical" href="https://treasurecoast.today/stuart/">' in page
    assert page.count('class="city-story-card') == 3
    assert "CollectionPage" in page


def test_searchable_archive_keeps_crawlable_article_links(tmp_path, monkeypatch):
    _setup_root(tmp_path, monkeypatch)
    rows=_archive_rows()
    features.render_searchable_archive(rows)
    page=(tmp_path/"archive.html").read_text(encoding="utf-8")
    assert 'data-archive-query' in page and 'data-archive-city' in page
    assert 'href="/articles/stuart-one.html"' in page
    assert page.count('data-archive-item') >= len(rows)


def test_news_tip_page_is_email_only_and_has_no_third_party_form(tmp_path, monkeypatch):
    _setup_root(tmp_path, monkeypatch)
    features.render_news_tip_page()
    page=(tmp_path/"news-tip.html").read_text(encoding="utf-8")
    assert 'mailto:hello@treasurecoast.today' in page
    assert 'Email a news tip' in page
    assert 'news-tip-form' not in page
    assert 'formspree.io' not in page
    assert 'multipart/form-data' not in page
    assert 'name="attachment"' not in page
    assert 'name="form_type"' not in page


def test_event_detail_pages_use_internal_canonical_and_event_schema(tmp_path, monkeypatch):
    _setup_root(tmp_path, monkeypatch)
    (tmp_path/"events.html").write_text(_chrome(), encoding="utf-8")
    payload={"schema_version":1,"events":[{"id":"0123456789abcdef12","title":"Stuart Art Walk","starts_at":"2026-09-12T18:00:00-04:00","ends_at":"2026-09-12T20:00:00-04:00","venue":"Downtown Stuart","address":"1 Main St","city":"Stuart","county":"Martin","category":"Arts & Culture","price":"Free","description":"A downtown art walk.","event_url":"https://example.com/event","ticket_url":"","source_name":"Example Calendar","source_url":"https://example.com/calendar"}]}
    (tmp_path/"data"/"events.json").write_text(json.dumps(payload), encoding="utf-8")
    report=features.render_event_detail_pages()
    assert report["rendered"] == 1
    enriched=json.loads((tmp_path/"data"/"events.json").read_text())
    detail=enriched["events"][0]["detail_url"]
    page=(tmp_path/detail.lstrip('/')).read_text(encoding="utf-8")
    assert f'<link rel="canonical" href="https://treasurecoast.today{detail}">' in page
    assert '"@type":"Event"' in page
    assert 'Official event page' in page
    assert f'<link rel="stylesheet" href="/style.css?v={features.ASSET_VERSION}">' in page
    assert 'name="tct-event-lifecycle-end" content="2026-09-12T20:00:00-04:00"' in page
    assert 'name="tct-event-id" content="0123456789abcdef12"' in page
    assert 'data-tct-event-ended' not in page


def _minimal_sitemap(path):
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        '<url><loc>https://treasurecoast.today/</loc></url>'
        '</urlset>',
        encoding="utf-8",
    )


def _event_fixture():
    return {
        "id":"0123456789abcdef12",
        "title":"Stuart Art Walk",
        "starts_at":"2026-09-12T18:00:00-04:00",
        "ends_at":"2026-09-12T20:00:00-04:00",
        "venue":"Downtown Stuart",
        "address":"1 Main St",
        "city":"Stuart",
        "county":"Martin",
        "category":"Arts & Culture",
        "price":"Free",
        "description":"A downtown art walk.",
        "event_url":"https://example.com/event",
        "ticket_url":"",
        "source_name":"Example Calendar",
        "source_url":"https://example.com/calendar",
    }


def test_event_detail_lifecycle_recently_ended_then_real_404_after_30_days(tmp_path, monkeypatch):
    _setup_root(tmp_path, monkeypatch)
    (tmp_path/"events.html").write_text(_chrome(), encoding="utf-8")
    _minimal_sitemap(tmp_path/"sitemap.xml")
    monkeypatch.setenv("TCT_EVENTS_NOW", "2026-09-12T19:00:00-04:00")
    (tmp_path/"data"/"events.json").write_text(json.dumps({"schema_version":1,"events":[_event_fixture()]}), encoding="utf-8")

    features.render_event_detail_pages()
    features.update_sitemap()
    active=json.loads((tmp_path/"data"/"events.json").read_text())
    detail=active["events"][0]["detail_url"]
    event_path=tmp_path/detail.lstrip('/')
    assert event_path.exists()
    assert f"https://treasurecoast.today{detail}" in (tmp_path/"sitemap.xml").read_text()
    features.validate_event_detail_lifecycle()

    # Ten days after the event, keep the URL available but remove rich-event
    # markup and sitemap discovery. noindex prevents stale event search results.
    monkeypatch.setenv("TCT_EVENTS_NOW", "2026-09-22T20:00:00-04:00")
    (tmp_path/"data"/"events.json").write_text(json.dumps({"schema_version":1,"events":[]}), encoding="utf-8")
    ended_report=features.render_event_detail_pages()
    features.update_sitemap()
    ended=event_path.read_text(encoding="utf-8")
    assert ended_report["recently_ended"] == 1
    assert "data-tct-event-ended" in ended
    assert "This event has ended." in ended
    assert '"@type":"Event"' not in ended
    assert '<meta name="robots" content="noindex,follow">' in ended
    assert f"https://treasurecoast.today{detail}" not in (tmp_path/"sitemap.xml").read_text()
    features.validate_event_detail_lifecycle()

    # Once the 30-day grace period is over, delete the static file. On GitHub
    # Pages that makes the URL return a genuine HTTP 404; do not fake a 410 page.
    monkeypatch.setenv("TCT_EVENTS_NOW", "2026-10-14T20:00:01-04:00")
    removed_report=features.render_event_detail_pages()
    features.update_sitemap()
    assert removed_report["removed"] == 1
    assert not event_path.exists()
    assert f"https://treasurecoast.today{detail}" not in (tmp_path/"sitemap.xml").read_text()
    features.validate_event_detail_lifecycle()


def test_event_detail_retention_override_preserves_high_value_page(tmp_path, monkeypatch):
    _setup_root(tmp_path, monkeypatch)
    (tmp_path/"events.html").write_text(_chrome(), encoding="utf-8")
    _minimal_sitemap(tmp_path/"sitemap.xml")
    monkeypatch.setenv("TCT_EVENTS_NOW", "2026-09-12T19:00:00-04:00")
    (tmp_path/"data"/"events.json").write_text(json.dumps({"schema_version":1,"events":[_event_fixture()]}), encoding="utf-8")
    features.render_event_detail_pages()
    active=json.loads((tmp_path/"data"/"events.json").read_text())
    detail=active["events"][0]["detail_url"]
    (tmp_path/"data"/"events-retention.json").write_text(json.dumps({"schema_version":1,"retain_ids":[],"retain_paths":[detail]}), encoding="utf-8")

    monkeypatch.setenv("TCT_EVENTS_NOW", "2026-11-01T12:00:00-05:00")
    (tmp_path/"data"/"events.json").write_text(json.dumps({"schema_version":1,"events":[]}), encoding="utf-8")
    report=features.render_event_detail_pages()
    features.update_sitemap()
    event_path=tmp_path/detail.lstrip('/')
    page=event_path.read_text(encoding="utf-8")
    assert report["retained"] == 1
    assert event_path.exists()
    assert "data-tct-event-ended" in page
    assert '"@type":"Event"' not in page
    assert '<meta name="robots" content="noindex,follow">' not in page
    assert f"https://treasurecoast.today{detail}" in (tmp_path/"sitemap.xml").read_text()
    features.validate_event_detail_lifecycle()


def test_event_detail_title_header_is_not_sticky_over_site_masthead():
    css = (Path(__file__).resolve().parents[1] / "style.css").read_text(encoding="utf-8")
    assert ".event-detail-page > .event-detail-shell > .event-detail-hero {" in css
    assert "position: static;" in css
    assert "top: auto;" in css
    assert "z-index: auto;" in css


def test_mobile_article_breadcrumb_and_byline_are_compact():
    css = (Path(__file__).resolve().parents[1] / "style.css").read_text(encoding="utf-8")
    assert "v1.13.8.5 — mobile article breadcrumb + byline rhythm" in css
    assert ".tct-breadcrumb--article > span:nth-last-child(2)" in css
    assert ".tct-breadcrumb--article .tct-breadcrumb-current" in css
    assert "clip: rect(0, 0, 0, 0) !important;" in css
    assert ".article-byline::before" in css
    assert 'content: "·";' in css
    assert ".article-times" in css
    assert "display: grid !important;" in css
    assert ".article-updated::before" in css
    assert "content: none !important;" in css


def test_article_enhancement_handles_legacy_shell_and_adds_schema(tmp_path, monkeypatch):
    _setup_root(tmp_path, monkeypatch)
    rows=_archive_rows()
    article=tmp_path/"articles"/"stuart-one.html"
    article.write_text('''<!doctype html><html><head><link rel="canonical" href="https://treasurecoast.today/articles/stuart-one.html"></head><body data-article-slug="stuart-one"><main><div class="article-wrap"><div class="article-meta">Meta</div><h1 class="article-headline">Stuart approves waterfront plan</h1><div class="article-body">Body copy</div><a class="article-more-link" href="/?cat=martin">More</a></div></main></body></html>''', encoding="utf-8")
    report=features.enhance_articles(rows)
    assert report["scanned"] == 1
    page=article.read_text(encoding="utf-8")
    assert 'TCT_BREADCRUMB_START' in page
    assert '<main class="article-page-main">' in page
    assert 'data-tct-most-read' in page
    assert 'google-add-preferred-source-btn' in page
    assert 'https://news.google.com/swg/js/v1/publisher.js' in page
    assert '"@type":"NewsArticle"' in page
    assert '"@type":"Person","name":"Andrew Dobrow"' in page



def test_sitewide_article_search_builds_index_page_and_masthead_control(tmp_path, monkeypatch):
    _setup_root(tmp_path, monkeypatch)
    rows=_archive_rows()
    count=features.write_story_index(rows)
    assert count == len(rows)
    payload=json.loads((tmp_path/"data"/"story-index.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    sample=payload["stories"]["stuart-one"]
    assert sample["teaser"]
    assert "Stuart" in sample["cities"]
    assert "Martin County" in sample["counties"]

    features.render_article_search_page()
    features.inject_site_navigation()
    search=(tmp_path/"search.html").read_text(encoding="utf-8")
    chrome=(tmp_path/"about.html").read_text(encoding="utf-8")
    assert 'name="robots" content="noindex,follow"' in search
    assert 'data-tct-search-page-input' in search
    assert 'data-tct-search-page-results' in search
    assert 'data-tct-search-toggle' in chrome
    assert 'data-tct-search-overlay' in chrome
    assert 'aria-label="Search Treasure Coast Today"' in chrome




def test_missing_persons_nav_is_repaired_even_when_footer_already_has_link(tmp_path, monkeypatch):
    monkeypatch.setattr(features, "ROOT", tmp_path)
    page = tmp_path / "article-like.html"
    page.write_text('''<!doctype html><html><body>
<header class="site-masthead">
<nav id="tct-mobile-nav" class="mobile-nav-panel"><a href="/weather.html" class="mobile-nav-link">Weather</a></nav>
<nav class="category-nav category-nav--primary"><div class="nav-sections-links"><a href="/weather.html" class="nav-section-link">Weather</a></div></nav>
</header>
<footer><div class="footer-links"><a href="/weather.html">Weather</a><a href="/missing-persons.html">Missing Persons</a></div></footer>
</body></html>''', encoding="utf-8")

    features.inject_site_navigation()
    rendered = page.read_text(encoding="utf-8")
    header = rendered.split('</header>', 1)[0]
    assert header.count('/missing-persons.html') == 2
    assert rendered.count('/missing-persons.html') == 3

    features.inject_site_navigation()
    assert page.read_text(encoding="utf-8") == rendered


def test_search_chrome_injection_is_idempotent(tmp_path, monkeypatch):
    _setup_root(tmp_path, monkeypatch)
    features.inject_site_navigation()
    first=(tmp_path/"about.html").read_text(encoding="utf-8")
    features.inject_site_navigation()
    second=(tmp_path/"about.html").read_text(encoding="utf-8")
    assert first == second
    assert second.count('data-tct-search-toggle') == 1
    assert second.count('data-tct-search-overlay') == 1


def test_footer_quick_links_are_migrated_to_two_real_columns():
    html = '''<footer><div class="footer-inner footer-v2"><div class="footer-column"><strong>Quick Links</strong><div class="footer-links">
    <a href="/about.html">About</a><a href="/newsroom.html">Newsroom</a><a href="/archive.html">Archive</a><a href="/contact.html">Contact</a>
    </div></div></div></footer>'''
    first = features._normalize_quick_links_columns(html)
    second = features._normalize_quick_links_columns(first)
    assert first == second
    assert first.count('class="footer-links-column"') == 2
    assert first.count('<a ') == 4


def test_modern_masthead_search_splits_desktop_and_mobile_controls(tmp_path, monkeypatch):
    _setup_root(tmp_path, monkeypatch)
    modern = """<!doctype html><html><body>
<header class="site-masthead"><div class="masthead-top-row">
<div class="masthead-promo-slot"><button type="button" class="mobile-nav-toggle-button"><span></span></button><a class="masthead-newsletter" href="#">Brief</a></div>
<div class="header-top"><a class="wordmark" href="/">TCT</a></div>
<div class="header-actions"><a class="membership-subscribe-btn" href="/subscribe.html">Subscribe</a><a class="membership-header-signin" href="/subscribe.html?signin=1">Sign in</a></div>
</div></header><main></main><footer><div class="footer-links"><a href="/contact.html">Contact</a></div></footer></body></html>"""
    (tmp_path / "about.html").write_text(modern, encoding="utf-8")
    features.inject_site_navigation()
    first=(tmp_path/"about.html").read_text(encoding="utf-8")
    features.inject_site_navigation()
    second=(tmp_path/"about.html").read_text(encoding="utf-8")
    assert first == second
    assert second.count('data-tct-search-toggle') == 2
    assert 'tct-search-toggle--desktop' in second
    assert 'tct-search-toggle--mobile' in second
    hamburger_end = second.index('</button>', second.index('mobile-nav-toggle-button'))
    mobile_pos = second.index('tct-search-toggle--mobile')
    newsletter_pos = second.index('masthead-newsletter')
    assert hamburger_end < mobile_pos < newsletter_pos
    actions_pos = second.index('header-actions')
    desktop_pos = second.index('tct-search-toggle--desktop')
    subscribe_pos = second.index('membership-subscribe-btn')
    signin_pos = second.index('membership-header-signin')
    assert actions_pos < desktop_pos < subscribe_pos < signin_pos


def test_paywall_avoids_duplicate_newsletter_fallback_and_keeps_value_copy():
    html=paywall_section_html("sample-story")
    assert "Not ready to subscribe?" not in html
    assert "free TCT Morning Brief" not in html
    assert "tct-paywall-newsletter-fallback" not in html
    assert "Keep reading for" in html and "$1</span>" in html
    assert "Get full access to every story" in html
    assert "Start for $1" in html
    assert 'tct-paywall-current-price">$1<' in html
    assert 'tct-paywall-old-price">$4.99<' in html
    assert "$4.99/month after your first month. Cancel anytime." in html
    assert "Prefer annual billing?" in html
    assert "$49/year" in html and "$4.08/month" in html
    assert "Unlimited access to every TCT story" in html
    assert "Morning Brief" not in html
    assert "tct-paywall-card" not in html


def test_most_read_implementation_is_aggregate_and_privacy_preserving():
    root=Path(__file__).resolve().parents[1]
    migration=(root/"supabase/migrations/202609080001_story_analytics.sql").read_text(encoding="utf-8")
    function=(root/"supabase/functions/story-analytics/index.ts").read_text(encoding="utf-8")
    main=(root/"main.js").read_text(encoding="utf-8")
    assert "story_pageviews_hourly" in migration
    assert "ip_address" not in migration.lower()
    assert "user_id" not in migration.lower()
    assert "device_id" not in migration.lower()
    assert "increment_story_pageview" in function
    assert "sessionStorage" in main
    assert "data-tct-most-read" in main
    assert "data-tct-search-overlay" in main
    assert "story-index.json" in main


def test_workflow_runs_features_before_paywall_and_validates_after_paywall():
    root=Path(__file__).resolve().parents[1]
    workflow=(root/".github/workflows/update.yml").read_text(encoding="utf-8")
    build=workflow.index("python -u scripts/build_audience_features.py")
    paywall=workflow.index("python scripts/prepare_membership_paywall.py")
    validate=workflow.index("python scripts/validate_seo_contracts.py")
    assert build < paywall < validate
    assert "supabase functions deploy story-analytics" in workflow



def test_final_seo_contract_accepts_recently_ended_event_without_active_event_schema(tmp_path, monkeypatch):
    (tmp_path / "archive.json").write_text("[]", encoding="utf-8")
    (tmp_path / "events").mkdir()
    ended = tmp_path / "events" / "0123456789abcdef12-stuart-art-walk.html"
    ended.write_text(
        """<!doctype html><html><head>
<meta name="robots" content="noindex,follow">
<link rel="canonical" href="https://treasurecoast.today/events/0123456789abcdef12-stuart-art-walk.html">
</head><body>
<p class="event-detail-ended" data-tct-event-ended><strong>This event has ended.</strong></p>
<a class="event-detail-primary" href="https://example.com/event">Official event page →</a>
</body></html>""",
        encoding="utf-8",
    )
    monkeypatch.setattr(seo_contracts, "ROOT", tmp_path)
    report = seo_contracts.validate()
    assert report["events"] == 1


def test_final_seo_contract_still_requires_event_schema_for_active_event_page(tmp_path, monkeypatch):
    import pytest
    (tmp_path / "archive.json").write_text("[]", encoding="utf-8")
    (tmp_path / "events").mkdir()
    active = tmp_path / "events" / "0123456789abcdef12-stuart-art-walk.html"
    active.write_text(
        """<!doctype html><html><head>
<link rel="canonical" href="https://treasurecoast.today/events/0123456789abcdef12-stuart-art-walk.html">
</head><body>
<a class="event-detail-primary" href="https://example.com/event">Official event page →</a>
</body></html>""",
        encoding="utf-8",
    )
    monkeypatch.setattr(seo_contracts, "ROOT", tmp_path)
    with pytest.raises(RuntimeError, match=r"event schema:0123456789abcdef12-stuart-art-walk\.html"):
        seo_contracts.validate()

def test_asset_normalization_migrates_svg_favicon_to_png_sitewide(tmp_path, monkeypatch):
    _setup_root(tmp_path, monkeypatch)
    page = tmp_path / "legacy.html"
    page.write_text(
        '<!doctype html><html><head>'
        '<link rel="icon" href="https://treasurecoast.today/favicon.svg" type="image/svg+xml">'
        '</head><body></body></html>',
        encoding="utf-8",
    )

    report = features.normalize_assets_and_analytics()

    rendered = page.read_text(encoding="utf-8")
    assert '<link rel="icon" href="/favicon.png" type="image/png">' in rendered
    assert "favicon.svg" not in rendered
    assert report["updated"] >= 1


def test_event_detail_unknown_time_uses_date_only_schema_and_safe_copy(tmp_path, monkeypatch):
    _setup_root(tmp_path, monkeypatch)
    (tmp_path/"events.html").write_text(_chrome(), encoding="utf-8")
    event = _event_fixture()
    event.update({
        "starts_at":"2026-09-12T00:00:00-04:00",
        "ends_at":"2026-09-12T00:00:00-04:00",
        "time_known":False,
        "time_source":"unknown",
    })
    (tmp_path/"data"/"events.json").write_text(json.dumps({"schema_version":1,"events":[event]}), encoding="utf-8")
    report = features.render_event_detail_pages()
    assert report["rendered"] == 1
    enriched = json.loads((tmp_path/"data"/"events.json").read_text())
    detail = enriched["events"][0]["detail_url"]
    page = (tmp_path/detail.lstrip('/')).read_text(encoding="utf-8")
    assert "Saturday, September 12, 2026 · See official event for time" in page
    assert '"startDate":"2026-09-12"' in page
    assert '"endDate"' not in page
    assert "at 12:00 AM" not in page
    assert 'name="tct-event-lifecycle-end" content="2026-09-12T23:59:59-04:00"' in page


def test_event_detail_all_day_uses_all_day_copy_and_date_only_schema(tmp_path, monkeypatch):
    _setup_root(tmp_path, monkeypatch)
    (tmp_path/"events.html").write_text(_chrome(), encoding="utf-8")
    event = _event_fixture()
    event.update({
        "starts_at":"2026-09-12T00:00:00-04:00",
        "ends_at":"",
        "all_day":True,
        "time_known":True,
    })
    (tmp_path/"data"/"events.json").write_text(json.dumps({"schema_version":1,"events":[event]}), encoding="utf-8")
    features.render_event_detail_pages()
    enriched = json.loads((tmp_path/"data"/"events.json").read_text())
    detail = enriched["events"][0]["detail_url"]
    page = (tmp_path/detail.lstrip('/')).read_text(encoding="utf-8")
    assert "Saturday, September 12, 2026 · All day" in page
    assert '"startDate":"2026-09-12"' in page
    assert "at 12:00 AM" not in page
