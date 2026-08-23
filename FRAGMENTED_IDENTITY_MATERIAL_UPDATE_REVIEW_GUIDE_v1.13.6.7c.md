# v1.13.6.7c Production Review Guide

## Apply

Extract this overlay at the repository root, preserving paths.

## Test workflow

Run **Test Editorial Engine** first. Do not proceed to production if the story-regression gate, persistent identity integrity, package validation, or publication/canonical contracts fail.

## Production workflow

Then run **Update Treasure Coast Today** with the Sonnet 5 assignment-editor -> Sonnet 4.5 writer shadow experiment enabled if continuing the bake-off.

## What to verify in production

For a same-event source whose registry ID is fragmented but whose canonical publication identity is hard-matched:

- materiality evaluation happens before terminal published-story suppression;
- a material development is routed to the existing canonical story;
- a non-material reprint remains suppressed;
- the existing canonical slug remains stable;
- no second article URL is minted;
- refreshed canonical content can participate in current placement using the new development;
- Hometown News remains excluded at ingestion;
- no new category contamination or canonical identity drift appears.

## Exact production case to watch

The Palm City Border Collie legal-surrender/adoption development is the key regression. The production defect had an incoming fragmented registry ID (`story_003665`) while the published canonical used the authoritative custom story ID. The publication ledger already knew they were the same incident; v1.13.6.7c moves that authority early enough for the materiality gate to make the decision.

## Bake-off interpretation

Do not count the August 22/23 final-pipeline blind run as a Sonnet promotion win/loss. Both scoreable categories collapsed to final ties because deterministic suppression erased the model-selected current sources and forced archive recovery. Rerun after this ordering correction so the final pipeline can preserve legitimate material updates.
