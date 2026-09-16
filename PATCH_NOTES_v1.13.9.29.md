# TCT v1.13.9.29 — editorial registry fixed-point repair

## Failure fixed

Production preflight could abort with:

`Registry preflight failed: deterministic repair did not converge within 16 passes. Last merges: {'story_002044': ('story_012322',)}`

## Root cause

The selective named-person-death repair can identify a legacy timeline row from its title even when that row has neither an `article_id` nor an `event_key`.

The old detach logic removed moved rows only by non-empty article ID or event key. For a legacy row where both were blank, the row was copied to the correct canonical story but accidentally remained in the contaminated secondary story. Every subsequent fixed-point pass therefore "moved" the exact same row again, making convergence impossible.

## Fix

- Adds a deterministic full timeline identity fallback using event key, article ID, canonical article ID, URL/source, normalized title, and published timestamp.
- Removes the exact moved row from the secondary record even when article/event IDs are blank.
- Preserves unrelated timeline entries in the secondary story.
- Does not broaden merge authority, delete unrelated stories, or relax the 16-pass safety ceiling.

## Regression

Adds a production-pattern regression using the reported `story_002044` / `story_012322` relationship. The synthetic registry now repairs on pass 1 and verifies clean on pass 2; a third direct repair is also clean.

## Validation

- Registry/fixed-point/incident focused suite: 53 passed.
- Exact GitHub editorial test command (`pytest tests` with the workflow's two intentional ignores): 1,340 passed, 0 failed.
