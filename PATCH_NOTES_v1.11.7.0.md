# TCT v1.11.7.0 — Trusted Source and County Membership Recovery

## Incident repaired

Two related production gaps could strip legitimate county coverage:

1. A trusted local article discovered through Google News remained a thin aggregator item when the expected publisher county feed did not carry it. The 80-word source-depth gate then correctly rejected it, but the engine made no attempt to recover the full publisher page.
2. Canonical archive rows stored only one `category_key`. When one story belonged to both a topic and a county, publication coalescing retained the primary topic and discarded the county membership. Homepage permalink deduplication then kept one correct URL but could no longer expose that card under every relevant category filter.

The exact regressions covered are:

- WPTV: `Indian River County firefighter/paramedic dies following off-duty personal tragedy`
- TCT: `Private racetrack resort community breaks ground in St. Lucie County on 650 acres`

## Trusted publisher recovery

For locally relevant Google News discoveries from an allowlisted publisher, the engine now:

1. Resolves the modern Google News wrapper through Google's bounded batchexecute flow.
2. Verifies that the resolved domain belongs to the expected trusted publisher.
3. Fetches the publisher article through the existing extraction cache.
4. Re-runs the unchanged source-depth contract.
5. Promotes the source to `full` or `summary` only when at least 80 verified words are recovered.
6. Keeps reported deaths eligible when they merely mention surviving relatives; obituary suppression now requires funeral-listing structure rather than the phrase `survived by` alone.

Allowlisted publishers include WPTV, WPBF, WPEC/CBS12/CW34, WFLX, Sebastian Daily and Hometown News.

This does **not** weaken the source-depth gate and does not write from a Google News snippet.

New report:

```text
data/trusted-source-recovery.json
```

It records publisher, wrapper URL, resolved URL, locality confirmation, source word count and recovery result.

## Durable multi-category membership

Each canonical archive row now retains:

```json
{
  "category_key": "business",
  "category_keys": ["business", "st_lucie"],
  "county_keys": ["st_lucie"]
}
```

`category_key` remains the primary editorial label and article-page category. `category_keys` contains every valid placement membership.

Membership is preserved or projected through:

- same-story publication coalescing;
- existing archive updates;
- deterministic archive backfill;
- recent homepage archive backfill;
- homepage permalink deduplication;
- category filters;
- county panels;
- permanent county archive recovery;
- category-specific “More Stories” lists.

The homepage still renders one card per canonical permalink. That one card now carries a `data-cats` membership list and can appear under each relevant filter without duplication.

New fail-closed report:

```text
data/category-membership-report.json
```

The production run stops if a clear deterministic county locality is not projected into the archive row's memberships.

## Safety boundary

Unchanged:

- canonical permalink identity;
- primary article category and label;
- source-depth minimum;
- story relationships and follow-up activation;
- ranking enforcement mode;
- duplicate suppression;
- custom article authority;
- RSS GUID behavior;
- hero eligibility and nonstory protection.

## Validation

- Focused trusted-source, obituary-safety and category-membership tests: 15 passed.
- Workflow-equivalent suite: 351 passed.
- Package validation: 29 modules and 98 public exports.
- Exact P1 archive replay produced `category_keys: ["business", "st_lucie"]`.
- Existing archive replay: 610 records checked, 0 missing deterministic county memberships after backfill.
- No GitHub Actions or production workflow has run with v1.11.7.0.
