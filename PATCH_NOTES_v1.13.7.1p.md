# v1.13.7.1p — Non-Queue Custom Canonical Transaction Integrity

## Production failure
The September 2 production run reached final rendering with the Debevec material-update story correctly promoted to the front-page hero, but then failed the fail-closed Custom RSS publication contract.

The run had minted a second permalink for the already-established Debevec canonical:

`2026-09-02-martin-county-sheriffs-office-investigates-body-found-in-hutchinson-island-mangr`

instead of keeping the existing canonical:

`2026-08-29-martin-county-sheriffs-office-searches-for-missing-oklahoma-visitor-last-seen-at-chastain-beach`

The later canonical consolidation removed the duplicate, leaving a current-custom publication receipt for a URL that was correctly absent from RSS. The RSS contract therefore failed rather than silently syndicating an invalid publication.

## Observed failure point
`is_custom` and `authoritative_custom` are durable provenance flags. They remain on a published custom-origin story after it leaves `custom_articles.json`.

`_resolve_custom_publication_target()` was treating those durable flags as if they meant the live object was a **new current manual submission**. The custom manual-publishing contract intentionally says a changed exact headline is a new article. That rule is correct for a current queue payload, but incorrect for an already-published custom canonical whose display headline advances through a validated semantic/material update.

The Debevec archive row therefore had:
- the original August 29 canonical slug;
- the advanced body-found display headline;
- the immutable original manual `custom_headline_key`;
- durable `is_custom` / `authoritative_custom` provenance;
- no `_custom_active_queue` transaction marker.

The resolver saw the headline difference and created a new custom identity/permalink.

## Candidate correction
1. Adds `_is_current_manual_custom_submission()`.
   - Only an active `custom_articles.json` payload carrying `_custom_active_queue` receives manual exact-headline publication semantics.
   - Durable custom provenance alone is not a submission transaction.

2. Adds fail-closed non-queue canonical resolution.
   - A non-queue authoritative-custom placement must resolve through an already-established `canonical_slug`, `_archived_slug`, or current custom publication slug.
   - It may reuse only an active custom archive row owning that permalink.
   - If no established binding exists, generation stops before a new permalink can be minted.

3. Preserves immutable manual custom identity metadata during semantic/material headline progression.
   - A non-queue material update may change the public headline/body on the established canonical.
   - It does not rewrite the original manual `custom_headline_key`, custom payload hash, series key, or edition metadata as though the update were a new editor submission.

4. Preserves the existing manual queue contract.
   - Same exact manual headline may update its custom permalink.
   - Any manual headline difference still creates a new article.
   - Explicit custom slug collision protection remains fail-closed.

## Regression coverage
Adds the exact Debevec production state as a regression:
- advanced body-found headline;
- original August 29 canonical slug;
- original immutable custom headline key;
- durable custom provenance;
- no active queue marker.

The regression requires the resolver to retain the August 29 canonical, preserve the original manual identity metadata, create an RSS receipt for the retained canonical only, and pass the Custom RSS publication contract without the erroneous September 2 slug.

Also adds a fail-closed regression proving that non-queue custom provenance without an established canonical binding cannot mint a new article.

Existing direct unit fixtures that model current manual submissions now explicitly carry `_custom_active_queue`, matching the production transaction contract.

## Local validation
- Focused affected tests: `90 passed`
- Test Editorial Engine equivalent: `1103 passed, 0 failed` (44 existing deprecation warnings)
- Package validation: `38 modules imported, 122 public exports verified`

## Production acceptance
After Test Editorial Engine is green, run one Generate News. The candidate correction is production-proven only if:
- no new September 2 Debevec permalink is created;
- the August 29 Debevec canonical remains the publication target;
- `Custom RSS publication contract PASSED` appears;
- the overall Generate News command exits successfully;
- the front-page/canonical surface contracts remain green.
