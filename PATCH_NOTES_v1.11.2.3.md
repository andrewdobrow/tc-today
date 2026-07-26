# TCT v1.11.2.3 — Custom Queue Fail-Closed

## Production failure addressed

The July 25 production run did not load either queued custom article because `custom_articles.json` was invalid JSON. The generator logged the parse error, returned an empty custom queue, and continued publishing the rest of the site. That fail-open behavior allowed a successful deployment with no new custom articles.

## Changes

- Replaces `custom_articles.json` with a valid two-item queue containing:
  - `Hurricane Season Ready: 12 Treasure Coast Essentials to Stock Up On`
  - `Port St. Lucie Police Unveil New $28 Million Training Facility`
- Removes the retired July traffic article from the active queue. Its exact headline and legacy slug remain permanently blocked by `data/custom-retirements.json`.
- Changes `load_custom_articles()` to fail closed on:
  - malformed JSON,
  - a non-array top-level value,
  - non-object queue items,
  - missing headlines,
  - duplicate exact headlines,
  - missing categories, and
  - missing article bodies.
- Adds the same queue validation to `scripts/validate_package.py`, so malformed custom content fails before the long generation step begins.
- Makes pushes that modify `custom_articles.json` or `data/custom-retirements.json` trigger the Test Editorial Engine workflow.
- Retains the v1.11.2.2 custom archive rebind protections:
  - different custom headlines cannot cross-replace,
  - exact-headline refreshes restore their declared category,
  - active queue payloads outrank archive-only clones during write-through.
- Updates the engine footer to:
  - `TCT Editorial Engine — v1.11.2.3 custom-queue-fail-closed`

## Image requirement

The police article references `/images/psltrainingfacility.png`. That file must exist in the repository at `images/psltrainingfacility.png` before deployment.

## Validation completed locally

- `python scripts/validate_package.py`: passed
- Focused custom-publication suite: 29 passed
- Workflow-equivalent local suite: 297 passed
- Existing warnings: 16 `datetime.utcnow()` deprecation warnings
- GitHub Actions: not run here
- Production generation/deployment: not run here

## Apply

Apply this repository-root overlay over the current v1.11.2.1 or v1.11.2.2 tree, commit it, run **Test Editorial Engine**, then run the production update workflow.
