from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
PATCHER_PATH = ROOT / "scripts" / "apply_generator_runtime_hotfix.py"
spec = importlib.util.spec_from_file_location("generator_hotfix", PATCHER_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _fixture(*, already_batched: bool = False) -> str:
    audit_body = '''def _audit_editorial_candidates(engine, headlines, category_key, audited_keys, audit_rows):
    if engine is None:
        return

    for entry in headlines:
        try:
            engine.process(entry, source="rss")
        except Exception:
            pass
'''
    if already_batched:
        audit_body = '''def _audit_editorial_candidates(engine, headlines, category_key, audited_keys, audit_rows):
    if engine is None:
        return

    # v1.13.1.3: batch persistent registry writes for this category.
    with engine._pipeline.defer_registry_saves(commit=True):
        for entry in headlines:
            try:
                engine.process(entry, source="rss")
            except Exception:
                pass
'''
    return f'''import html as html_lib

def _apply_article_content_overrides_to_outputs(output_dir):
    old_h1 = object()
    old_headline = html.unescape(str(old_h1))
    headline = "Example"
    esc_headline = html.escape(headline, quote=True)
    esc_body = html.escape("Body")
    return old_headline, esc_headline, esc_body

{audit_body}
def _save_editorial_engine_audit(engine, audit_rows):
    return None
'''


def test_hotfix_repairs_every_html_namespace_call_and_batches_registry_writes():
    patched, changes = module.patch_source(_fixture())
    assert changes == {
        "html_alias_changed": True,
        "registry_batching_changed": True,
    }
    assert "html_lib.unescape(" in patched
    assert patched.count("html_lib.escape(") == 2
    assert "html.unescape(" not in patched
    assert "html.escape(" not in patched
    assert "with engine._pipeline.defer_registry_saves(commit=True):" in patched
    compile(patched, "fixture.py", "exec")


def test_hotfix_repairs_escape_left_by_v1_13_1_3_without_rebatching():
    source = _fixture(already_batched=True).replace(
        "old_headline = html.unescape(str(old_h1))",
        "old_headline = html_lib.unescape(str(old_h1))",
    )
    patched, changes = module.patch_source(source)
    assert changes == {
        "html_alias_changed": True,
        "registry_batching_changed": False,
    }
    assert "html.escape(" not in patched
    assert patched.count("html_lib.escape(") == 2
    assert patched.count("defer_registry_saves(commit=True)") == 1


def test_hotfix_is_idempotent_after_complete_namespace_repair():
    first, _ = module.patch_source(_fixture())
    second, changes = module.patch_source(first)
    assert second == first
    assert changes == {
        "html_alias_changed": False,
        "registry_batching_changed": False,
    }
