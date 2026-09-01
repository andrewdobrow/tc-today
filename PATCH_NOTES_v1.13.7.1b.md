# TCT v1.13.7.1b — Post-read Meter Card Placement Integrity

## Fix
The first free monthly article must render completely before the post-read membership card appears. On long or legacy/repaired article shells, relying on the original paywall placeholder position could leave the `You've read your free article this month.` card before the true end of story content.

After a `monthly_free` unlock, `membership.js` now explicitly relocates the entire `.tct-member-only` conversion block to the article's true end boundary:

1. immediately before the article newsletter slot when present;
2. otherwise immediately before the share block;
3. otherwise immediately after the last unlocked `.article-body` block.

The second-and-later article paywall remains at the teaser boundary and is unchanged.

## Cache integrity
Membership asset version is bumped to `1.13.7.1b` so generated/retained article pages request the corrected JS immediately rather than reusing cached `1.13.7.1` assets.

## Validation
- Membership-focused regression suite: 36 passed / 0 failed.
- Full `tests/` CI-equivalent suite excluding the two standard standalone contract files: 1060 passed / 0 failed / 44 existing warnings.
