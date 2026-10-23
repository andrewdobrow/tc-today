"""Canonical, verified October 23 incident update and article-shell regression."""
import json
import os
import re
import sys
import types
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SLUG = "2026-10-09-port-st-lucie-police-seek-help-identifying-critically-injured-man-found-on-roadw"

def _load_generator():
    if "feedparser" not in sys.modules:
        f = types.ModuleType("feedparser")
        f.parse = lambda *a, **k: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = f
    if "anthropic" not in sys.modules:
        a = types.ModuleType("anthropic")
        class Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda *args, **kwargs: None)
        a.Anthropic = Anthropic
        sys.modules["anthropic"] = a
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    from scripts import generate
    return generate

def test_verified_psl_correction_exists_and_keeps_identity_unchanged():
    overrides = json.loads((ROOT / "data/article-content-overrides.json").read_text())['overrides']
    row = overrides[SLUG]
    assert 'Eric Saint Aude' in row['headline']
    assert 'Eric Saint Aude' in row['update_text']
    assert 'leaving the scene' in row['update_text']
    assert 'second vehicle' in row['body'].lower()
    assert 'news conference at 1' not in (row['body'] + row['update_text']).lower()
    assert row['update_status'] == 'verified_arrest_report'
    assert all(u.startswith('https://') for u in row['verification_sources'])
    assert 'slug' not in row and 'custom_id' not in row

def test_verified_psl_repair_replaces_outdated_body_and_stray_newsletter_markup(tmp_path):
    g = _load_generator()
    root = tmp_path
    (root / 'data').mkdir()
    (root / 'articles').mkdir()
    overrides = json.loads((ROOT / 'data/article-content-overrides.json').read_text())
    (root / 'data/article-content-overrides.json').write_text(json.dumps(overrides))
    (root / 'archive.json').write_text(json.dumps([{'slug': SLUG, 'headline': 'Old story', 'teaser': 'Old preview'}]))
    # A nested paywall and accidentally leaked raw newsletter fragment must
    # not survive the authoritative verified content-region replacement.
    broken = ('<!doctype html><html><head><title>Old story | Treasure Coast Today</title>'
        '<meta name="description" content="Old preview">'
        '<meta property="og:title" content="Old story">'
        '<meta property="og:description" content="Old preview">'
        '</head><body><h1 class="article-headline">Old story</h1>'
        '<div class="article-body tct-member-preview"><div class="tct-preview-copy">'
        '<p>Information will be released at a news conference at 1 p.m.</p>'
        '<p>slot--article" aria-label="Subscribe to the Treasure Coast Morning Brief"></p>'
        '</div></div><div class="tct-member-only">'
        '<section class="tct-paywall" data-tct-paywall></section>'
        '<div id="tct-protected-content" class="article-body"></div></div>'
        '<aside class="newsletter-inline-slot newsletter-inline-slot--article" '
        'aria-label="Subscribe to the Treasure Coast Morning Brief">'
        '<script async data-uid="30e15672d3" '
        'src="https://treasure-coast-today.kit.com/30e15672d3/index.js"></script></aside>'
        '<div class="article-share">share</div></body></html>')
    page = root / 'articles' / f'{SLUG}.html'
    page.write_text(broken)
    assert g._apply_article_content_overrides_to_outputs(root) == 1
    updated = page.read_text()
    soup = BeautifulSoup(updated, 'html.parser')
    visible = soup.get_text(' ', strip=True)
    assert 'Eric Saint Aude' in visible
    assert 'news conference at 1' not in visible.lower()
    assert 'slot--article" aria-label' not in visible
    assert len(soup.select('aside.newsletter-inline-slot--article')) == 1
    assert len(soup.select('.article-share')) == 1
    assert len(soup.select('div.article-body')) == 1
    assert len(soup.select('[data-tct-paywall]')) == 0  # membership stage rebuilds it
    assert g._apply_article_content_overrides_to_outputs(root) == 1
    assert page.read_text() == updated
    rows = json.loads((root / 'archive.json').read_text())
    assert rows[0]['slug'] == SLUG
    assert 'Eric Saint Aude' in rows[0]['body'] or 'Eric Saint Aude' in rows[0]['teaser']

def test_verified_psl_full_content_is_long_enough_for_membership_split():
    from tct_engine.membership_paywall import split_article_body
    import html
    row = json.loads((ROOT/'data/article-content-overrides.json').read_text())['overrides'][SLUG]
    paragraphs = [row['update_text']] + [part.strip() for part in row['body'].split('\n\n') if part.strip()]
    source = ''.join('<p>'+html.escape(part)+'</p>' for part in paragraphs)
    split = split_article_body(source)
    assert split is not None
    assert 'Eric Saint Aude' in split.preview_html + split.protected_html
    assert 'second vehicle' in split.protected_html.lower()


def test_verified_psl_override_survives_membership_preparation(tmp_path, monkeypatch):
    import importlib.util
    import html
    g = _load_generator()
    root = tmp_path / 'site'
    (root / 'data').mkdir(parents=True)
    (root / 'articles').mkdir()
    payload = json.loads((ROOT/'data/article-content-overrides.json').read_text())
    (root/'data/article-content-overrides.json').write_text(json.dumps(payload))
    (root/'archive.json').write_text(json.dumps([{'slug':SLUG,'headline':'Old story','source_url':'https://www.wptv.com/'}]))
    page = root / 'articles' / f'{SLUG}.html'
    page.write_text('<html><head><title>Old | Treasure Coast Today</title></head><body>'
        '<h1 class="article-headline">Old story</h1>'
        '<div class="article-body tct-member-preview"><p>Old preview</p></div>'
        '<div class="tct-member-only"><section data-tct-paywall></section>'
        '<div id="tct-protected-content" class="article-body"></div></div>'
        '<aside class="newsletter-inline-slot newsletter-inline-slot--article">'
        '<script async data-uid="30e15672d3" '
        'src="https://treasure-coast-today.kit.com/30e15672d3/index.js"></script>'
        '</aside><div class="article-share">share</div></body></html>')
    assert g._apply_article_content_overrides_to_outputs(root) == 1
    spec = importlib.util.spec_from_file_location('psl_membership_prep_test', ROOT/'scripts/prepare_membership_paywall.py')
    prep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prep)
    monkeypatch.setattr(prep,'ROOT',root)
    monkeypatch.setattr(prep,'ARTICLES',root/'articles')
    out = tmp_path/'protected-out.json'
    monkeypatch.setenv('TCT_MEMBERSHIP_UI_ENABLED','true')
    monkeypatch.setenv('TCT_PROTECTED_EXPORT_PATH',str(out))
    monkeypatch.delenv('TCT_PROTECTED_SNAPSHOT_PATH',raising=False)
    prep.main()
    result = page.read_text()
    export = json.loads(out.read_text())
    assert result.count('data-tct-paywall') >= 1
    assert result.count('newsletter-inline-slot--article') == 1
    assert len(export['articles']) == 1
    assert export['articles'][0]['slug'] == SLUG
    assert 'second vehicle' in html.unescape(export['articles'][0]['protected_body']).lower()
    assert 'news conference at 1' not in result.lower()
