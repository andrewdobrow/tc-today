from pathlib import Path


def _source():
    return (Path(__file__).resolve().parents[1] / "scripts" / "generate.py").read_text(encoding="utf-8")


def test_product_detail_images_use_natural_aspect_without_a_clipping_frame():
    source = _source()
    assert (
        ".pg-product-image {{ box-sizing:border-box; display:flex; align-items:center; "
        "justify-content:center; width:100%; min-width:0; min-height:230px; padding:18px;"
    ) in source
    assert (
        ".pg-product-image img {{ display:block!important; width:auto!important; "
        "height:auto!important; max-width:100%!important; max-height:280px!important; "
        "aspect-ratio:auto!important; object-fit:contain!important;"
    ) in source
    assert ".pg-product-image {{ box-sizing:border-box; display:grid" not in source
    assert "height:230px; min-height:230px; overflow:hidden" not in source


def test_mobile_product_images_keep_full_natural_aspect():
    source = _source()
    assert ".pg-product-card {{ grid-template-columns:minmax(0,1fr); padding:17px; }}" in source
    assert ".pg-product-image {{ width:100%; min-height:0; padding:16px; }}" in source
    assert (
        ".pg-product-image img {{ width:auto!important; height:auto!important; "
        "max-width:100%!important; max-height:320px!important; aspect-ratio:auto!important; "
        "object-fit:contain!important;"
    ) in source
    assert "height:210px; min-height:210px" not in source


def test_quick_pick_thumbnails_remain_contained():
    source = _source()
    assert (
        ".pg-quick-picks img {{ display:block; width:44px; height:44px; "
        "object-fit:contain; object-position:center; }}"
    ) in source


def test_template_version_forces_existing_guides_to_republish():
    assert 'PRODUCT_GUIDE_TEMPLATE_VERSION = "1.4-natural-aspect-image-containment"' in _source()
