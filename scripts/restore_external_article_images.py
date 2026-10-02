#!/usr/bin/env python3
"""Restore mirrored TCT article images to their recorded publisher URLs.

This is an emergency recovery tool. It never contacts Bunny and relies only on the
version-controlled article-image registry. By default it is a dry run; pass --apply
to write changes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "data" / "article-image-registry.json"


def load_registry(path: Path = REGISTRY) -> dict:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def slug_mapping(registry: dict) -> dict[str, tuple[str, str]]:
    result = {}
    for slug, row in (registry.get("articles") or {}).items():
        if not isinstance(row, dict):
            continue
        current = row.get("current_image") if isinstance(row.get("current_image"), dict) else {}
        hosted = str(current.get("public_url") or "").strip()
        original = str(current.get("original_url") or "").strip()
        if hosted and original:
            result[str(slug)] = (hosted, original)
    return result


def replace_article_pages(root: Path, mapping: dict, *, apply: bool) -> int:
    changed = 0
    for slug, (hosted, original) in mapping.items():
        path = root / "articles" / f"{slug}.html"
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        updated = text.replace(hosted, original)
        if updated != text:
            changed += 1
            if apply:
                path.write_text(updated, encoding="utf-8")
    return changed


def _replace_json_node(node, mapping: dict, *, inherited_slug: str = "") -> int:
    changed = 0
    if isinstance(node, dict):
        slug = str(
            node.get("slug") or node.get("canonical_slug") or node.get("_archived_slug") or inherited_slug or ""
        ).strip()
        pair = mapping.get(slug)
        for key, value in list(node.items()):
            # Keep mirror provenance so the operation is reversible and auditable.
            if key in {"hosted_image_url", "image_storage_key", "image_sha256", "image_storage_provider"}:
                continue
            if isinstance(value, str) and pair and value == pair[0]:
                node[key] = pair[1]
                changed += 1
            elif isinstance(value, (dict, list)):
                changed += _replace_json_node(value, mapping, inherited_slug=slug)
    elif isinstance(node, list):
        for value in node:
            changed += _replace_json_node(value, mapping, inherited_slug=inherited_slug)
    return changed


def replace_json_surface(path: Path, mapping: dict, *, apply: bool) -> int:
    if not path.is_file():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    changed = _replace_json_node(payload, mapping)
    if changed and apply:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return changed


def replace_feed(root: Path, mapping: dict, *, apply: bool) -> int:
    path = root / "feed.xml"
    if not path.is_file():
        return 0
    text = path.read_text(encoding="utf-8", errors="ignore")
    updated = text
    # RSS items carry canonical article GUIDs, but an exact URL replacement is safe
    # here because identical mirrored bytes are visually equivalent in an emergency.
    # Prefer the first publisher URL recorded for each public mirror.
    seen = {}
    for _slug, (hosted, original) in mapping.items():
        seen.setdefault(hosted, original)
    for hosted, original in seen.items():
        updated = updated.replace(hosted, original)
    if updated == text:
        return 0
    if apply:
        path.write_text(updated, encoding="utf-8")
    return 1


def replace_html_surfaces(root: Path, mapping: dict, *, apply: bool) -> int:
    """Restore non-article HTML surfaces using unambiguous mirror mappings only."""
    public_to_originals = {}
    for _slug, (hosted, original) in mapping.items():
        public_to_originals.setdefault(hosted, set()).add(original)
    safe = {hosted: next(iter(values)) for hosted, values in public_to_originals.items() if len(values) == 1}
    changed = 0
    article_dir = (root / "articles").resolve()
    for path in root.rglob("*.html"):
        try:
            if path.resolve().parent == article_dir:
                continue
        except Exception:
            pass
        text = path.read_text(encoding="utf-8", errors="ignore")
        updated = text
        for hosted, original in safe.items():
            updated = updated.replace(hosted, original)
        if updated != text:
            changed += 1
            if apply:
                path.write_text(updated, encoding="utf-8")
    return changed


def restore(root: Path = ROOT, *, apply: bool = False) -> dict:
    registry = load_registry(root / "data" / "article-image-registry.json")
    mapping = slug_mapping(registry)
    report = {
        "mode": "apply" if apply else "dry-run",
        "registered_articles": len(mapping),
        "article_pages_changed": replace_article_pages(root, mapping, apply=apply),
        "archive_fields_changed": replace_json_surface(root / "archive.json", mapping, apply=apply),
        "data_fields_changed": replace_json_surface(root / "data.json", mapping, apply=apply),
        "feed_changed": replace_feed(root, mapping, apply=apply),
        "other_html_pages_changed": replace_html_surfaces(root, mapping, apply=apply),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write the restoration; default is dry-run")
    args = parser.parse_args()
    report = restore(ROOT, apply=args.apply)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
