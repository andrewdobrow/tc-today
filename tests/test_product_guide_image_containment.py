from pathlib import Path


def _source():
    return (Path(__file__).resolve().parents[1] / "scripts" / "generate.py").read_text(encoding="utf-8")


def test_product_detail_images_use_bounded_contain_media_viewport():
    source = _source()
    assert (
        ".pg-product-image {{ box-sizing:border-box; display:grid; place-items:center; "
        "width:100%; max-width:100%; min-width:0; height:280px; max-height:280px; "
        "overflow:hidden; padding:18px;"
    ) in source
    assert (
        ".pg-product-image img {{ display:block!important; width:100%!important; "
        "height:100%!important; min-width:0!important; min-height:0!important; "
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
        ".pg-product-image {{ width:100%; max-width:100%; height:230px; "
        "max-height:230px; overflow:hidden; padding:12px; }}"
    ) in source
    assert (
        ".pg-product-image img {{ width:100%!important; height:100%!important; "
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
    assert 'PRODUCT_GUIDE_TEMPLATE_VERSION = "1.5-bounded-contain-product-media"' in _source()
