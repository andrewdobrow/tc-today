# Treasure Coast Today — October 23 Update reliability + malformed article ending

**Baseline reviewed:** `tc-today` ZIP from commit `4f4c4535f28be9e6e439ee708681bd9bd0e3ae56`, supplied October 23, 2026.

This overlay **supersedes** the earlier `TCT_Update_Push_Rebase_Hardening_2026-10-23.zip`: it includes that same push/rebase repair **plus** the article-text cleanup, so apply **this one ZIP only**. All files are repository-relative. No git patch commands, generator replacement, archive dump, or live protected content are included.

## A. Exact cause of the broken closing paragraph

In `tct_engine/article_prose_policy.py`, sentence splitting treated the period in reporter Laurie **K.** Blandford's name as a sentence boundary. A source-attribution filter removed the beginning of that sentence but kept the trailing fragment `Blandford and Olivia Franklin.`. It then removed an unrelated source-outlet sentence while retaining `Information about a possible second vehicle remains part of the investigation.`. The two leftovers were combined into the malformed paragraph the user saw on the article's subscribed/full-text view.

## B. Corrections

* `tct_engine/article_prose_policy.py` protects personal initials before sentence splitting, including chains such as `J. R. Smith`; legitimate attribution sentences now get removed in their entirety, not starting from the surname.
* `data/article-content-overrides.json` removes the entire source-attribution coda from the Oct. 9 Port St. Lucie article's authoritative editorial override; the preceding paragraph now ends on the continuing search for the second vehicle. It also adds exact, slug-scoped replacements for both old protected-store forms (full unedited attribution and already-sanitized orphan), so the automatic Supabase snapshot-rehydration process cannot reintroduce the broken ending. Does not alter the original publication timestamp, story slug, headline, arrest facts, or other articles.
* `tests/test_oct23_police_attribution_fragment_guard.py` reproduces the sentence-split error and exercises protected-store snapshot rehydration with both old broken forms, retaining a correct Kit newsletter slot.

## C. Previously prepared publishing fix (included, no functional changes)

* `scripts/push_generated_update.sh` hardens the Update workflow when concurrent GitHub runs modify the same generated files, including missing allowlist items and deletions, while maintaining fail-closed protection for non-generated/hand-edited content.
* `tests/test_generated_update_rebase_conflicts_oct23.py` tests that push/rebase behavior.

## Verification

On the supplied repository snapshot, running:

`PYTHONPATH=. pytest -q tests/test_generated_update_rebase_conflicts_oct23.py tests/test_oct23_police_attribution_fragment_guard.py tests/test_article_source_outlet_prose_guard.py tests/test_membership_protected_copyedit_persistence.py tests/test_article_content_overrides.py tests/test_membership_payfirst_protected_content.py`

produced **115 passed** (Python 3.13 container). The complete suite has **not** been run successfully in this environment; GitHub's Python 3.11 workflow remains authoritative. Production access to the member-only stored article and verification of live corrected text require a successful Update + protected-store sync.

## Deploy

1. Extract the ZIP over the latest local `tc-today` checkout. It contains files, **not a standalone repository**. If any of these paths have been independently changed since commit `4f4c453`, reconcile those edits instead of blindly overwriting.
2. Commit and push.
3. Run GitHub Actions **Test Editorial Engine**. Proceed only if green.
4. Run **Update Treasure Coast Today** once and verify it completes its `Prepare member-only article payload` and `Sync protected article store` steps and successfully pushes/deploys the updated article.
5. Open the existing October 9 canonical article as an authenticated member and verify it ends with the substantive second-vehicle paragraph, without the stray names. Verify the Kit newsletter module renders normally.

**Important:** The previous failure's commit/rebase cause was a well-supported hypothesis from concurrent GitHub commits, not a confirmed reading of the omitted error lines. This overlay repairs a real unsafe/missing-generated-file conflict path but does not establish that it was the only problem in that workflow. No attempt is made here to claim the entire article-update engine is fixed.
