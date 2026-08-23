# v1.13.6.7a — Writer Contract Hardening

## Why this increment exists

The final-pipeline-aligned Sonnet 5 assignment editor -> Sonnet 4.5 writer experiment exposed two quality-guard failures after the editor had made useful source assignments:

1. the Treasure Coast Square Mall card used `$22K` in the headline but did not state the equivalent amount in the first paragraph; and
2. the Fort Pierce July 5 fatal-shooting update was rejected as missing original-event context even though its lead said the suspect was accused of "shooting and killing" the victim.

The first rejection was editorially correct. The second was a deterministic false negative.

## Changes

### 1. One shared lead/headline contract

The existing live production `LEAD AND HEADLINE INTEGRITY STANDARD` is now a single shared constant used by both:

- normal live category generation; and
- the publication-isolated Sonnet 5 assignment editor -> Sonnet 4.5 writer path.

This closes prompt drift between the live writer and assignment-shadow writer without changing the live standard itself.

The assignment writer is now explicitly told that:

- every monetary amount and local jurisdiction used in a headline must also appear accurately in the first paragraph;
- an update lead must state both the original event and the new development; and
- if the lead cannot support a headline claim cleanly, the writer must remove the claim from the headline rather than defer the support to a later paragraph.

### 2. Fatality-context inflection repair

The deterministic update-lead baseline anchor now recognizes normal fatality wording including `killing`, `kills`, `murder`, `murdered`, and `murdering`, in addition to the existing death/died/killed/homicide forms.

This permanently covers the exact Fort Pierce shadow output that said the suspect was accused of "shooting and killing" a 28-year-old man. That lead now correctly satisfies original-event context while still requiring a distinct new-development signal such as identification/arrest/charge.

### 3. Equivalent money-format normalization

Headline/lead claim integrity now treats equivalent compact and ordinary dollar forms as the same magnitude:

- `$22K` == `$22,000`
- `$63M` == `$63,000,000`

The guard remains strict about paragraph placement. A `$22K` headline still fails if `$22,000` appears only in paragraph two; it passes only when the equivalent amount is in the first paragraph.

## Permanent regressions

`tests/test_assignment_editor_shadow.py` now locks:

- the assignment writer receives the same live lead/headline contract;
- the exact Fort Pierce "shooting and killing" update lead is accepted as containing original-event context;
- the exact `$22K` Treasure Coast Square Mall card remains rejected when the amount appears only after the lead; and
- the same card passes claim consistency when `$22,000` is moved into the first paragraph.

## Scope

This increment does **not**:

- promote Sonnet 5 to live production;
- change source selection authority;
- add writer retries or extra model calls;
- alter persistent story identity, canonicalization, material-update routing, or permalink authority;
- change the live production lead/headline wording beyond sharing the same literal contract with the shadow writer.

## Validation

Local validation on the reconstructed v1.13.6.7 code line:

- focused writer/update/framing suite: **42 passed**;
- workflow-equivalent suite: **941 passed**;
- warnings: **45**, all the existing `datetime.utcnow()` deprecation class;
- package validation: **38 modules / 119 public exports**;
- generator runtime hotfix guard: **PASS**;
- false-jurisdiction source guard: **PASS**.
