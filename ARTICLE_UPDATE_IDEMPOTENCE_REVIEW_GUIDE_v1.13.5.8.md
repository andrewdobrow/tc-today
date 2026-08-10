# v1.13.5.8 review guide — manual article update/paywall idempotence

## Apply

Upload the overlay at the repository root, preserving paths.

## Required validation order

1. Run **Test Editorial Engine**.
2. If green, run **Update Treasure Coast Today**.
3. Confirm the production run reaches both:
   - `Prepare member-only article payload`
   - `Sync protected article store`

The second step is important because the workflow will rebuild the protected
Ethan Boyd payload from the authoritative manual content override and overwrite
any truncated protected row left by the old parser.

## Article to verify

`/articles/2026-08-06-martin-county-sheriffs-office-seeks-public-help-finding-missing-14-year-old-auti.html`

Expected public result:

- headline remains the resolved **safely located** headline
- Ethan Boyd image remains pinned
- only one bounded teaser/update sequence is visible
- no repeated `Original report` sections
- membership paywall appears once for signed-out/non-entitled readers
- article side rail is present again
- newsletter and share controls remain below the article content

Expected entitled-member result after the production workflow:

- the complete update and original report unlock
- the full original report appears once
- no repeated blocks are appended on refresh or on a later production run

## Regression invariant

A second production run with no editorial changes must not change the number of
`Original report` blocks. The manual content override is a replacement operation,
not an append operation.
