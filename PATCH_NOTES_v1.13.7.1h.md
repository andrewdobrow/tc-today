# TCT v1.13.7.1h — Validated Material Update Quality Repair + No-Silent-Loss Authority

## Production incident

The September 1, 2026 production run after v1.13.7.1g still failed to publish the Michael Anthony Debevec body-recovery development.

The new run changed the failure mode. The WPTV update survived source ingestion, material-update promotion, duplicate suppression, source-depth filtering, category eligibility, and model selection. In Martin County the generator had five publishable sources and produced two Debevec body-recovery cards. Those two generated cards were then removed by prose-quality guards:

- `original_event_context_missing`
- `headline_jurisdiction_missing_from_lead`

The remaining I-95 crash became the Martin County hero. By the time forward publication ran, the Debevec update no longer existed as a live generated placement, so the semantic publication gate had no candidate to commit.

This release treats that observed failure as a pipeline handoff defect. It does **not** weaken the underlying quality rules and does **not** add a Debevec/body-found special case.

## What changes

### 1. Carry validated material-update authority into generated copy before prose guards

When the live writer selects a source that already has all of the following:

- validated semantic materiality,
- `update_existing_canonical`,
- `same_real_world_event=true`,
- `material_new_update=true`,
- an exact selected canonical slug, and
- target-bound canonical write authorization,

the generated hero/card now receives that narrow current-run authority immediately when its `source_index` is attached.

Previously, most of that authority was restored only later during forward identity stamping. The prose-quality guards ran before that restoration and therefore treated a major canonical update as an ordinary disposable generated card.

### 2. Repairable quality failures queue grounded recomposition instead of deleting the update

A target-bound validated material update that fails a **repairable** update-lead or article-framing rule is retained and marked for semantic canonical recomposition.

This applies at both quality-check layers:

- immediately after generation; and
- the repeated checks after card/hero enrichment.

The release also prevents the final article-depth gate from discarding that protected item solely for temporary thinness while it is awaiting recomposition.

The following dangerous failures remain fail-closed and are **not** bypassed:

- generated copy drifted from the verified source focus;
- generated jurisdiction is unsupported by the source; or
- source jurisdiction conflicts with the generated county.

### 3. Recompose from publisher reporting + canonical context

At the existing published-story write barrier, a protected quality-held material update is rebuilt from:

- the original publisher article text/summary,
- the original publisher headline,
- the existing canonical TCT article context, and
- the already validated semantic material-update decision.

The repaired article must pass semantic composition validation and the universal article-framing contract before it can replace the canonical page.

The material-update composer contract is also tightened: any specific city, county, or monetary claim used in the refreshed headline must be explicitly present in the first paragraph.

If recomposition cannot validate, the update remains fail-closed rather than publishing malformed copy.

### 4. Selected material updates may no longer disappear behind a green workflow

The live run now records canonical targets for validated material-update sources actually selected by the category writer.

After `write_archives()` completes, `data/material-update-publication-invariant.json` verifies that every such selected target appears in the committed `material_updates` records in `data/semantic-publication-gate.json`.

If a selected validated material update disappears anywhere between writer selection and canonical commit, Generate News now raises:

`MATERIAL UPDATE PUBLICATION INVARIANT FAILED`

This converts the previous silent editorial failure into an explicit failed workflow. Broad-feed source promotions that were never selected by the live writer do not trigger the invariant.

## Regression coverage

New production-class regressions verify that:

1. the Debevec body-recovery source carries its exact target-bound authority into generated copy before quality guards;
2. a context-poor Debevec generated card is retained for repair instead of silently discarded;
3. a quality-held Debevec placement is semantically recomposed and survives the published-story suppression barrier;
4. a selected validated material update that disappears causes the terminal publication invariant to fail;
5. a committed canonical material update satisfies the invariant;
6. a context-poor Debevec hero survives both generation-time prose guards pending recomposition;
7. temporary article thinness cannot delete a protected update before its recomposition barrier; and
8. dangerous jurisdiction failures are still rejected rather than bypassed.

## Validation

Production-equivalent Test Editorial Engine suite:

- **1,080 passed**
- **0 failed**
- 44 existing deprecation warnings

Focused published-story/material-update suppression suite:

- **36 passed**
- **0 failed**

Package validation:

- **passed**
- 38 modules imported
- 122 public exports verified

Python compilation of the modified generator, semantic material-update module, and regression test file also passed.

## Expected production evidence

On a run where the Debevec update is selected and its first generated copy still fails a repairable prose check, the log may now show a protected-material-update message instead of a removal message. The canonical update must then either:

- be recomposed, validated, and committed to the August 29 canonical; or
- cause the terminal material-update publication invariant to fail the workflow.

A green run in which a selected validated Debevec update silently vanishes is no longer an allowed terminal state.
