# TCT v1.11.8.2 — Publisher Logo Guard and Sports Fast Recovery

Base version: **v1.11.8.1**

## Incident

The Indiantown data-center article displayed the reporting publisher's logo as its story image. The image pipeline already contained URL patterns for publisher branding and TownNews custom assets, but those patterns were not enforced when accepting RSS images, Open Graph images, cached category output, or archive image restoration.

The affected Martin County category was also being reused from the incremental category cache, allowing the previously accepted logo URL to persist after the original generation run.

## Publisher-logo protection

This release adds one deterministic source-image quality contract across all image paths:

1. RSS and media-enclosure image extraction.
2. Generated hero source images.
3. `og:image` and `twitter:image` fallback discovery.
4. Incremental category-cache reuse.
5. Live category placements before archive restoration.
6. Archive source-image restoration.

The guard rejects:

- TownNews `/content/tncms/custom/` branding assets.
- URL tokens such as `logo`, `masthead`, `wordmark`, `favicon`, and station/publisher logo variants.
- Open Graph image-alt metadata identifying a logo or masthead.
- Declared social images that are undersized or have extreme logo-like aspect ratios.
- Existing default-image, news-slate, station-branding, and tracking placeholders.

The TownNews domain itself is **not** blocked. Normal TownNews editorial assets under `/content/tncms/assets/.../editorial/` remain eligible.

When a cached or archived logo is rejected, the image is cleared before restoration and the normal TCT editorial fallback system supplies a relevant local image. Cached category data is rewritten without the rejected URL so the same logo is not reconsidered on every run. A production archive migration also replaces the rejected URL in `archive.json` and rewrites the already-published article HTML, so the affected page is repaired even when it is not selected live on the next run.

## Open Graph fallback behavior

`fetch_og_image()` no longer returns the first social image blindly. It evaluates each Open Graph and Twitter candidate independently. A publisher logo in `og:image` can be skipped while a valid story-specific `twitter:image` is accepted.

## Sports zero-candidate fast recovery

After source-depth and category filtering, Sports now checks whether the selected source pool contains any deterministic athletic hero candidate.

When none exists, the engine:

- Skips incremental category generation and both Claude attempts.
- Requests verified permanent archive recovery immediately.
- Records status `sports_zero_candidate_archive_recovery`.
- Records failure code `no_sports_hero_candidates`.

This preserves the v1.11.8.0 Sports relevance contract while avoiding approximately one to two minutes of unnecessary model work on clearly non-sports pools.

## Observability

A successful run writes:

`data/source-image-quality-report.json`

The report includes rejection counts by reason and stage plus the rejected URL, headline, and source URL. The production log prints:

`Source-image quality: N publisher logo/placeholder candidate(s) rejected`

The Sports fast path prints:

`Sports fast recovery: no deterministic hero candidate; skipping Claude and using verified archive recovery`

## Regression coverage

Permanent tests cover:

- The exact TownNews custom-asset pattern used by Hometown News branding.
- A normal TownNews editorial photo remaining eligible.
- Open Graph logo rejection with valid Twitter-image fallback.
- Cached category logo removal.
- Archive restoration refusing to revive the logo.
- A non-sports Sports pool triggering fast recovery.
- A Conner Ware/St. Lucie Mets story preventing fast recovery.
- Non-Sports categories remaining unaffected.

## Validation

- Focused source-image and Sports regressions: **33 passed**.
- Workflow-equivalent suite: **382 passed**.
- Existing warnings: **17** `datetime.utcnow()` deprecation warnings.
- No custom queue, archive, registry, generated article page, or production data is included in the overlay.
