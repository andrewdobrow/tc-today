import json
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("restore_external_images", ROOT / "scripts" / "restore_external_article_images.py")
restore_mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(restore_mod)


def test_restore_uses_registry_without_bunny_network(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "articles").mkdir()
    slug = "2026-10-02-story"
    hosted = "https://images.treasurecoast.today/articles/aa/hash.jpg"
    original = "https://publisher.test/photo.jpg"
    registry = {
        "articles": {
            slug: {
                "current_image": {
                    "public_url": hosted,
                    "original_url": original,
                    "status": "mirrored",
                }
            }
        }
    }
    (tmp_path / "data" / "article-image-registry.json").write_text(json.dumps(registry))
    (tmp_path / "articles" / f"{slug}.html").write_text(f'<img src="{hosted}"><meta property="og:image" content="{hosted}">')
    archive = [{"slug": slug, "image_url": hosted, "source_image_url": original, "hosted_image_url": hosted}]
    (tmp_path / "archive.json").write_text(json.dumps(archive))

    dry = restore_mod.restore(tmp_path, apply=False)
    assert dry["article_pages_changed"] == 1
    assert hosted in (tmp_path / "articles" / f"{slug}.html").read_text()

    applied = restore_mod.restore(tmp_path, apply=True)
    assert applied["article_pages_changed"] == 1
    assert original in (tmp_path / "articles" / f"{slug}.html").read_text()
    saved = json.loads((tmp_path / "archive.json").read_text())
    assert saved[0]["image_url"] == original
    assert saved[0]["source_image_url"] == original
    assert saved[0]["hosted_image_url"] == hosted
