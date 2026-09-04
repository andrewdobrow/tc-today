from pathlib import Path


KIT_INLINE_FORM_UID = "30e15672d3"
KIT_INLINE_FORM_SRC = "https://treasure-coast-today.kit.com/30e15672d3/index.js"
KIT_MODAL_FORM_UID = "be625cadfe"


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


def test_article_template_uses_dormant_paywall_newsletter_slot_after_body():
    source = _source()
    body = '<div class="article-body">{body}</div>'
    slot = '{_paywall_newsletter_slot()}'
    assert body in source
    assert slot in source
    assert '{_newsletter_inline_embed("article")}' not in source
    assert source.index(body) < source.index(slot)


def test_inline_form_is_rendered_beneath_hero_inside_lead_stack():
    source = _source()
    stack = '<div class="lead-stack">'
    hero_row = '<div class="lead-primary">{heroes_html}</div>'
    slot = '{_newsletter_inline_embed("category-hero")}'
    rail = '<aside class="latest-rail">'
    assert stack in source
    assert hero_row in source
    assert slot in source
    homepage = source.index('<main class="homepage-v2">')
    assert source.index(stack, homepage) < source.index(hero_row, homepage)
    assert source.index(hero_row, homepage) < source.index(slot, homepage)
    assert source.index(slot, homepage) < source.index(rail, homepage)


def test_inline_and_modal_kit_forms_use_distinct_uids():
    source = _source()
    runtime = (Path(__file__).resolve().parents[1] / "main.js").read_text(
        encoding="utf-8"
    )
    assert KIT_INLINE_FORM_UID != KIT_MODAL_FORM_UID
    assert KIT_MODAL_FORM_UID in runtime
    assert KIT_INLINE_FORM_UID in source


def test_inline_slot_css_keeps_form_within_tct_content_width():
    css = (Path(__file__).resolve().parents[1] / "style.css").read_text(encoding="utf-8")
    assert ".newsletter-inline-slot" in css
    assert ".lead-stack > .newsletter-inline-slot--category-hero" in css
    assert ".article-main-column > .newsletter-inline-slot" in css
    assert "max-width: none !important" in css
