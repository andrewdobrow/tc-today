# v1.13.6.7n — Terminal Permalink Authority

This stabilization release closes the last architectural hole that allowed an angle-shifted or updated story to mint a new public permalink after earlier identity gates missed it.

## Root causes fixed

1. **Candidate miss implicitly meant NEW.** The existing semantic gate was precision-oriented. If no recent row crossed its fuzzy candidate threshold, publication could continue without a model comparing the proposed article to broader recent coverage.
2. **Canonical headline evolution contradicted slug safety.** TCT correctly updates living canonicals as facts develop, but archive safety later compared the *current* headline to the original slug. A legitimate update such as `to consider` → `approved`, or `survey planned` → `NWS confirms`, could eventually make the canonical look unsafe and force another URL.
3. **Publication slugs used UTC date.** A Tuesday-evening Treasure Coast publication after 8 p.m. could receive a Wednesday slug because UTC had crossed midnight.

## New terminal authority

Every ordinary generated article still about to create a new URL now passes a final Sonnet 5 permalink adjudication immediately before slug creation.

- Recent window: 14 days by default.
- Candidate ceiling: 12 canonicals by default.
- Retrieval is intentionally high-recall and is **not** identity authority.
- The shortlist includes exact-source, shared incident/person/location, same locality + event family, same locality + section, and lower-scoring recent continuity candidates.
- Sonnet 5 must explicitly return `new_story` before the create branch may write a page.
- `duplicate_use_existing_canonical` reuses the existing page.
- `update_existing_canonical` routes through the existing semantic material-update composer and context validation.
- `hold`, model failure, malformed output, or missing terminal NEW receipt fails closed: **no permalink is written**.
- A second same-event permalink still requires a material, independently newsworthy follow-up **and** a distinct persistent story identity.

The create branch contains an independent defense-in-depth assertion: ordinary generated articles without `_terminal_permalink_new_authorized` cannot write a slug even if another code path accidentally reaches the branch.

## Canonical evolution authority

New archive rows now store immutable:

- `permalink_origin_headline`
- `permalink_origin_date`

Slug/headline identity safety is anchored to the headline that created the URL, not the current living headline. Validated legacy material updates are also accepted through the existing `meaningful_update_validated` receipt.

This preserves the historical overwrite guard while allowing normal newsroom evolution of one canonical URL.

## Treasure Coast local publication date

`write_archives()` now uses `America/New_York` calendar date for new permalink slugs. A run at Tuesday 8:30 p.m. ET will no longer create a Wednesday-dated slug merely because it is already Wednesday UTC.

## Current production cleanup

The source-retirement cleanup policy additionally redirects:

- `2026-08-26-port-st-lucie-resident-takes-cover-as-possible-tornado-hits-neighborhood-sunday`
  → authoritative Port St. Lucie tornado canonical.
- `2026-08-26-port-st-lucie-residents-clean-up-debris-damaged-structures-after-sunday-tornado`
  → authoritative Port St. Lucie tornado canonical.
- `2026-08-26-port-st-lucie-to-consider-1483-annual-trash-fee-increase`
  → single retained approved/raised trash-fee canonical.

No useful article is deleted without a canonical destination; existing bad URLs become redirects.

## Validation

- New terminal-permalink regressions: 7/7 passed.
- Focused semantic/publication stabilization suite: 89/89 passed.
- Full CI-equivalent repository suite, excluding the same two workflow-excluded files:
  - 501/501 passed.
  - 503/503 passed.
  - **1004/1004 total passed.**
- Package validation: **38 modules / 119 public exports**.
- Python compilation: PASS.
