# TCT v1.13.6.5c — Anthropic SDK Semantic Gate Compatibility Hotfix

## Trigger

Production model-usage telemetry recorded a zero-duration `TypeError` from `tct_engine/semantic_publication_gate.py:adjudicate_candidates` before any Anthropic usage metadata was produced.

## Root cause

The production workflow installs the current `anthropic` Python SDK without a version pin. The current SDK's stable `messages.create()` signature no longer accepts the legacy `temperature` keyword. TCT still supplied `temperature=0` in two semantic identity/update request sites:

- `tct_engine/semantic_publication_gate.py`
- `tct_engine/semantic_material_update.py`

Because request validation happens locally in the SDK, the semantic publication request failed immediately with `TypeError`, before an API request could be billed or timed.

## Changes

- Removes the obsolete `temperature` keyword from semantic publication adjudication.
- Removes the same latent obsolete keyword from the semantic material-update composer.
- Preserves model IDs, prompts, max-token limits, timeouts, fail-closed behavior, validation thresholds, publication actions, and all deterministic identity rules.
- Adds strict-signature regressions that emulate the current Anthropic SDK request surface and reject any future reintroduction of unsupported request kwargs.

## Validation

- Focused semantic gate/material update/model-usage tests: 41 passed.
- Workflow-equivalent suite: 921 passed, 43 existing deprecation warnings.
- Package validation: 37 modules imported, 119 public exports verified.

## Production expectation

On a run that reaches semantic publication adjudication, `model-usage-report.json` should no longer contain a zero-duration `TypeError` for `semantic_publication_gate.py:adjudicate_candidates`. A successful identity call should instead appear under the `identity_decision` workload with normal usage metadata. If the model/API itself fails, the existing fail-closed hold remains in force.
