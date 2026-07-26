from pathlib import Path


def test_product_guide_images_are_confined_without_distortion():
    source = (Path(__file__).resolve().parents[1] / 'scripts' / 'generate.py').read_text(encoding='utf-8')
    assert '.pg-product-image {{ display:grid; place-items:center; height:230px;' in source
    assert 'overflow:hidden; padding:18px;' in source
    assert 'width:auto; max-width:100%; height:auto; max-height:100%; object-fit:contain; object-position:center;' in source
    assert '.pg-product-image {{ height:210px; min-height:210px; padding:16px; }}' in source
    assert '.pg-quick-picks img {{ display:block; width:44px; height:44px; object-fit:contain; object-position:center; }}' in source
