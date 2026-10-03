# TCT v1.13.9.79 — Bunny shadow observability refinement

Apply this delta on top of **v1.13.9.78**.

## Scope

This is a shadow-pilot refinement only. It does **not** switch article delivery to
Bunny and does not change the SHA-256 content-addressed object naming scheme.

## Changes

- Replaces the misleading manager-lifetime `elapsed` metric with cumulative
  article-image work time.
- Adds per-run timing totals for candidate handling, downloads, uploads, public
  verification, publisher revalidation, registry writes, and metadata repair.
- Adds per-image timing details to mirror report events.
- Keeps `manager_lifetime_seconds` as a separate diagnostic so it cannot be
  confused with Bunny/image-stage cost.
- Writes a shadow/mirror report even when the run has zero image candidates.
- Backfills blank `source_name` values in the existing image registry from known
  publisher article domains (including CBS12, WPTV, and WPBF), even on a
  zero-candidate run.
- New mirrors also derive a known publisher name from the source article URL when
  the render item does not already carry one.
- The generator summary now reports `metadata_repairs` and
  `image_work_elapsed`.

## Deliberately unchanged

- `TCT_ARTICLE_IMAGE_MODE` should remain `shadow` for this validation run.
- Storage object keys remain `articles/<sha-prefix>/<sha256>.<ext>`.
- No historical image backfill is introduced.
- Events remain untouched.
- Failure behavior remains publisher-URL fallback.
- No registry snapshot is bundled in this overlay, so applying the patch cannot
  overwrite a newer production `data/article-image-registry.json`.

## Validation

- Focused Bunny/image tests: 18 passed.
- Production pytest command (excluding the same two intentionally ignored suites):
  **1465 passed, 0 failed**.
- Package validator: **42 modules imported / 123 public exports verified**.
- Verified against the supplied production registry that a zero-candidate metadata
  repair resolves the three blank labels to CBS12, WPTV, and WPBF without network
  image work.
