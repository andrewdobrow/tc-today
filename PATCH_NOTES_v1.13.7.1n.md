# v1.13.7.1n — Persistent Story Registry History Compaction

## Production failure addressed

The Generate News workflow reached the repository-size safety check and failed because:

```text
Generated repository contains file(s) above the 90 MiB safety ceiling:
./data/story-registry.json
```

The safety ceiling is not changed or weakened.

## Observed storage defect

`data/story-registry.json` had grown to approximately 90 MiB even though its durable identity population was modest. The dominant growth was repeated no-op history receipts:

- `revision_history`: 83,836 entries
- `confidence_history`: 220,157 entries

The persistent merge logic treated a new `run_id` / monotonically increasing `revision` as a new revision even when the story's actual editorial state was unchanged. Attachment-confidence receipts were also appended again on ordinary runs when the article's confidence, matched prior slug, and attachment basis had not changed.

This made the registry grow on every Generate News run without adding new editorial information.

## Repair

The persistent story registry now stores history as **semantic state transitions**, not per-run duplicate observations.

### Revision history

A revision transition is defined by changes to:

- `article_count`
- `latest_stage`
- `latest_date`
- `canonical_slug`

Repeated runs with the same state do not append another revision-history receipt. A later transition back to an earlier state remains represented because only consecutive no-op observations are collapsed.

### Attachment-confidence history

Confidence history is compacted independently per article slug. A new receipt is retained only when one of these changes:

- `confidence`
- `matched_prior_slug`
- `attachment_basis`

A true A → B → A transition is retained. Repeated A → A observations across ordinary runs are not.

### Inactive stories

Previously preserved/inactive stories are compacted too, so stale histories cannot remain as a hidden source of registry growth.

## Current registry repair included

The overlay includes a compacted `data/story-registry.json` generated from the current committed registry state.

Identity-bearing state is unchanged:

- stories: **932 → 932**
- `article_to_story` memberships: **1,037 → 1,037**
- revision history: **83,836 → 981**
- confidence history: **220,157 → 1,446**
- serialized registry size: **~89.8 MiB → ~3.60 MiB**

A deterministic identity projection covering story IDs, canonical slugs/headlines, timelines, articles, aliases, historical slugs, retired IDs, and article-to-story membership was byte-normalized and SHA-256 compared before/after compaction. It was unchanged.

## Observability

Generate News now logs:

```text
Persistent story registry history compacted: revisions N -> M; confidence X -> Y
Persistent story registry size after compaction: Z.ZZ MiB
```

The existing 90 MiB repository safety check remains authoritative.

## Tests

Added `tests/test_story_registry_history_compaction.py` covering:

- no-op revision collapse
- real revision transition preservation
- per-slug confidence-state transition preservation
- A → B → A confidence reversion preservation
- no new history on an unchanged merge
- compaction of preserved inactive stories

Validation on the patched tree:

- focused registry/runtime/timeline tests: **14 passed**
- exact Test Editorial Engine command: **1,100 passed, 0 failed**
- package validation: **38 modules imported / 122 public exports verified**
- repository >90 MiB safety scan: **no oversized files**

## Apply

Apply v1.13.7.1n over v1.13.7.1m, then run Test Editorial Engine. If green, run one Generate News.
