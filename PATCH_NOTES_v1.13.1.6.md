# v1.13.1.6 — Source-Backed County Jurisdiction Authority

## Emergency correction

Retires the exact false Indian River County publication:

`2026-08-06-indian-river-county-sheriffs-deputies-shoot-kill-18-year-old-attacking-father-wi`

The article page is replaced with a noindex withdrawal notice and redirect to the Indian River County section. The preflight removes the exact slug from archive data, live data, RSS, sitemaps, homepage/category HTML, and generation cache.

## Root cause

The county filter could return a scored source pool even when it contained zero deterministic hero-eligible sources. Sports already failed over to archive recovery in that situation, but county sections still called Claude. Generated copy was then validated against its own inserted county wording rather than source-only jurisdiction evidence.

## Permanent prevention

- County sections skip Claude when Martin, St. Lucie, or Indian River has no deterministic source-backed hero candidate.
- Every generated county item is stamped with its category before validation.
- County jurisdiction is validated only against original source title, source body/summary, source URL, and feed URL.
- Generated headline and body text cannot prove their own jurisdiction.
- Explicit outside-area evidence, including Palm Beach County, fails the article-framing contract.
- Cached category output is revalidated under the same source-backed jurisdiction contract.

## Workflow failure containment

- Both workflows install the source-authority guard and retire the false publication before package validation and pytest.
- The editorial test workflow now fixes `TCT_ARTICLE_BANNER_MODE` to `reader_support`, matching the banner test contract and preventing a repository variable from making the 50-article migration a no-op.
- The retirement preflight also removes the known stale shark-video-to-policy cache entry as a second safety layer behind `sanitize_generation_cache.py`.
- The workflow version assertion remains aligned to bounded runtime v1.9.6.

## Scope

The repair is exact-slug and source-contract scoped. It does not rewrite unrelated articles, registry stories, custom articles, image overrides, or the retained Ethan Boyd canonical article.
