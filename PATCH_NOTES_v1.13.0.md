# TCT v1.13.0 — Semantic Material Update Routing

## Purpose

The semantic final publication gate already distinguished between a duplicate and a genuine development in an existing story. Until this release, a validated `update_existing_canonical` decision was reported but not fully executed: the newer article could remain active beside the older canonical page and its persistent story fragment could remain separate.

This release turns that decision into a complete canonical update workflow.

## Canonical material-update workflow

When Claude validates that an incoming report covers the same real-world story and contains a material development, the publisher now:

1. Loads the complete existing canonical article and the incoming report.
2. Asks a bounded Claude composer to produce one self-contained replacement article using only those two supplied texts and the semantic gate's explicit novel facts.
3. Requires the first paragraph to explain both the original event and the new development.
4. Revalidates the merged article deterministically for contextual completeness, article depth, and canonical-permalink alignment.
5. Rewrites the existing canonical page while preserving its original URL and first-published timestamp.
6. Adds a visible `Updated` timestamp and uses it as structured data `dateModified`.
7. Persists the incoming source, source headline, source image, shared anchors, novel facts, confidence, and source history on the canonical archive record.
8. Redirects the later update URL to the refreshed canonical page and removes the later row from active archive, RSS, sitemap, and visible surfaces.
9. Consolidates the incoming persistent story fragment into the canonical story ID and writes a permanent alias.
10. Refreshes canonical ranking freshness only after the material update passes every validation gate.

## Fail-closed behavior

Claude does not directly write files or choose a canonical permalink. If the composer is unavailable, returns malformed JSON, omits original context, omits the new development, or produces a thin/incoherent replacement, the publisher preserves both existing pages and records a material-update hold for review and retry.

## Shark-fishing production case

The release includes regression coverage for the Martin County shark-fishing sequence:

- July 29 canonical article about commissioners beginning a rewrite after complaints involving drones and chum.
- August 1 update reporting that the Florida Fish and Wildlife Conservation Commission directed the county to align the ordinance with state law.

The expected production action is to refresh the July 29 canonical page, redirect the August 1 URL to it, and consolidate `story_001724` into `story_001155`.

## Diagnostics

`data/semantic-publication-gate.json` now records:

- material-update composer calls
- validated material updates applied
- update redirects
- update holds
- composition validation details
- shared anchors and novel facts
- registry consolidation relationship type

The workflow summary separately reports duplicate redirects and material-update redirects.
