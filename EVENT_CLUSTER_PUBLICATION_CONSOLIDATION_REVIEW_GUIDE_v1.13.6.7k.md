# v1.13.6.7k Review Guide

After applying the overlay, run **Test Editorial Engine**, then one production run.

## Expected future behavior

For multiple sources about one event:
- routine resident reaction/color -> update existing event canonical
- official classification/damage totals -> update existing event canonical
- cleanup/mechanics/explanation -> update the relevant canonical
- genuinely independent accountability/consequence/policy question -> may receive a second permalink only with distinct persistent story identity

A different headline or reporting angle alone must not create another story URL.

## Port St. Lucie tornado migration

The retirement cleanup should redirect five redundant tornado articles and leave two retained publications:
1. Main event canonical:
   `2026-08-25-port-st-lucie-residents-receive-tornado-emergency-alert-20-minutes-after-storm-p`
2. Alert/accountability canonical:
   `2026-08-25-port-st-lucie-residents-question-why-tornado-alerts-arrived-late-or-never-came-a`

Five redundant slugs should be canonical redirects:
- resident frightening sounds/damage -> main
- Hurricane Andrew anniversary angle -> main
- Aug. 24 pre-survey article -> main
- 20–30 homes / 2-mile path article -> main
- radar-limitations article -> alert/accountability

## Diagnostics to inspect
- `data/semantic-publication-gate.json`
- `data/source-retirement-cleanup-report.json`
- Top Stories ranking diagnostics/log output
- `data/editorial_story_registry.json`

## Regression expectations
- Angle-shifted tornado coverage with strong shared facts is recalled for semantic adjudication.
- Unrelated Fort Pierce structure fire is not recalled as the tornado event.
- Same-event angle defaults to update, not new permalink.
- Same persistent story identity cannot mint an independent follow-up URL.
- A distinct accountability story identity can be independently published.
- Top Stories caps a single event cluster at two placements.
- Current cleanup leaves exactly the two intended tornado canonicals.
