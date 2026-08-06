# Missing-Person Identity Continuity Review Guide — v1.13.1.2

## Required workflow

1. Apply the overlay to the current repository.
2. Run **Test Editorial Engine**.
3. Confirm `Normalize persistent story registry` reports
   `verification_clean: true` before pytest.
4. Run **Update Treasure Coast Today**.

## Acceptance criteria

- The complete pytest suite passes.
- `remaining_unified_incident_groups` is `0` after registry preflight.
- The Ethan Boyd source records resolve to one persistent story.
- The first Aug. 6 article remains canonical:
  `2026-08-06-martin-county-sheriffs-office-seeks-public-help-finding-missing-14-year-old-auti`.
- The second Aug. 6 URL is a verified noindex/301 redirect to that canonical article.
- The duplicate is absent from `archive.json`, RSS, homepage and category surfaces.
- The canonical article retains `/images/ethan-boyd.png` when the earlier image
  override is present in the repository.
- Missing-person alerts with different names or ages remain separate.
- Registry fixed-point preflight completes in bounded time and its second pass is
  clean.

## Reports to provide after production

- Complete workflow log
- `data/editorial_story_registry.json`
- `data/canonical-redirects.json`
- `data/persistent-story-identity-integrity.json`
- `data/category-generation-report.json`
- `archive.json`
