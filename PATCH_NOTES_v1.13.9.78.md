# TCT v1.13.9.78 — Bunny finally-contract compatibility fix

Apply on top of **v1.13.9.77**.

## Fix

Restores the existing production model-usage observability contract by making
`_finalize_model_usage_observability()` the first direct statement in the
`finally:` block of `scripts/generate.py`.

The Bunny article-image mirror finalizer still runs immediately afterward in
its own guarded `try/except`, so Bunny/reporting failures remain non-fatal to
publication.

## Scope

- `scripts/generate.py` only
- No Bunny credentials/settings changes
- No workflow/YAML changes
- No article-image behavior changes
- No reader-facing changes

## Validation

Production test command rerun against the current repo with v1.13.9.77 applied:

`python -m pytest tests -q --ignore=tests/test_canonical_identity.py --ignore=tests/test_matcher_contract.py`

Result: **1460 passed, 0 failed**.
