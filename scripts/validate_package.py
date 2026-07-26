#!/usr/bin/env python3
"""Validate that the TCT editorial package is complete and importable."""

from __future__ import annotations

import importlib
import json
import pkgutil
import re
import sys
from pathlib import Path


def validate_custom_queue(path: Path) -> list[str]:
    """Return actionable errors for the authoritative custom publication queue."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [
            "custom_articles.json invalid JSON at "
            f"line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ]
    except OSError as exc:
        return [f"custom_articles.json could not be read: {exc}"]

    if not isinstance(data, list):
        return ["custom_articles.json must contain a top-level JSON array"]

    errors: list[str] = []
    headlines: set[str] = set()
    slugs: dict[str, str] = {}
    for index, item in enumerate(data, start=1):
        label = f"custom_articles.json item {index}"
        if not isinstance(item, dict):
            errors.append(f"{label} must be a JSON object")
            continue
        headline = str(item.get("headline") or "").strip()
        if not headline:
            errors.append(f"{label} is missing a non-empty headline")
            continue
        if headline in headlines:
            errors.append(f"{label} duplicates exact headline: {headline}")
        headlines.add(headline)
        requested_slug = re.sub(
            r"[^a-z0-9]+", "-", str(item.get("slug") or "").strip().lower()
        ).strip("-")
        if requested_slug:
            prior_headline = slugs.get(requested_slug)
            if prior_headline and prior_headline != headline:
                errors.append(
                    f"{label} ('{headline}') reuses slug '{requested_slug}' "
                    f"already assigned to '{prior_headline}'"
                )
            slugs[requested_slug] = headline
        if item.get("retired") is True:
            continue
        if not str(item.get("category") or "").strip():
            errors.append(f"{label} ('{headline}') is missing a category")
        if str(item.get("article_type") or "") == "product_guide":
            if not str(item.get("intro") or "").strip():
                errors.append(f"{label} ('{headline}') is missing product-guide intro")
            if not isinstance(item.get("products"), list) or not item.get("products"):
                errors.append(f"{label} ('{headline}') requires a non-empty products array")
        elif not str(item.get("body") or "").strip():
            errors.append(f"{label} ('{headline}') is missing a non-empty body")
    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    errors: list[str] = []

    try:
        package = importlib.import_module("tct_engine")
    except Exception as exc:  # pragma: no cover - fatal bootstrap failure
        print(f"Package validation failed: cannot import tct_engine: {exc}", file=sys.stderr)
        return 1

    discovered = sorted(
        module.name
        for module in pkgutil.walk_packages(
            package.__path__, prefix=f"{package.__name__}."
        )
    )

    for module_name in discovered:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            errors.append(f"{module_name}: {type(exc).__name__}: {exc}")

    for export_name in getattr(package, "__all__", []):
        if not hasattr(package, export_name):
            errors.append(f"tct_engine.__all__ export is missing: {export_name}")

    required_files = [
        repo_root / "tct_engine" / "editorial_proximity.py",
        repo_root / "tct_engine" / "observability.py",
        repo_root / "scripts" / "generate.py",
    ]
    for path in required_files:
        if not path.is_file():
            errors.append(f"required file is missing: {path.relative_to(repo_root)}")

    errors.extend(validate_custom_queue(repo_root / "custom_articles.json"))

    if errors:
        print("Package validation failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print(
        "Package validation passed: "
        f"{len(discovered)} modules imported and "
        f"{len(getattr(package, '__all__', []))} public exports verified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
