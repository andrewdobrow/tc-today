#!/usr/bin/env python3
"""Remove public photo-credit presentation from generated and legacy TCT pages.

Image origins and source URLs stay in internal archive/provenance fields. The
article's visible source citations and reporting attribution are not modified.
Run after all HTML generators and editorial repair passes, including deploy-only.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# A credit caption is not an ordinary descriptive image caption. Match any
# figcaption whose class contains img-credit or photo-credit.
CREDIT_FIGCAPTION = re.compile(
    r'\s*<figcaption\b'
    r'(?=[^>]*\bclass\s*=\s*["\'][^"\']*(?:img-credit|photo-credit)[^"\']*["\'])'
    r'[^>]*>.*?</figcaption>',
    flags=re.IGNORECASE | re.DOTALL,
)

# Contributor portraits can contain a descriptive caption followed by a
# separate photo credit. Preserve the descriptive caption.
PORTRAIT_PHOTO_SMALL = re.compile(
    r'\s*<small>\s*Photo:\s*.*?</small>',
    flags=re.IGNORECASE | re.DOTALL,
)

# Some optional image galleries present attribution as the entire caption.
# Do not remove genuine descriptive captions about what the image depicts.
CAPTION_ONLY_CREDIT = re.compile(
    r'\s*<div\b'
    r'(?=[^>]*\bclass\s*=\s*["\'][^"\']*article-carousel-caption[^"\']*["\'])'
    r'[^>]*>\s*(?:Photo|Image)\s*(?:credit)?\s*:\s*[^<]*</div>',
    flags=re.IGNORECASE,
)


def remove_photo_credits(markup: str) -> str:
    result = CREDIT_FIGCAPTION.sub("", markup)
    result = PORTRAIT_PHOTO_SMALL.sub("", result)
    result = CAPTION_ONLY_CREDIT.sub("", result)
    return result


def public_pages(root: Path):
    # Only shipped HTML, not test fixtures, documentation or development tools.
    yield from root.glob("*.html")
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        if folder.name in {"tests", "scripts", "tct_engine", "docs", "node_modules", "venv", ".venv"}:
            continue
        yield from folder.rglob("*.html")


def clean(root: Path = ROOT, *, check: bool = False) -> tuple[int, int]:
    examined = 0
    changed = 0
    for path in public_pages(root):
        examined += 1
        original = path.read_text(encoding="utf-8")
        cleaned = remove_photo_credits(original)
        if cleaned == original:
            continue
        changed += 1
        if not check:
            path.write_text(cleaned, encoding="utf-8")
    if check and changed:
        raise SystemExit(f"Public photo credits still present on {changed} HTML page(s)")
    print(f"Public photo-credit cleanup: checked {examined} page(s), updated {changed}")
    return examined, changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if credits remain")
    options = parser.parse_args()
    clean(check=options.check)
