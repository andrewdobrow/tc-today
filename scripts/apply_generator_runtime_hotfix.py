#!/usr/bin/env python3
"""Apply the v1.13.1.4 generator runtime and registry-write hotfix.

This patch edits the repository's current ``scripts/generate.py`` in place. It
never replaces that large file, so newer article, identity, and content changes
remain intact.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import tempfile

CONTENT_OVERRIDE_FUNCTION = "def _apply_article_content_overrides_to_outputs"
AUDIT_FUNCTION = "def _audit_editorial_candidates"
NEXT_AUDIT_FUNCTION = "\ndef _save_editorial_engine_audit"
BATCH_MARKER = "# v1.13.1.3: batch persistent registry writes for this category."
BARE_HTML_REFERENCE = re.compile(r"(?<![A-Za-z0-9_.])html\.")


def _function_bounds(
    source: str,
    function_name: str,
    next_function: str | None = None,
) -> tuple[int, int] | None:
    start = source.find(function_name)
    if start < 0:
        return None
    if next_function:
        end = source.find(next_function, start)
    else:
        end = source.find("\ndef ", start + len(function_name))
    if end < 0:
        end = len(source)
    return start, end


def _ensure_html_alias(source: str) -> tuple[str, bool]:
    """Replace every bare ``html.*`` call in the content-override function.

    v1.13.1.3 repaired only ``html.unescape``. The production generator also
    used ``html.escape`` later in the same function, causing another late-run
    NameError. This version intentionally covers the entire module namespace.
    """
    bounds = _function_bounds(source, CONTENT_OVERRIDE_FUNCTION)
    if bounds is None:
        return source, False

    start, end = bounds
    block = source[start:end]
    if not BARE_HTML_REFERENCE.search(block):
        return source, False

    if "import html as html_lib" not in source:
        anchor = "import threading\n"
        if anchor not in source:
            raise RuntimeError("Cannot safely add html_lib import: import anchor missing")
        source = source.replace(anchor, anchor + "import html as html_lib\n", 1)
        bounds = _function_bounds(source, CONTENT_OVERRIDE_FUNCTION)
        assert bounds is not None
        start, end = bounds
        block = source[start:end]

    patched_block = BARE_HTML_REFERENCE.sub("html_lib.", block)
    return source[:start] + patched_block + source[end:], patched_block != block


def _batch_audit_registry_writes(source: str) -> tuple[str, bool]:
    """Coalesce multi-megabyte registry writes performed for audit items."""
    bounds = _function_bounds(source, AUDIT_FUNCTION, NEXT_AUDIT_FUNCTION)
    if bounds is None:
        raise RuntimeError("Cannot locate _audit_editorial_candidates")

    start, end = bounds
    block = source[start:end]
    if BATCH_MARKER in block:
        return source, False

    loop_token = "\n    for entry in headlines:\n"
    loop_at = block.find(loop_token)
    if loop_at < 0:
        raise RuntimeError("Cannot locate editorial audit candidate loop")

    before = block[:loop_at]
    loop_and_body = block[loop_at + 1 :]
    indented = "\n".join(("    " + line) if line else line for line in loop_and_body.split("\n"))
    replacement = (
        before
        + "\n    " + BATCH_MARKER + "\n"
        + "    with engine._pipeline.defer_registry_saves(commit=True):\n"
        + indented
    )
    return source[:start] + replacement + source[end:], True


def patch_source(source: str) -> tuple[str, dict[str, bool]]:
    patched, html_changed = _ensure_html_alias(source)
    patched, batching_changed = _batch_audit_registry_writes(patched)

    content_bounds = _function_bounds(patched, CONTENT_OVERRIDE_FUNCTION)
    if content_bounds is not None:
        content_block = patched[content_bounds[0] : content_bounds[1]]
        remaining = sorted(set(BARE_HTML_REFERENCE.findall(content_block)))
        if remaining:
            raise RuntimeError(
                "Bare html namespace reference remains in content override function"
            )
        # Explicit guards make future regressions obvious in logs/tests.
        for forbidden in ("html.escape(", "html.unescape("):
            if forbidden in content_block:
                raise RuntimeError(f"Unrepaired runtime reference remains: {forbidden}")

    audit_bounds = _function_bounds(patched, AUDIT_FUNCTION, NEXT_AUDIT_FUNCTION)
    assert audit_bounds is not None
    audit_block = patched[audit_bounds[0] : audit_bounds[1]]
    if BATCH_MARKER not in audit_block:
        raise RuntimeError("Editorial audit registry batching was not installed")

    compile(patched, "scripts/generate.py", "exec")
    return patched, {
        "html_alias_changed": html_changed,
        "registry_batching_changed": batching_changed,
    }


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="scripts/generate.py")
    parser.add_argument("--check", action="store_true", help="Verify without writing")
    args = parser.parse_args()

    path = Path(args.path)
    source = path.read_text(encoding="utf-8")
    patched, changes = patch_source(source)

    if args.check:
        if patched != source:
            raise SystemExit("Generator hotfix is required but has not been applied")
        print("Generator runtime hotfix check PASSED")
        return 0

    if patched != source:
        atomic_write(path, patched)
    print(
        "Generator runtime hotfix v1.13.1.4: "
        f"html_alias_changed={changes['html_alias_changed']}, "
        f"registry_batching_changed={changes['registry_batching_changed']}, "
        f"source_changed={patched != source}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
