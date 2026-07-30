# Story-Aware Update Context Review Guide — v1.12.0.4

## Production acceptance

Confirm the run log reports one or more lines like:

```text
Story-aware update context: attached N canonical baseline(s) before generation
```

Review `data/category-generation-report.json`:

- `summary.story_aware_update_context_count` should reflect sources matched to an
  existing TCT canonical before generation.
- Each category may include `story_aware_update_context_bindings` with the source
  headline, canonical slug, canonical headline and identity basis.

## Lead requirements

For every in-place story update, remove the headline and read only the first paragraph.
It must answer:

1. What originally happened?
2. What is new in this report?
3. How are the two connected?

A quote, neighbor reaction, scene description, investigative detail or official
statement cannot appear as the only lead context.

## Silverstream Circle regression

A passing lead should resemble:

> After a 3-month-old Fort Pierce boy died from dehydration and malnutrition and
> three caregivers were arrested, a Silverstream Circle neighbor said residents
> had worried about the child before the case became public.

The exact wording is not required. The original death and the new neighbor reaction
are both required.

## Fail-closed behavior

When the proposed replacement does not pass:

```text
UPDATE CONTEXT HOLD: preserved canonical page '<slug>' because the replacement lead did not stand alone
```

The canonical article must remain unchanged, and no new permalink may be created.
