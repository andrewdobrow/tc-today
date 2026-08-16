# Treasure Coast Today v1.13.6.1e
## Martin cocaine duplicate — conflict-override and fingerprint repair

### Production regression
A third public permalink was created for the same Martin County Sheriff's Office cocaine operation:

Canonical (preserve):
- `2026-08-14-17-arrested-in-indiantown-cocaine-trafficking-ring-three-remain-wanted-after-mon`

Later duplicates (redirect):
- `2026-08-15-17-arrested-in-martin-county-cocaine-trafficking-bust-4-kilos-seized-in-indianto`
- `2026-08-16-17-arrested-in-major-martin-county-cocaine-bust-4-kilos-seized-in-indiantown-ope`

### Root cause
v1.13.6.1d added strong candidate evidence for a named law-enforcement operation and a drug-operation continuity bundle, but the final semantic eligibility expression could still veto those candidates whenever legacy/generated event keys conflicted. The prior regression fixture did not reproduce that conflict, so it passed while production still failed.

The v1.13.6.1d migration fallback was also scoped to the one then-known Aug. 15 duplicate slug. It could repair that page, but it could not catch a newly minted Aug. 16 slug if generalized prevention failed.

### Fix
- Semantic publication gate bumped from 1.5 to 1.6, invalidating stale gate-cache keys.
- Exact matching named law-enforcement operations may now override a contradictory structured event key for *candidate retrieval only*.
- Added a narrow independent drug-operation bundle: same `drug-case` family, shared locality, shared law-enforcement agency, exact arrest count, shared named drug and at least three shared headline tokens.
- That strict bundle can override structured conflict for candidate retrieval only. It never directly authorizes a merge.
- Preserved existing conflict behavior for all other story classes; `unknown-event-*` handling was not globally relaxed.
- Replaced the Aug. 15-slug-only cleanup with a deterministic incident-fingerprint migration. Any later archive row within seven days that states 17 arrests + cocaine + Martin County/Indiantown + drug-operation framing is redirected to the Aug. 14 canonical.
- The fingerprint is intentionally incident-specific and is not a general drug-story fuzzy merge rule.

### Safety
- Aug. 14 remains the substantive canonical page.
- Later duplicate URLs become permanent redirects; they are not deleted into 404s.
- Different drug cases with a different arrest count are explicitly rejected by regression.
- No membership, Stripe, custom-article, ranking or follow-up activation behavior changes.

### Validation
- Exact Martin cocaine regression suite: 8 passed.
- Surrounding semantic/cross-source/incident/permalink suite: 106 passed.
- Workflow-equivalent suite: 889 passed.
- Package validation: 35 modules / 119 public exports.
- Generator runtime guard: PASS.
- False-jurisdiction guard: PASS.
