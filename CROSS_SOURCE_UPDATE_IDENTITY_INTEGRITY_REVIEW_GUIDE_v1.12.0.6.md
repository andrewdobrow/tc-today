# Cross-Source Update Identity Integrity Review Guide — v1.12.0.6

Review `data/cross-source-update-identity.json` after production.

Required:

- `passed` is `true`.
- Every recorded match has confidence of at least `0.90`.
- `matched_canonical_slug` identifies the already-established TCT permalink.
- `resolved_url` and `publisher` represent the underlying source when a Google News wrapper was resolved.
- `evidence_dimensions` contains multiple stable event dimensions rather than source or headline equality alone.
- `relationship` is `same_event`.
- `canonical_story_id` replaces any different incoming fragmented story ID.
- `final_publication_action` is a canonical bind, in-place update, skip or fail-closed preservation—not a newly minted parallel permalink.
- Contextless update copy appears as `preserve_existing_page_contextless_update_rejected`.
- A successful in-place update preserves the canonical `first_published` value.
- `last_meaningful_update_at` appears only when the replacement changed and passed both context and novelty checks.
- Authoritative custom and recurring custom reports remain outside this fallback.

Expected log when matches occur:

`Cross-source canonical match: '<incoming>' -> '<existing slug>' (<confidence>)`

Expected report summary:

- `match_count`: number of high-confidence canonical bindings;
- `updated_existing_count`: accepted in-place updates;
- `preserved_or_held_count`: fail-closed skips or context holds;
- `canonical_bound_before_generation_count`: matched candidates that were bound before generation but not selected for final publication.

A run may legitimately record zero matches. Do not force an update count; validate the deterministic fixtures and the evidence for any live match.
