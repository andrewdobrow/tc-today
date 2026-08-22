# v1.13.6.6 Assignment Editor Shadow — Production Review Guide

## Run

Open **Update Treasure Coast Today → Run workflow**.

- Leave **Run Sonnet 5 shadow model bake-off** unchecked.
- Check **Run Sonnet 5 assignment editor + Sonnet 4.5 writer shadow**.
- Run the normal production workflow.

The live site continues to publish through the existing Sonnet 4.5 production path.

## Expected Generate News log

Near the end, after normal production timing, expect:

```text
Assignment-editor shadow: N live-generated category packet(s) queued; editor=claude-sonnet-5; writer=claude-sonnet-4-5
    <Category>: editor X.Xs + N writer call(s) X.Xs
Assignment-editor shadow complete: N scoreable, 0 shadow failure(s). Review data/assignment-editor-shadow-review.md before opening the answer key.
```

Only categories that actually ran fresh live category generation are queued. Cache-hit/archive-recovery categories will not be manufactured solely for the experiment.

A shadow failure must say `live publication unaffected` and must not turn the production workflow red by itself.

## Artifact

The workflow uploads `tct-assignment-editor-shadow-<run-id>` containing:

1. `assignment-editor-shadow-review.md`
2. `assignment-editor-shadow-answer-key.json`
3. `assignment-editor-shadow-report.json`
4. `model-usage-report.json`

## Blind scoring order

Open **only** `assignment-editor-shadow-review.md` first.

Score each category on:

- hero/story choice;
- supporting-story selection and omissions;
- story ordering;
- angle/new-development focus;
- exact source mapping;
- headline;
- lead/context;
- factual fidelity;
- completeness;
- least filler;
- overall publishability.

Only after recording A/B/Tie should you open the answer key.

## Machine-report checks

For every scoreable category:

- `assignment_diagnostics.valid_hero` should be `true`;
- `assignment_diagnostics.source_mapping_valid` should be `true`;
- `invalid_source_indexes` should be empty;
- `duplicate_source_indexes` should be empty;
- every challenger story should map to exactly one source from the displayed pool.

`omitted_source_indexes` is informational, not automatically an error: the assignment editor is allowed to omit weak or redundant stories rather than fill space.

## Model-usage checks

`model-usage-report.json` should separately show:

- `assignment_editor_shadow` calls on `claude-sonnet-5`;
- `assignment_writer_shadow` calls on `claude-sonnet-4-5-...`;
- normal production workloads still on the existing production model;
- zero unexpected failures without usage metadata.

## Files to send back for review

Upload:

- `assignment-editor-shadow-review.md`
- `assignment-editor-shadow-answer-key.json`
- `assignment-editor-shadow-report.json`
- `model-usage-report.json`

The review should be scored blind before model/path identities are revealed.
