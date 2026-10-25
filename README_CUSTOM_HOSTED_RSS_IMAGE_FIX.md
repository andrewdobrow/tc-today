# TCT — Austin Hodge RSS/social image contract repair

**Why the Oct 24/25 Update failed:** The image URL was the correct, editor-selected TCT-hosted photo. The RSS validator treated its TCT CDN URL as an ordinary mirrored news-source image and required a separate external publisher URL, which a directly editor-supplied custom photo does not have. The validation code reported `mirrored_source_authority_not_persisted_to_archive` even though archive `hosted_image_url` and `source_image_url` both held the requested hosted URL.

**What changes:** A precisely restricted exception is added for an explicitly custom article with a durable `custom_id`, correct TCT CDN host, and exact `image_url`, `source_image_url`, `hosted_image_url` equality; non-custom automated publisher mirrors *still require* a different original publisher `source_image_url`. A stale `article_image_mirror_status` flag on a custom editorial asset does not override the editor-selected image. This leaves the existing RSS validator and its other checks intact.

This ZIP **does not replace** the current 2 MB `scripts/generate.py` and **does not modify the Austin Hodge article text, photo, or queue**. It must be applied over your existing, already-fixed current repo.

## Deployment
1. Extract this overlay over the local repo, commit and push.
2. In GitHub Actions, run **Repair custom-hosted RSS image authority** once. It modifies the *current main* `scripts/generate.py` at a unique guarded insertion point and runs eight new targeted tests before committing. It does **not** publish.
3. Run **Test Editorial Engine**. If green, run **Update Treasure Coast Today**.
4. Confirm the RSS social image contract passes, the original Austin Hodge photo and original URL persist, and the competing duplicate URL is redirected to the canonical.

Avoid running the main Update before the repair action has committed, as the validator failure is deterministic with the current custom image.

## Files
- `tct_engine/custom_hosted_social_image.py` — restricted first-party custom photo predicate
- `scripts/apply_custom_hosted_rss_image_guard.py` — safe idempotent current-HEAD patcher
- `.github/workflows/tct-custom-hosted-rss-image-repair.yml` — one-time patch-and-test workflow
- `tests/test_custom_hosted_image_rss_contract.py` — positive and negative regressions
- This README
