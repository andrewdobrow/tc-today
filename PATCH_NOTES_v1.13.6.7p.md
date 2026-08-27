# v1.13.6.7p — Canonical Update Transaction + Terminal Resolution + Final Surface Authority

This overlay closes the authority-ordering defects exposed by the first production run after 6.7o. It keeps the terminal permalink write barrier intact while making validated living-story updates and final homepage identity converge on one canonical publication state.

## What changed

- **Atomic canonical update metadata:** validated material updates may evolve the live canonical headline without restoring the permalink-origin headline. Legacy canonicals freeze `permalink_origin_headline` before mutation, while unrelated overwrite attempts still fail the contextual update contract.
- **Canonical freshness split:** canonical first publication and latest validated material update are persisted separately as `canonical_first_published_at` and `canonical_last_material_update_at`. Final canonical rebinding now carries those receipts forward, so a fresh update cannot become stale merely because it reused an older permalink.
- **One focused terminal HOLD resolution:** a validated first-pass terminal HOLD gets exactly one bounded Sonnet 5 resolution pass over the strongest shortlist. Clear no-match cases may resolve to NEW; same-event cases resolve to UPDATE/DUPLICATE; model errors or genuine ambiguity remain HOLD.
- **Terminal authority propagated to shadow:** the assignment-editor challenger now consumes the live terminal source outcome. A source held by terminal publication authority cannot appear publishable only in shadow; duplicate/update outcomes rebind to the selected canonical.
- **Final surface authority ordering:** homepage candidates are canonicalized and deduped before Top Stories ranking, then deduped again after final binding. Redirect-backed historical placements cannot survive as independent cards, and two placements that rebound to one canonical collapse before render.
- **Observability:** semantic publication report schema advances to 5 with explicit terminal-resolution policy and counters.

## Permanent regressions added

1. Giustino animal-hoarding plea/probation update keeps the July permalink but publishes the new headline and fresh update receipt.
2. Legacy canonical without `permalink_origin_headline` freezes the stored old headline as origin before live headline evolution.
3. Unrelated homicide-over-trash overwrite still fails closed.
4. Byron Donalds/Bryan Avila first-pass HOLD resolves NEW when no candidate is the same event.
5. Martin County burglary arrests first-pass HOLD resolves NEW when no canonical matches.
6. NWS Port St. Lucie tornado-warning explanation resolves to the retained tornado canonical instead of minting a third URL.
7. Redirect-backed tornado placement canonicalizes before homepage ranking.
8. Two redirect placements that rebound to one canonical collapse before final render.
9. Shadow cannot retain a source that live terminal authority held.

## Validation

- `python scripts/validate_package.py` → 38 modules imported, 122 public exports verified.
- CI-equivalent pytest gate → **1,013 passed**, zero failures.
