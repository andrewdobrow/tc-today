# TCT v1.11.6.1 — Category Generation Failure Containment

## Purpose

This release hardens the model-driven category generation stage before several normal production observation runs. It does not activate follow-up grouping, homepage ranking, or any new publication behavior.

The triggering production failure was Indian River County generation returning non-JSON on the first attempt and a response with `"hero": null` on the retry. The old source-attachment path dereferenced the null hero, printed a full traceback, and only then fell through to archive recovery.

## Changes

### Null-hero protection

- `generate_category_content()` now treats a null hero or null card as an empty object.
- Source attachment never calls `.get()` on `None`.
- A response without a usable hero becomes a controlled category failure and uses permanent archive recovery.

### Bounded model attempts

Category article generation now has an explicit, configurable budget:

- Model-call timeout: **120 seconds** by default.
- Combined category generation budget: **180 seconds** by default.
- Maximum attempts: **2**.
- Minimum remaining retry window: **15 seconds**.
- Anthropic SDK hidden retries are disabled for these calls; the engine owns the visible retry policy.

Environment overrides:

```text
TCT_CATEGORY_MODEL_CALL_TIMEOUT_SECONDS
TCT_CATEGORY_GENERATION_BUDGET_SECONDS
```

### Structured failure reporting

A new report is written to:

```text
data/category-generation-report.json
```

It records, per category:

- source candidate counts;
- fresh and publishable counts;
- selected source count;
- cache hit status;
- model attempt count and duration;
- timeout assigned to each attempt;
- failure code and concise summary;
- total category duration;
- whether permanent archive recovery was requested;
- final live hero when generation succeeded.

The same report is embedded under `category_generation` in:

```text
data/editorial_observability.json
```

Expected failure codes include:

- `invalid_json`
- `missing_or_null_hero`
- `model_timeout`
- `generation_budget_exhausted`
- `generation_exception`
- `publication_quality_rejected`

### Cleaner production logs

Persistent category failures now produce one concise line such as:

```text
Category generation contained for Indian River County: missing_or_null_hero (...); using archive recovery
```

The pipeline no longer prints a full traceback for this controlled failure class.

### Dead-feed cleanup

Removed the two known 404 WPTV content-bank endpoints:

```text
https://www.wptv.com/feeds/rss/news
https://www.wptv.com/feeds/rss/local
```

Current working WPTV feeds and all category feeds remain unchanged.

## Safety boundaries

This release does not change:

- story relationship decisions;
- follow-up activation;
- duplicate suppression rules;
- homepage ranking behavior;
- hero eligibility rules;
- canonical URLs or GUIDs;
- custom article identity;
- RSS publication identity;
- product-guide content or presentation.

Archive recovery remains the fail-closed response when a category cannot generate usable current content.

## Validation

- Focused category failure-containment tests: **7 passed**.
- Full workflow-equivalent suite: **372 passed** after adding the new regressions.
- Package validation: **29 modules and 98 public exports**.
- Existing `datetime.utcnow()` deprecation warnings remain unrelated to this patch.

GitHub Actions and production have not been run with v1.11.6.1 at package creation time.
