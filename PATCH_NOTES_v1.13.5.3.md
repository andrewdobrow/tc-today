# Treasure Coast Today v1.13.5.3 — Stale Source + Identity Guard

## Why this release exists

A delayed publisher reprint of the Stuart Costco electrical-fire/reopening story was allowed to mint a new TCT permalink even though TCT had already covered the closure and updated the older canonical article with the reopening. The failure was not one bad story ID; it exposed four systemic gaps in the pre-publication path.

## Changes

### 1. Hard age ceiling for NEW publication candidates

- New normal-news permalinks now require a parseable source publication time younger than 48 hours.
- This is separate from category/archive depth windows, which may remain wider for section recovery and display.
- `Things To Do` keeps a wider event-oriented window because future events are intentionally useful even when announced earlier.
- A thin category no longer gets permission to publish an old source merely to fill cards; archive recovery supplies section depth instead.
- Missing/unparseable publisher dates remain fail-open so a source is not rejected solely because metadata is absent.

### 2. Publisher-page extraction contamination guard

- Full-source extraction now detects a large block of unrelated landing/newsletter content before the title-aligned article body.
- When that bounded pattern is present, identity/generation uses the headline-aligned article cluster instead of the entire publisher page.
- Normal articles whose topic begins near the lead are unchanged.

### 3. Final-copy identity no longer re-imports poisoned source identity

- The late-reprint barrier now derives its final comparison features from the final TCT headline/teaser/body/facts only.
- Stored source `incident_anchor`, family, locality, people, location, and agency fields are no longer unioned back into the final-copy identity snapshot.
- This prevents sidebar/newsletter contamination from defeating the second publication barrier.

### 4. Strong same-site delayed-reprint proof

- Electrical/store/commercial fires are recognized as the `fire` incident family.
- Stuart Police is recognized as an agency identity anchor.
- Directional address variants are normalized for comparison only (for example, `3173 S. Kanner Highway` vs. `3173 Kanner Highway`).
- A conservative same-site composite can now prove a delayed business/store reprint when locality, event family, exact site, agency, headline topic, and substantial distinctive-fact overlap all agree.

### 5. Pathological registry catch-all containment

- Added a deliberately high-threshold detector for a persistent story that has become a multi-incident catch-all across many unrelated event families, communities, event keys, and sources.
- Such a record is quarantined and its active event mappings are rebuilt away rather than being allowed to keep authorizing future merges.
- The rule is structural; it contains no numeric story IDs, Costco-specific terms, publisher names, or one-off URL exceptions.
- Long-running single-family stories are explicitly covered by a non-quarantine regression test.

## Production replay

Against the repository state used to build this release:

- the delayed Costco source was over the 48-hour new-publication ceiling;
- the contaminated publisher extraction was reduced to the actual Costco article cluster and unrelated death/shooting material was excluded;
- the existing Aug. 9 duplicate was deterministically matched to the Aug. 6 canonical by final-copy same-site evidence;
- retrospective repair selected exactly one redirect for that archive: the Aug. 9 Costco permalink to the Aug. 6 Costco canonical;
- the pathological active catch-all registry record was detected by the generic structural rule and was the only active record meeting that quarantine threshold.

No archive or registry JSON is included in this overlay. Production must repair its own current runtime state.

## Validation performed

- Python compile check passed for `scripts/generate.py` and `tct_engine/registry_repair.py`.
- 133 focused editorial/membership regression tests passed.
- Package validation passed: 35 modules / 119 public exports.
- Exact current-archive delayed-reprint replay produced one Costco redirect and retained the older canonical.

## Deployment

1. Apply this overlay at repository root on top of v1.13.5.2/current production code.
2. Keep `TCT_MEMBERSHIP_UI_ENABLED=false` while validating this editorial fix.
3. Run **Test Editorial Engine**.
4. If green, run **Update Treasure Coast Today**.
5. Verify the Aug. 9 Costco URL redirects to the Aug. 6 canonical and no stale source is minted as a new article.
