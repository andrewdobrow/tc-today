# v1.12.0.1 Production Review Guide

## Expected workflow behavior

The production run must progress beyond:

- `Live permalink integrity PASSED`
- `Live category canonicalization ...`
- `Live category canonical contract PASSED`

It must not raise `NameError: name '_publication_identity' is not defined`.

## Required output checks

Review these generated reports after the run:

- `data/canonical-publication-ledger.json`
- `data/global-incident-identity-contract.json`
- `data/live-category-canonical-dedup.json`
- `data/live-category-canonical-contract.json`
- `data/final-canonical-surface-contract.json`

The category contract must report `passed: true` and zero duplicate or redirect-source
placements. Confirm the Geoffrey Lang and Glades Cut Off Road duplicate URLs now
redirect to their selected canonical articles and no longer appear as parallel cards.
