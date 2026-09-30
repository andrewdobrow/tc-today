import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SLUG='2026-08-06-martin-county-sheriffs-office-seeks-public-help-finding-missing-14-year-old-auti'

def test_ethan_boyd_resolution_override_is_durable():
    payload=json.loads((ROOT/'data/article-content-overrides.json').read_text())
    row=payload['overrides'][SLUG]
    assert row['headline']=='Missing 14-year-old autistic boy Ethan Boyd safely located, Martin County sheriff says'
    assert row['image_url']=='https://treasurecoast.today/images/ethan-boyd.png'
    assert row['update_status']=='resolved'
    assert 'safely located' in row['update_text']

def test_canonical_page_keeps_permalink_image_and_resolution_update():
    text=(ROOT/'articles'/f'{SLUG}.html').read_text()
    assert 'Missing 14-year-old autistic boy Ethan Boyd safely located' in text
    assert 'UPDATE — Aug. 5, 2026, 11:44 p.m.:' in text
    assert 'https://treasurecoast.today/images/ethan-boyd.png' in text
    assert f'<link rel="canonical" href="https://treasurecoast.today/articles/{SLUG}.html">' in text
    assert text.count('Original report:') <= 1
    assert len(re.findall(r'(?<![\w-])data-tct-paywall(?![\w-])', text, re.I)) == 1
    assert text.count('<div id="tct-protected-content"') == 1
    assert text.count('<aside class="article-side-rail">') == 1
    assert text.count('<div class="article-share">') == 1


def test_override_replaces_entire_paywall_region_and_is_idempotent(tmp_path, monkeypatch):
    import sys
    import types

    feedparser = types.ModuleType("feedparser")
    feedparser.parse = lambda *args, **kwargs: None
    anthropic = types.ModuleType("anthropic")
    anthropic.Anthropic = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "feedparser", feedparser)
    monkeypatch.setitem(sys.modules, "anthropic", anthropic)
    from scripts import generate

    root = tmp_path / 'site'
    (root / 'data').mkdir(parents=True)
    (root / 'articles').mkdir()
    override = {
        'version': 1,
        'overrides': {
            SLUG: {
                'headline': 'Missing 14-year-old autistic boy Ethan Boyd safely located, Martin County sheriff says',
                'teaser': 'Ethan Boyd was safely located.',
                'body': 'Original paragraph one.\n\nOriginal paragraph two.\n\nOriginal paragraph three.',
                'update_label': 'UPDATE — Aug. 5, 2026, 11:44 p.m.:',
                'update_text': 'Ethan Boyd has been safely located.',
                'original_label': 'Original report:',
            }
        },
    }
    (root / 'data' / 'article-content-overrides.json').write_text(json.dumps(override))
    (root / 'archive.json').write_text(json.dumps([{'slug': SLUG, 'headline': 'Old headline'}]))

    repeated = (
        '<p><strong>Original report:</strong></p><p>Old original paragraph.</p></div>'
        '<p><strong>Original report:</strong></p><p>Old original paragraph.</p></div>'
    )
    page = f'''<html><head><title>Old | Treasure Coast Today</title><meta name="description" content="old"><meta property="og:title" content="old"><meta property="og:description" content="old"></head><body>
<h1 class="article-headline">Old headline</h1>
<div class="article-editorial-grid"><div class="article-main-column">
<figure class="article-hero-image"><img src="old.jpg"></figure>
<div class="article-body tct-member-preview"><div class="tct-preview-copy"><p>Old preview</p></div></div>
<div class="tct-member-only"><section class="tct-paywall" data-tct-paywall></section><div id="tct-protected-content" class="article-body tct-protected-content"></div></div>{repeated}
<aside class="newsletter-inline-slot newsletter-inline-slot--article">newsletter</aside>
<div class="article-share">share</div></div><aside class="article-side-rail">TOP NEWS SIDEBAR</aside></div>
</body></html>'''
    article = root / 'articles' / f'{SLUG}.html'
    article.write_text(page)

    assert generate._apply_article_content_overrides_to_outputs(root) == 1
    first = article.read_text()
    assert first.count('Original report:') == 1
    assert first.count('Old original paragraph.') == 0
    assert first.count('data-tct-paywall') == 0
    assert first.count('TOP NEWS SIDEBAR') == 1
    assert '<aside class="newsletter-inline-slot newsletter-inline-slot--article">newsletter</aside>' in first
    assert '<div class="article-share">share</div>' in first

    # A second production pass must not append another copy of the manual update.
    assert generate._apply_article_content_overrides_to_outputs(root) == 1
    second = article.read_text()
    assert second == first
    assert second.count('Original report:') == 1


def test_headline_only_override_preserves_existing_body_and_descriptions(tmp_path, monkeypatch):
    import sys
    import types

    feedparser = types.ModuleType("feedparser")
    feedparser.parse = lambda *args, **kwargs: None
    anthropic = types.ModuleType("anthropic")
    anthropic.Anthropic = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "feedparser", feedparser)
    monkeypatch.setitem(sys.modules, "anthropic", anthropic)
    from scripts import generate

    root = tmp_path / "site"
    (root / "data").mkdir(parents=True)
    (root / "articles").mkdir()
    slug = "2026-09-30-23-month-old-drowns-in-pond-on-family-property-in-martin-county"
    old_headline = "Toddler drowned in 10 minutes, pronounced dead at Cleveland Clinic South"
    new_headline = "Martin County toddler drowned in family pond after being out of sight no more than 10 minutes"
    old_description = "A 23-month-old boy drowned in a pond on his family's property in Martin County."
    old_body = "<div class=\"article-body\"><p>Existing full article body stays exactly here.</p></div>"

    (root / "data" / "article-content-overrides.json").write_text(json.dumps({
        "version": 1,
        "overrides": {slug: {"headline": new_headline, "update_status": "headline_context_correction"}},
    }))
    (root / "archive.json").write_text(json.dumps([{
        "slug": slug,
        "headline": old_headline,
        "teaser": old_description,
    }]))
    page = f'''<html><head><title>{old_headline} | Treasure Coast Today</title>
<meta name="description" content="{old_description}">
<meta property="og:title" content="{old_headline} | Treasure Coast Today">
<meta property="og:description" content="{old_description}">
<script type="application/ld+json">{{"headline": {json.dumps(old_headline)}, "description": {json.dumps(old_description)}}}</script>
</head><body><h1 class="article-headline">{old_headline}</h1>{old_body}<div class="article-share">share</div></body></html>'''
    article = root / "articles" / f"{slug}.html"
    article.write_text(page)

    assert generate._apply_article_content_overrides_to_outputs(root) == 1
    rendered = article.read_text()
    assert new_headline in rendered
    assert old_description in rendered
    assert "Existing full article body stays exactly here." in rendered
    assert "article-update" not in rendered
    assert "Original report:" not in rendered


def test_headline_only_override_projects_to_live_hero_and_top_story_candidate(monkeypatch):
    import sys
    import types

    feedparser = types.ModuleType("feedparser")
    feedparser.parse = lambda *args, **kwargs: None
    anthropic = types.ModuleType("anthropic")
    anthropic.Anthropic = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "feedparser", feedparser)
    monkeypatch.setitem(sys.modules, "anthropic", anthropic)
    from scripts import generate

    slug = "2026-09-30-23-month-old-drowns-in-pond-on-family-property-in-martin-county"
    old_headline = "Toddler drowned in 10 minutes, pronounced dead at Cleveland Clinic South"
    new_headline = "Martin County toddler drowned in family pond after being out of sight no more than 10 minutes"
    hero = {
        "headline": old_headline,
        "link": f"https://treasurecoast.today/articles/{slug}.html",
    }
    card = {
        "headline": old_headline,
        "_archived_slug": slug,
    }
    categories = [{"category_key": "martin", "hero": hero, "cards": [card]}]
    overrides = {
        slug: {
            "headline": new_headline,
            "update_status": "headline_context_correction",
        }
    }

    changed = generate._apply_article_content_overrides_to_categories(
        categories, categories[0], overrides=overrides
    )

    assert changed == 2
    assert hero["headline"] == new_headline
    assert card["headline"] == new_headline
    assert hero["update_status"] == "headline_context_correction"
    assert card["update_status"] == "headline_context_correction"


def test_production_applies_content_overrides_before_homepage_and_rss_rendering():
    source = (ROOT / "scripts" / "generate.py").read_text(encoding="utf-8")
    early = source.index("_early_content_override_count = _apply_article_content_overrides_to_outputs")
    homepage = source.index("index_html = render_index(all_categories, top_cat)")
    rss = source.index('(OUTPUT_DIR / "feed.xml").write_text(render_rss_feed(all_categories, top_cat)')
    assert early < homepage < rss
    final_live = source.index("_final_live_content_override_count = _apply_article_content_overrides_to_categories")
    assert early < final_live < homepage
