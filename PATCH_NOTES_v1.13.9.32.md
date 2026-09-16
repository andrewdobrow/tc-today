# TCT v1.13.9.32 — monthly-free Mediavine leaderboard placement

## Fix
- Keeps Mediavine's `.mv-leader` slot immediately above the subscription offer after the monthly free article is unlocked and the offer is moved to the end of the full story.
- Corrects the v1.13.9.31 behavior where the leaderboard stayed inside the original membership wrapper and was removed when that wrapper was discarded.
- Preserves the intended monthly-free end-of-story order: full story -> Mediavine leaderboard -> subscription offer -> Morning Brief -> ancillary event/share content.
- Does not add ads for paid subscribers; the existing `mv-no-ads` behavior remains unchanged.

## Delivery
- Bumps membership assets to `1.13.9.32` so browsers receive the corrected client logic immediately.
- Delta overlay only; apply on top of v1.13.9.31.

## Validation
- Targeted membership/Mediavine/release tests: 61 passed.
- Exact GitHub editorial pytest command (`tests`, excluding the two workflow-ignored legacy identity files): 1,347 passed.
