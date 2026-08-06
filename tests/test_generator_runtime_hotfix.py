from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
PATCHER_PATH = ROOT / "scripts" / "apply_generator_runtime_hotfix.py"
spec = importlib.util.spec_from_file_location("generator_hotfix", PATCHER_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _fixture() -> str:
    return '''import html as html_lib\n\ndef _apply_article_content_overrides_to_outputs(output_dir):\n    old_h1 = object()\n    old_headline = html.unescape(str(old_h1))\n    return old_headline\n\ndef _audit_editorial_candidates(engine, headlines, category_key, audited_keys, audit_rows):\n    if engine is None:\n        return\n\n    for entry in headlines:\n        try:\n            engine.process(entry, source="rss")\n        except Exception:\n            pass\n\ndef _save_editorial_engine_audit(engine, audit_rows):\n    return None\n'''


def test_hotfix_repairs_html_alias_and_batches_registry_writes():
    patched, changes = module.patch_source(_fixture())
    assert changes == {
        "html_alias_changed": True,
        "registry_batching_changed": True,
    }
    assert "html_lib.unescape(" in patched
    assert "html.unescape(" not in patched
    assert "with engine._pipeline.defer_registry_saves(commit=True):" in patched
    compile(patched, "fixture.py", "exec")


def test_hotfix_is_idempotent():
    first, _ = module.patch_source(_fixture())
    second, changes = module.patch_source(first)
    assert second == first
    assert changes == {
        "html_alias_changed": False,
        "registry_batching_changed": False,
    }
