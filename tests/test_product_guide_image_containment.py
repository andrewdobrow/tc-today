from pathlib import Path


def _source():
    return (Path(__file__).resolve().parents[1] / "scripts" / "generate.py").read_text(encoding="utf-8")


def test_product_detail_images_use_compact_auto_sized_media_viewport():
    source = _source()
    assert (
        ".pg-product-image {{ box-sizing:border-box; display:grid; place-items:center; "
        "align-self:start; width:min(100%,280px); max-width:280px; min-width:0; "
        "height:240px; max-height:240px; margin:0 auto; overflow:hidden; padding:14px;"
    ) in source
    assert (
        ".pg-product-image img {{ display:block!important; width:auto!important; "
        "height:auto!important; min-width:0!important; min-height:0!important; "
        "max-width:100%!important; max-height:100%!important;"
    ) in source
    assert "object-fit:contain!important" in source
    assert "contain:layout paint" in source


def test_mobile_product_images_cannot_expand_card_height_or_width():
    source = _source()
    assert (
        ".pg-product-card {{ grid-template-columns:minmax(0,1fr); width:100%; "
        "max-width:100%; padding:17px; }}"
    ) in source
    assert (
        ".pg-product-image {{ width:min(100%,220px); max-width:220px; height:190px; "
        "max-height:190px; margin:0 auto; overflow:hidden; padding:10px; }}"
    ) in source
    assert (
        ".pg-product-image img {{ width:auto!important; height:auto!important; "
        "min-width:0!important; min-height:0!important; max-width:100%!important; "
        "max-height:100%!important;"
    ) in source
    assert "max-height:320px!important" not in source


def test_product_card_itself_is_width_bounded():
    source = _source()
    assert (
        ".pg-product-card {{ box-sizing:border-box; display:grid; "
        "grid-template-columns:minmax(170px,30%) minmax(0,1fr); gap:24px; "
        "width:100%; max-width:100%; min-width:0; overflow:hidden;"
    ) in source


def test_quick_pick_thumbnails_remain_contained_and_unchanged():
    source = _source()
    assert (
        ".pg-quick-picks img {{ display:block; width:44px; height:44px; "
        "object-fit:contain; object-position:center; }}"
    ) in source


def test_template_version_forces_existing_guides_to_republish():
    assert 'PRODUCT_GUIDE_TEMPLATE_VERSION = "1.7-compact-auto-sized-product-media"' in _source()
