# Treasure Coast Today v1.13.6.1b

## Forward identity reconciliation hotfix

Production exposed a contract mismatch after `write_archives()` correctly held a generated story with no current persistent story ID. The later live-publication reconciliation treated the existing archive page as a valid receipt, while the final forward-live-identity gate correctly rejected the same placement with `forward_published_article_missing_story_id`.

### Fix

- A current forward-generated live placement now treats an archive row as a valid publication receipt only when that row has a persistent `editorial_story_id`.
- Explicit `_archive_only` recovery retains its existing legacy exemption.
- Current-run duplicate and exact-source rebound paths apply the same requirement.
- Writer holds now stamp `_publication_skip_reason=missing_current_run_persistent_story_id` so reconciliation diagnostics explain why a placement was removed.
- Added a regression reproducing the production condition: an article file and archive row exist, but the archive row has no story ID. Reconciliation must remove that forward-live placement before the final gate.

### Scope

No changes to story matching, ranking, follow-up detection, category eligibility, membership, Stripe, Supabase, custom article logic, or archive-only recovery policy.
