from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "scripts" / "generate.py"


def _source() -> str:
    return SOURCE_PATH.read_text(encoding="utf-8")


def test_branded_og_assets_remain_the_final_fallback_layer():
    source = _source()
    expected = {
        "local_gov": "og-local_gov.png",
        "crime": "og-crime.png",
        "business": "og-business.png",
        "sports": "og-sports.png",
        "things_to_do": "og-things_to_do.png",
        "florida": "og-florida.png",
        "martin": "og-martin.png",
        "st_lucie": "og-st_lucie.png",
        "indian_river": "og-indian_river.png",
        "top_news": "og-image.png",
    }
    for key, filename in expected.items():
        assert f'"{key}":' in source
        assert f'["{filename}"]' in source
    assert "selection = _select_editorial_fallback(" in source
    assert "return _branded_fallback_image(category_key)" in source


def test_legacy_ai_urls_are_migration_inputs_not_active_pool_entries():
    source = _source()
    assert '"local_gov":    ["og-local_gov.png"]' in source
    assert "local_gov-1.jpg" not in source
    assert "crime-1.jpg" not in source
    assert "business-1.jpg" not in source
    assert 'if "/images/fallback/" in path:' in source


def test_engine_release_identifies_contextual_update_lead_guard():
    observability = (ROOT / "tct_engine" / "observability.py").read_text(encoding="utf-8")
    assert 'ENGINE_VERSION = "1.11.8.4.1"' in observability
    assert 'ENGINE_RELEASE = "first-responder-image-fallback-hotfix"' in observability
