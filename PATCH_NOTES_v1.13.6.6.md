# TCT v1.13.6.6 — Assignment Editor Shadow Experiment

## Purpose

The two clean Sonnet 4.5 vs. Sonnet 5 bake-offs finished 3–3 across valid categories, but the wins suggested a role-specific pattern: Sonnet 5 often showed stronger assignment/section judgment while Sonnet 4.5 often produced tighter straight-news copy. This release tests that architecture directly instead of running another all-in-one model comparison.

## Production safety

**Live publication behavior is unchanged.** Sonnet 4.5 remains the production category model. The shadow experiment is manual-only and runs after the normal site build, caches, publication contracts, identity gates, observability, and static writes have already completed.

The shadow path cannot write to `all_categories`, the archive, generation cache, story registry, RSS, article pages, homepage selection, or any other live publication state. Any editor/writer failure is contained and the production run remains unaffected.

## Shadow architecture

When the new workflow checkbox is enabled:

1. A copy of each successfully live-generated category source packet is queued in memory.
2. **Sonnet 5 acts only as assignment editor.** It chooses the hero, supporting-story order, a concise angle/new-development focus, urgency, and exact `source_index` values.
3. Deterministic validation rejects missing heroes, out-of-range source indexes, and duplicate source assignments.
4. **Sonnet 4.5 acts only as writer.** Each writer call receives exactly one preassigned source plus the editor's angle. It cannot see competing sources and cannot alter the source index, urgency, or published timestamp.
5. Blind A/B artifacts compare the current production output against the editor→writer shadow result.

The assignment editor is explicitly prohibited from writing publication prose. The writer is explicitly prohibited from choosing, combining, or substituting stories.

## New artifacts

- `data/assignment-editor-shadow-report.json`
- `data/assignment-editor-shadow-review.md`
- `data/assignment-editor-shadow-answer-key.json`
- `data/model-usage-report.json` (existing telemetry, now with separate shadow workload classes)

The machine report records source-selection diagnostics including selected/omitted indexes, duplicate-index detection, invalid-index detection, exact mapping validity, hero agreement, and baseline vs. challenger source sets.

The blind review adds scoring for supporting-story selection/omissions, story order, angle/new-development focus, and source mapping in addition to prose quality.

## Model usage telemetry

New workload classes:

- `assignment_editor_shadow` — Sonnet 5 editorial assignment calls
- `assignment_writer_shadow` — Sonnet 4.5 single-source writing calls

No prompt or source text is stored in model-usage telemetry.

## Workflow

A new manual checkbox appears in **Update Treasure Coast Today**:

`Run Sonnet 5 assignment editor + Sonnet 4.5 writer shadow`

Routine production runs default to off. The original `Run Sonnet 5 shadow model bake-off` checkbox is retained separately.

For this experiment, enable the new assignment-editor checkbox and leave the old all-in-one bake-off checkbox off.

## Validation

- Focused assignment/editor/model/semantic tests: **46 passed**
- Workflow-equivalent suite: **929 passed**
- Existing warnings: **43** (`datetime.utcnow()` deprecations; unchanged)
- Package validation: **38 modules / 119 public exports**
- Generator runtime guard: **PASS**
- False-jurisdiction source guard: **PASS**
