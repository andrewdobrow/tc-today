# Review Guide — v1.13.0 Semantic Material Update Routing

## Expected workflow output

A successful material update should produce log output similar to:

```text
SEMANTIC MATERIAL UPDATE: refreshed '<canonical-slug>' and redirected '<incoming-slug>'
Semantic publication gate: ... 1 material update(s), 1 update redirect(s), 1 update composer call(s), ... 1 registry merge(s), ... 0 update hold(s)
```

The exact counts may vary when multiple stories are evaluated.

## Required report checks

Review `data/semantic-publication-gate.json` and confirm:

- `summary.material_update_composer_calls` increased.
- `summary.material_updates_applied` increased.
- `summary.material_update_redirects` increased.
- `summary.material_update_holds` is zero for the successful case.
- `material_update_compositions[].status` is `validated`.
- `material_updates[]` contains the source slug, target slug, confidence, shared anchors, novel facts, and update timestamp.
- `registry_consolidation.merges[]` identifies `relationship_type: material_update`.

## Canonical article checks

For the Martin County shark-fishing case:

1. Open the July 29 canonical URL.
2. Confirm the article now explains the original complaints and ordinance rewrite as well as the later state directive.
3. Confirm the first paragraph stands alone for a reader who did not see the earlier story.
4. Confirm the original `Published` date remains July 29.
5. Confirm an `Updated` timestamp appears beside it.
6. Confirm page source uses the update timestamp for NewsArticle `dateModified`.
7. Confirm the refreshed story remains eligible for current homepage/category ranking.

## Redirect and surface checks

Open the August 1 URL and confirm it redirects to the July 29 canonical page.

Confirm the August 1 URL is no longer emitted as an independent item in:

- `archive.json`
- RSS
- sitemap
- homepage/category cards
- Latest News

## Registry checks

In `data/editorial_story_registry.json`, confirm:

- `story_001724` is no longer an active independent story.
- `story_aliases.story_001724` points to `story_001155`.
- Sources and timeline entries from the update fragment are retained under `story_001155`.
- The merge audit records `relationship_type: material_update` and the validated novel facts.

## Fail-closed test

A malformed or contextless composer response must not overwrite the canonical page or redirect the incoming URL. It should instead increment `summary.material_update_holds`, preserve both pages, and leave the decision retryable on a later run.
