# TCT v1.13.0.2 — Semantic Source-Focus and Provenance Repair

## Purpose

The v1.13.0.1 production run successfully prevented an unsafe persistent-story registry merge, but it exposed contamination that had already been committed during the earlier partial v1.13.0 publication. A WPBF article about two shark sightings was generated as though its primary subject were Martin County's shark-fishing ordinance. That generated copy was then accepted as a material update to the ordinance article, adding unrelated St. Lucie and Jupiter incidents to the canonical page and source history.

This release repairs the canonical publication and closes both trust-boundary gaps that allowed the contamination.

## Changes

- Adds a universal source-focus contract that compares the generated headline and opening lead with the publisher headline and the opening focus of the source text. Generated copy that abandons the source story's primary event is rejected before publication.
- Adds an independent source-headline drift veto to semantic candidate retrieval. A generated headline cannot nominate an existing canonical story when publisher headlines have weak continuity and no structured identity anchor corroborates the pair.
- Treats `merge_would_contaminate_target` as a terminal registry rejection. It is recorded under `rejected_directives` and is no longer copied into or replayed from `pending_directives`.
- Repairs the July 29 Martin County shark-fishing canonical archive row and article page. The valid August 1 WPTV state-directive update remains attached; the unrelated WPBF shark-sighting source, St. Lucie classification, false incident anchor, sighting paragraphs, and image are removed.
- Removes the contaminated category-generation cache entry while preserving the source-text and URL-resolution cache so the shark-sighting story can be evaluated independently on a later run.
- Adds permanent regression coverage for source-focus drift, semantic retrieval drift, terminal merge rejection, and the repaired production publication state.

## Expected production result

The Martin County ordinance article remains canonical and retains the valid WPTV update. Its source history contains only ordinance coverage, its body contains no Normandy Beach or dead-hammerhead material, and its classifications remain limited to Martin County and Local Government. `story_001783` remains a separate shark-sighting story and is not aliased into `story_001155`. A future run may publish it independently only if its generated copy remains faithful to the shark-sighting source.
