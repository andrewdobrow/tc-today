import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "scripts" / "generate.py"


def _source() -> str:
    return SOURCE_PATH.read_text(encoding="utf-8")


def _fallback_runtime(tmp_path: Path):
    tree = ast.parse(_source())
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "FALLBACK_IMAGE_MAP"
            for target in node.targets
        ):
            selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == "get_fallback_image":
            selected.append(node)
    namespace = {
        "OUTPUT_DIR": tmp_path,
        "SITE_URL": "https://treasurecoast.today",
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE_PATH), "exec"), namespace)
    return namespace


def test_every_editorial_section_maps_to_the_existing_tct_og_asset(tmp_path):
    runtime = _fallback_runtime(tmp_path)
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
    assert runtime["FALLBACK_IMAGE_MAP"] == {key: [value] for key, value in expected.items()}

    for key, filename in expected.items():
        (tmp_path / filename).write_bytes(b"placeholder")
        url, credit = runtime["get_fallback_image"](key, "Any headline", sequential=True)
        assert url == f"https://treasurecoast.today/{filename}"
        assert credit == ""


def test_unknown_or_missing_category_asset_uses_generic_tct_graphic(tmp_path):
    runtime = _fallback_runtime(tmp_path)
    (tmp_path / "og-image.png").write_bytes(b"placeholder")

    assert runtime["get_fallback_image"]("unknown-category") == (
        "https://treasurecoast.today/og-image.png",
        "",
    )
    assert runtime["get_fallback_image"]("crime") == (
        "https://treasurecoast.today/og-image.png",
        "",
    )


def test_legacy_ai_fallback_library_is_no_longer_referenced_by_generator():
    source = _source()
    assert "/images/fallback/" not in source
    assert "local_gov-1.jpg" not in source
    assert "crime-1.jpg" not in source
    assert "business-1.jpg" not in source


def test_engine_release_identifies_branded_og_fallbacks():
    observability = (ROOT / "tct_engine" / "observability.py").read_text(encoding="utf-8")
    assert 'ENGINE_VERSION = "1.11.4.6"' in observability
    assert 'ENGINE_RELEASE = "branded-og-fallbacks"' in observability
