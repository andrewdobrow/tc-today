# TCT v1.13.9.82 — Bunny mirror delivery reconciliation fix

## Problem
After switching `TCT_ARTICLE_IMAGE_MODE` to `mirror`, a newly generated article successfully uploaded and verified its image in Bunny, but the live article still rendered the original publisher image URL.

Root cause: `recover_recent_archive_source_images()` runs after article-page generation. It treated `source_image_url` as both provenance and public delivery authority. For a mirrored row it therefore:

1. saw the publisher `source_image_url` as authoritative,
2. reset archive `image_url` from the verified Bunny URL back to the publisher URL, and
3. replaced the Bunny URL in the freshly rendered article page with the publisher URL.

The mirror itself had succeeded. A later reconciliation pass was undoing it.

## Fix
- Keep `source_image_url` as immutable publisher provenance.
- Keep `hosted_image_url` as TCT/Bunny delivery provenance.
- In `mirror` mode, when `article_image_mirror_status == "mirrored"` and the hosted URL is a valid TCT mirror URL, `image_url` remains the hosted Bunny URL.
- The recent-source-image recovery pass may restore missing publisher provenance, but it can no longer downgrade public delivery from Bunny to the publisher.
- Existing recent pages already damaged by the old pass self-heal on the next normal mirror-mode Generate News run: publisher hero/OG/Twitter references are rewritten back to the verified Bunny URL.
- Shadow/external behavior is unchanged.

## Regression coverage
Added tests proving:
- a damaged mirrored page is repaired back to Bunny,
- shadow mode continues to use the publisher URL,
- a freshly mirrored page is not downgraded by the later recovery pass.

## Validation
Production suite command:

`python -m pytest tests -q --ignore=tests/test_canonical_identity.py --ignore=tests/test_matcher_contract.py`

Result: **1482 passed, 0 failed**.

Package validation: **42 modules imported, 123 public exports verified**.
