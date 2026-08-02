# Semantic Source-Focus and Provenance Repair Review Guide — v1.13.0.2

## 1. Pre-production validation

Run **Test Editorial Engine** and confirm package validation and the full pytest suite pass. The current release metadata must report:

- Engine version: `1.13.0.2`
- Release: `semantic-source-focus-and-provenance-repair`
- Observability schema: `39`

## 2. Canonical shark-fishing article

Open:

`/articles/2026-07-29-martin-county-commissioners-move-to-rewrite-shark-fishing-rules-after-public-bea.html`

Confirm:

- The page remains the canonical Martin County ordinance story.
- The article retains the August 1 state-directive update and WPTV image.
- The body does not mention Normandy Beach, a 12-foot shark video, or a dead hammerhead near Jupiter Beach Resort.
- The article remains classified only as Local Government and Martin County.

## 3. Archive provenance

In `archive.json`, inspect the canonical row and confirm:

- `latest_source_url` is the WPTV state-directive article.
- `source_history` contains the original WPBF ordinance article and the WPTV material update only.
- The unrelated WPBF shark-video URL is absent.
- `county_keys` is `martin` only.
- `incident_anchor_key` is absent.
- Material-update novel facts describe the state directive, postponement, and legal review—not shark sightings.

## 4. Persistent-story identity

In `data/editorial_story_registry.json`, confirm:

- `story_001155` remains the ordinance story.
- `story_001783` remains a separate active shark-sighting story.
- There is no alias from `story_001783` to `story_001155`.

In `data/semantic-publication-gate.json`, a future attempted unsafe consolidation should appear under `registry_consolidation.rejected_directives` with `reason_code: merge_would_contaminate_target`; it must not remain pending for replay.

## 5. Source-focus behavior

If the WPBF shark-sighting source is encountered again, verify one of these safe outcomes:

- It is generated and evaluated as a shark-sighting story, or
- Generation is rejected with `generated_copy_drifted_from_source_focus`.

It must not be reframed as a Martin County ordinance update, nominated against the canonical ordinance article, or added to that article's source history.

## 6. Redirects

Keep the existing August 1 WPTV update redirect pointed to the July 29 canonical article. No redirect should be created from a shark-sighting article URL to the ordinance article.
