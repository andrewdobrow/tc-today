# TCT v1.13.5.4b — Kit Embed Ownership + Provenance Test Fix

Incremental hotfix on top of v1.13.5.4 / v1.13.5.4a.

## Kit newsletter form
- Removes the visible TCT-side Morning Brief intro/wrapper copy added in v1.13.5.4.
- Restores the prior embed-only contract: TCT provides only the layout slot and Kit embed script.
- Visible newsletter wording remains owned entirely by the Kit form, so copy is managed in one place.
- Removes the now-unused wrapper-intro CSS.
- Adds regression coverage preventing TCT-side visible Morning Brief wrapper copy from being reintroduced.

## Shark-policy regression
- Keeps the shark-policy test focused on its actual purpose: provenance/content contamination.
- Accepts both legacy member-preview markup and the current character-bounded cliffhanger markup.
- Dedicated membership tests remain responsible for enforcing the current paywall structure.

## Validation
- Python compile checks passed.
- Focused membership + shark-policy suite: 8 passed.
- The shark-policy test was also replayed against a synthetic legacy paywall page: 3 passed.
