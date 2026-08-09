# TCT v1.13.3.2 — Autonomous Registry / CI Stability

This release is a reliability correction, not a membership or presentation release.
It addresses the recurring class of CI failures caused by coupling regression tests
and workflow preparation to mutable production story IDs.

## Root cause

Persistent story IDs are internal implementation identifiers. Deterministic repair
can legitimately merge a former canonical story into another canonical and remove
that numeric ID. The test workflow previously normalized the tracked production
registry in-place *before* pytest, while several tests asserted that specific
numeric IDs (for example historical road-rage and evolving-story IDs) must still
exist. A correct repair could therefore make the test suite fail.

The workflows also executed generator hotfix scripts in write mode on every run,
meaning CI/production could rewrite source code before validating it.

## Changes

- Test Editorial Engine now verifies registry repairability on a `$RUNNER_TEMP`
  scratch copy instead of mutating `data/editorial_story_registry.json` before
  pytest.
- Production keeps the real deterministic registry normalization step because the
  live state must be healed before generation.
- Production and test workflows now run the generator runtime and county-source
  guards in verification-only mode. Source code must already contain the fix;
  workflows no longer silently patch `scripts/generate.py` before tests.
- `apply_false_jurisdiction_hotfix.py` now supports `--check`.
- Registry aliases are flattened after repair so every retained historical alias
  points directly to one active canonical story. Chains through removed
  intermediate canonicals are eliminated and invalid/dangling aliases are removed.
- Production-registry regression tests use semantic/source invariants rather than
  pinning active records to numeric `story_XXXXXX` IDs.
- A permanent test contract prevents future tests that read the live registry from
  reintroducing mutable active-story-ID assertions (with one explicit quarantine
  audit exception).

## Safety

- No public HTML, membership UI, Stripe behavior, Supabase configuration, pricing,
  article text, or paywall state is changed.
- No fail-closed identity authority rule is weakened.
- Fuzzy/candidate-only evidence still cannot authorize destructive identity writes.
- The production registry is still normalized and validated before generation.

## Validation performed

- `python scripts/validate_package.py`: passed (34 modules / 119 exports).
- Focused autonomous-registry/workflow suite: 58 passed.
- Remaining post-reader-support test tranche: 216 passed.
- Registry/identity-focused tranche: 75 passed.

The local container uses Python 3.13 and the monolithic all-tests invocation is
substantially slower than the GitHub Python 3.11 runner, so validation was also
split into focused tranches. The changed components and workflow contracts passed.
