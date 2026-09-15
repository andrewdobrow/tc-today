# TCT v1.13.9.27 — Recurring custom edition slug fix

## Production failure addressed

The Sept. 19-20 weekend-events custom article reached publication, but the generic
80-character headline slug clipped off the visible edition marker near the end of the
headline. The final forward identity contract correctly rejected that permalink with:

`recurring_custom_edition_slug_mismatch`

The failed workflow did not complete deployment.

## Root cause

Recurring custom series such as weekly weekend-event roundups carry a durable edition
identity (`sep-19-20`). If no explicit custom slug is supplied, the new-page branch used
the ordinary generated-headline slug helper. That helper intentionally clips long slugs,
which can remove a date range placed late in a headline.

## Fix

- Keeps ordinary generated slugs unchanged.
- Keeps explicit editor-supplied custom slugs unchanged.
- For a recurring custom publication with a visible edition marker, first tries the
  normal headline slug.
- If that slug lost the edition marker, falls back to a concise deterministic slug:
  `YYYY-MM-DD-{series-key}-{edition-key}`.
- The current weekend-events edition therefore resolves to a permalink shaped like:
  `2026-09-14-treasure-coast-weekend-events-sep-19-20`.
- Adds a regression reproducing the exact long weekend-roundup headline class and
  verifies the resulting slug passes the recurring-edition identity contract.

No article copy, event selection, image URL, archive state, registry state, or membership
code is changed by this patch.

## Validation

`python -m pytest tests -q --ignore=tests/test_canonical_identity.py --ignore=tests/test_matcher_contract.py`

Result: **1336 passed**.
