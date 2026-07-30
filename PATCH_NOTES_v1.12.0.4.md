# TCT v1.12.0.4 — Story-Aware Update Context

## Problem

A source could be a clear continuation of an already-published TCT story while its
headline contained no literal word such as “update,” “new details,” or “follow-up.”
The category writer therefore treated it as a standard new article. The universal
lead prompt asked for context, but the deterministic update contract did not run.

The July 30 Silverstream Circle neighbor-reaction article exposed the gap: the copy
began with a neighbor’s reaction without first explaining that a 3-month-old Fort
Pierce boy died from dehydration and malnutrition and that three caregivers were
later arrested.

## Changes

- Builds the canonical publication ledger before category generation.
- Any incoming source that resolves to an existing canonical TCT publication is
  marked as an update before Claude sees it, regardless of headline wording or a
  fragmented upstream registry route.
- Supplies the model with two explicitly separated evidence blocks:
  - `ORIGINAL PUBLISHED STORY`
  - `CURRENT UPDATE SOURCE`
- Carries the canonical context through source attachment, category caching,
  enrichment and publication.
- Strengthens the update-lead contract. The first paragraph must contain:
  - the original event anchor;
  - enough identifying facts from the canonical headline to explain the event;
  - the current development or reaction;
  - at least 18 words.
- Adds community/neighbor reaction as a recognized update development.
- Replaces the final writer’s generic article-framing check with a direct comparison
  between the proposed replacement lead and the canonical article it would overwrite.
- Preserves the existing canonical page when the replacement lead lacks context.
- Adds story-aware update context counts and binding details to the category-generation
  report.

## Publication behavior

Headline wording can no longer decide whether a source is an update. When the
canonical ledger finds an existing story, the model must write a first-time-reader
lead or the existing page remains unchanged. No second permalink is created.

## Regression fixture

The exact Silverstream Circle neighbor-reaction pattern is permanent coverage:

- contextless neighbor reaction fails;
- contextual reaction naming the infant death, cause and arrests passes;
- the original canonical article is injected into the category prompt;
- a registry `generate_new` misclassification cannot bypass the final write barrier.
