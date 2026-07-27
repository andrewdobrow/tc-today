# TCT v1.11.4.9.1 — Editorial Image Asset Packaging Repair

Base: **v1.11.4.9 specific-topic-image-priority**

## Purpose

Repair the v1.11.4.9 deployment overlay, which included the editorial image manifest and validation test but omitted the physical optimized image files referenced by that manifest.

The failed GitHub test correctly reported that `/images/editorial/cities/fellsmere/fellsmere-sign.webp` did not exist. The same packaging omission affected the rest of the optimized editorial library.

## Changes

- Includes all 55 optimized WebP editorial assets referenced by `data/editorial-image-library.json`.
- Preserves the existing 20-pool folder structure.
- Includes the five approved `og-*` graphics inside their topic rotations.
- Includes `images/editorial/README.md` and the canonical image manifest.
- Does not change fallback selection logic, topic priority, rotation state, article content, or `custom_articles.json`.
- Keeps the runtime engine release at v1.11.4.9 because this is a packaging-only asset repair.

## Validation

- Manifest asset check: 55 of 55 paths present.
- Optimized library size remains below 10 MB.
- Package validation: passed — 29 modules and 98 public exports.
- CI-equivalent suite: 340 passed.
- GitHub Actions and production deployment: not run in this environment after packaging.

## Apply

Apply this repository-root overlay over v1.11.4.9 and commit the added `images/editorial/**/*.webp` files.
