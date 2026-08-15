# v1.13.6.1c — Dynamic Image Regression Test Fix

## Scope
Test-only production hotfix. No generator, article, archive, permalink, membership, ranking, follow-up, or identity behavior is changed.

## Production failure addressed
`tests/test_article_image_overrides.py::test_current_surfaces_use_selected_image` required the historical Ethan Boyd article to remain on the current homepage and in the rolling RSS feed. That made the regression depend on mutable presentation state rather than the image-override contract.

## Change
- The durable assertions remain: override ledger, persisted archive image fields, and article-page OG/Twitter/hero image must use the selected override.
- Homepage and RSS are now conditional surfaces: when the story is present, any rendered image must use the selected override; rotating off those surfaces is not itself a failure.
- No production code changes.

## Validation
- Formerly failing current-surfaces test: PASS against current repo state.
- Durable override-ledger test: PASS.
- Test module compiles under Python 3.11.
