# TCT v1.13.9.66 — Temporal Source Revalidation + Beasley Resolution

## Problem fixed
A publisher can update an article in place without changing its RSS URL, title, summary, or published timestamp. TCT's source-text cache normally keeps a successful extraction for 24 hours. For the Curtis Beasley execution story, WPTV's pre-execution body was cached at 2026-09-29T16:16:09Z with an expiry of 2026-09-30T16:16:09Z. After the execution occurred, later runs could therefore keep receiving the pre-event cached body even though the publisher page had changed.

## Code change
`scripts/generate.py` now gives only near-term, future-framed state-transition stories a one-hour source revalidation window. A source must contain all three signals before the shorter cache applies:

1. future framing such as scheduled/set/slated/due/expected/planned;
2. a near-term day or clock marker such as Tuesday/today/tonight/6 p.m.; and
3. a state-transition event such as an execution, vote, hearing, sentencing, ruling, launch, reopening/closure, deadline, or similar event.

Stable reporting keeps the existing 24-hour successful-source cache. Existing long-TTL cache entries are also age-checked, so an already-cached volatile source is invalidated on the first run after it is more than one hour old; no cache reset is required.

## Immediate article repair
`data/article-content-overrides.json` permanently resolves the Curtis Beasley article to the confirmed post-execution state. It now records that Beasley was pronounced dead at 6:12 p.m. Tuesday after a three-drug lethal injection and updates the headline/body from the earlier scheduled-execution report.

## Regression coverage
`tests/test_temporal_event_integrity_and_hero_lifetime.py` now verifies:

- the Beasley-style scheduled execution receives the one-hour refresh interval;
- stable completed reporting retains the normal cache behavior;
- an old 24-hour cache entry is invalidated by the new max-age rule; and
- the Beasley content override is terminal/resolved rather than time-bounded pre-event copy.

Validation performed on the overlay source:

- `python -m py_compile scripts/generate.py` — PASS
- temporal/event regression file — 11/11 PASS
- incremental generation cache + source-focus + trusted-source recovery + temporal regression set — 36/36 PASS

## Expected production behavior
On the next production run, the resolved Beasley override will correct the live article even if the source has fallen out of the active feed. For future near-term scheduled stories, stale publisher text can no longer remain cached for a full day simply because the publisher updated the same URL in place.
