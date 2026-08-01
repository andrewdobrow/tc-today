from pathlib import Path


KIT_INLINE_FORM_UID = "30e15672d3"
KIT_INLINE_FORM_SRC = "https://treasure-coast-today.kit.com/30e15672d3/index.js"
KIT_STICKY_FORM_UID = "4edef44197"


def _source() -> str:
    return (
        Path(__file__).resolve().parents[1] / "scripts" / "generate.py"
    ).read_text(encoding="utf-8")


def test_inline_kit_embed_is_defined_once_and_is_async_https():
    source = _source()
    assert source.count(KIT_INLINE_FORM_SRC) == 1
    assert f'KIT_INLINE_FORM_UID = "{KIT_INLINE_FORM_UID}"' in source
    assert '<script async data-uid="{KIT_INLINE_FORM_UID}"' in source
    assert 'src="{KIT_INLINE_FORM_SRC}"></script>' in source


def test_inline_form_is_rendered_after_every_article_body():
    source = _source()
    body = '<div class="article-body">{body}</div>'
    slot = '{_newsletter_inline_embed("article")}'
    assert body in source
    assert slot in source
    assert source.index(body) < source.index(slot)


def test_inline_form_is_rendered_immediately_after_category_hero_row():
    source = _source()
    hero_row = '<div class="lead-primary">{heroes_html}</div>'
    slot = '{_newsletter_inline_embed("category-hero")}'
    top_stories = '<section class="top-stories-v2">'
    assert hero_row in source
    assert slot in source
    homepage = source.index('<main class="homepage-v2">')
    assert source.index(hero_row, homepage) < source.index(slot, homepage)
    assert source.index(slot, homepage) < source.index(top_stories, homepage)


def test_inline_and_sticky_kit_forms_use_distinct_uids():
    source = _source()
    assert KIT_INLINE_FORM_UID != KIT_STICKY_FORM_UID
    assert KIT_STICKY_FORM_UID in source
    assert KIT_INLINE_FORM_UID in source


def test_inline_slot_css_keeps_form_within_tct_content_width():
    css = (Path(__file__).resolve().parents[1] / "style.css").read_text(encoding="utf-8")
    assert ".newsletter-inline-slot" in css
    assert ".homepage-v2 > .newsletter-inline-slot--category-hero" in css
    assert ".article-main-column > .newsletter-inline-slot" in css
    assert "max-width: none !important" in css
