# Review Guide — v1.12.2.3 Semantic Registry Consolidation

Apply this overlay on top of v1.12.2.2 and run the production workflow once.

## Expected workflow line

The semantic summary should include registry merges, for example:

```text
Semantic publication gate: 0 candidate pair(s), 0 conflict override(s), 0 model call(s), 0 retroactive redirect(s), 5 registry merge(s), 0 hold(s)
```

The candidate and redirect counts may differ if new stories arrive during the run. The important first-run expectation is that the five decisions from the prior report are replayed into the registry.

## Required reports

Review:

- `data/semantic-publication-gate.json`
- `data/editorial_story_registry.json`
- `data/editorial_observability.json`
- `data/story-regression-report.json`
- the complete workflow log

## Required checks

In `semantic-publication-gate.json` confirm:

- `registry_consolidation.status` is `consolidated`;
- `registry_consolidation.story_records_merged` is expected to be 5 on the first run over the supplied production state;
- `registry_consolidation.skipped` is empty;
- the merge list includes the two Port St. Lucie pairs.

In `editorial_story_registry.json` confirm:

- `story_001684` is absent from `stories`;
- `story_aliases.story_001684` equals `story_001557`;
- `story_001685` is absent from `stories`;
- `story_aliases.story_001685` equals `story_001316`;
- source URLs and timeline entries from each retired record appear on its canonical story;
- event keys formerly mapped to retired records now point to the canonical story IDs.

On a second unchanged run, the merge count should be zero or the directives should report as already consolidated; the retired story records must not reappear.
