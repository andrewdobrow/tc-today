# v1.13.6.8l Review Guide

## Purpose
Verify that later publisher reporting about an already-covered named missing person cannot create a parallel permalink when TCT has an authoritative custom canonical.

## Regression incident
Authoritative custom canonical:

`/articles/2026-08-29-martin-county-sheriffs-office-searches-for-missing-oklahoma-visitor-last-seen-at-chastain-beach.html`

Escaped duplicate to retire:

`/articles/2026-08-30-martin-county-sheriffs-office-searches-for-missing-oklahoma-man-last-seen-at-hut.html`

## Test Editorial Engine
Expected full result: **1,038 passed / 0 failed**.

## Generate News review
After one successful production run, verify:

1. The Aug. 30 escaped duplicate is not an active archive row or live homepage/category placement.
2. Opening the Aug. 30 duplicate route resolves/redirects to the Aug. 29 custom canonical and is not indexable as independent coverage.
3. The Aug. 29 custom canonical remains the identity/ranking authority for this incident.
4. If the newer publisher source is still in the source packet, inspect `data/semantic-publication-gate.json` for a materiality evaluation against the custom canonical.
5. If material new facts are validated, the update should land on the Aug. 29 permalink. If not, the source should be suppressed rather than published separately.

## What this patch intentionally does not do
- It does not automatically merge unnamed missing-person alerts.
- It does not make person-name equality alone sufficient.
- It does not force every later source to update the custom body.
- It does not weaken semantic materiality or source-integrity checks.
