from pathlib import Path


def test_product_guide_images_use_a_definite_containment_canvas():
    source = (Path(__file__).resolve().parents[1] / "scripts" / "generate.py").read_text(
        encoding="utf-8"
    )

    assert (
        ".pg-product-card {{ display:grid; "
        "grid-template-columns:minmax(170px,30%) minmax(0,1fr); "
        "gap:24px; min-width:0; overflow:hidden;"
    ) in source
    assert (
        ".pg-product-image {{ box-sizing:border-box; display:grid; place-items:center; "
        "width:100%; min-width:0; height:230px; min-height:230px; overflow:hidden;"
    ) in source
    assert (
        ".pg-product-image img {{ display:block; width:100%; height:100%; "
        "max-width:100%; max-height:100%; object-fit:contain; object-position:center; }}"
    ) in source


def test_mobile_product_images_cannot_escape_or_crop_their_wrapper():
    source = (Path(__file__).resolve().parents[1] / "scripts" / "generate.py").read_text(
        encoding="utf-8"
    )

    assert ".pg-product-card {{ grid-template-columns:minmax(0,1fr); padding:17px; }}" in source
    assert (
        ".pg-product-image {{ width:100%; height:210px; min-height:210px; padding:16px; }}"
    ) in source
    assert (
        ".pg-product-image img {{ width:100%; height:100%; max-width:100%; "
        "max-height:100%; object-fit:contain; object-position:center; }}"
    ) in source
    assert "width:auto; max-width:100%; height:auto; max-height:100%" not in source


def test_quick_pick_thumbnails_remain_contained():
    source = (Path(__file__).resolve().parents[1] / "scripts" / "generate.py").read_text(
        encoding="utf-8"
    )
    assert (
        ".pg-quick-picks img {{ display:block; width:44px; height:44px; "
        "object-fit:contain; object-position:center; }}"
    ) in source
