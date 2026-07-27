# TCT v1.11.6.2 — Homepage Permalink Uniqueness

## Production defect

The homepage all-news grid could render the same article more than once when one
canonical story was intentionally placed in multiple editorial categories. The live
example showed:

- the St. Lucie County internship article under both Local Government and St. Lucie County;
- the Martin County boat-GPS arrest article under both Crime & Safety and Martin County.

Category cross-posting is valid. Repeating the same article URL on the front page is not.

## Root cause

`global_rank()` returned a model-ranked, semantically deduplicated subset. The renderer
then rebuilt the display list as:

```python
topnews + every input object not present in topnews by Python object identity
```

A county cross-post is a copied dictionary with a different in-memory identity even
when it resolves to the same archived slug and permalink. Therefore the copy removed by
semantic ranking was appended back into the live grid. The observe-only ranking report
recognized these duplicate placements, but intentionally did not mutate rendered HTML.

## Fix

The front-page card list now receives a deterministic canonical-permalink pass after
ranking, pin placement, archive reconciliation and permalink resolution.

- One visible homepage placement is kept for each normalized article permalink.
- Query strings, fragments, relative links and absolute TCT links collapse to the same identity.
- A card resolving to the visible front-page hero permalink is removed.
- Pinned placements win their permalink group.
- Authoritative custom placements win over syndicated copies.
- A model-ranked placement wins over an appended cross-category fallback copy.
- Category and county section surfaces remain unchanged and may still cross-post the story.

The advertising support card is now inserted after four cards that actually render,
rather than after the fifth raw list position.

## New diagnostics and fail-closed contract

Each production run writes:

```text
data/homepage-permalink-dedupe.json
```

It records the input count, unique permalink count and every removed duplicate placement,
including the kept and removed category labels.

After HTML rendering, the engine writes:

```text
data/homepage-permalink-contract.json
```

The contract checks the visible all-news hero and every visible news grid card. A repeated
article permalink now stops deployment instead of reaching production.

Expected log lines:

```text
Homepage permalink dedupe removed N duplicate card placement(s)
Homepage permalink uniqueness PASSED (N visible article link(s))
```

## Scope boundary

This release does not change:

- category-page placement;
- story relationships or follow-up detection;
- ranking enforcement;
- duplicate-suppression activation;
- archive identity or canonical redirects;
- RSS GUIDs or publication dates;
- category generation or Anthropic API behavior;
- custom-article publication behavior.

`tests/test_custom_authority_contract.py` was synchronized with the already-authoritative
v1.11.3.1 active-custom-retention behavior. That test-only correction does not change
runtime behavior.

## Validation

- Exact screenshot regression: two cross-category pairs collapse from four cards to two.
- Focused homepage/ranking/permalink tests: 24 passed.
- Full workflow-equivalent suite: 344 passed.
- Package validation: 29 modules and 98 public exports.
- Existing warnings: 15 `datetime.utcnow()` deprecation warnings.

GitHub Actions and production were not run with v1.11.6.2 at package creation time.
