# v1.13.6.7i — Final Pipeline Stabilization

## Purpose
Close the post-generation mutation paths that made assignment-editor bakeoffs unscoreable even when the model decisions themselves were correct.

This increment is deliberately about shared final-package invariants, not model tuning.

## Fixes

### 1. Duplicate suppression preserves story continuity
When a live hero/card is suppressed because it is a proven duplicate of an already-published story, the exact canonical slug is remembered as the preferred recovery target.

Recovery order is now:
1. promote the first surviving valid live card;
2. recover the exact canonical story that caused the duplicate suppression;
3. only then consider unrelated generic archive recovery.

This prevents the Aug. 24 Crime failure where suppression of current crime coverage left the section to recover a Palm City barn-fire article.

### 2. Canonical rebinding is atomic
Final canonical rebinding now adopts the canonical owner's:
- headline
- teaser
- body
- image metadata
- publication metadata
- source/provenance metadata
- persistent story identity

The body is loaded from the canonical article page when it is not stored directly in archive metadata. A canonical fallback uses canonical teaser/headline rather than leaving a different story's body in place.

This permanently covers the prior crash-headline/tornado-body corruption class.

### 3. Geographic containment for headline/lead integrity
Headline/lead claim validation now understands city ↔ parent-county containment:
- Port St. Lucie / Fort Pierce ↔ St. Lucie County
- Stuart / Jensen Beach / Hobe Sound / Palm City / Port Salerno / Indiantown ↔ Martin County
- Vero Beach / Sebastian / Fellsmere ↔ Indian River County

Sibling cities remain distinct. Port St. Lucie in a headline is NOT satisfied by Fort Pierce in the lead.

This fixes the exact Aug. 24 St. Lucie failure where a Port St. Lucie tornado headline was rejected even though the lead explicitly established St. Lucie County.

### 4. Final topic-category integrity gate
After canonicalization, every topic category with an enforced category contract is revalidated again.

If a final hero no longer fits its topic:
- remove it;
- remove invalid cards;
- promote a surviving valid card first;
- recover only after that;
- fail closed if recovery still leaves an invalid enforced-topic placement.

County pages remain under the separate county-membership authority contract.

A machine-readable report is written to:
`data/final-topic-category-integrity.json`

## Exact natural regressions
- Crime hero removed while Flock homicide/privacy card survives → Flock becomes hero before archive recovery.
- Proven duplicate suppression with a canonical Flock article → recover that exact canonical before a newer generic barn-fire archive article.
- Port St. Lucie headline + St. Lucie County lead → valid geographic grounding.
- Port St. Lucie headline + Fort Pierce lead → still invalid.
- Canonical crash headline cannot retain tornado body; copy replacement is atomic.
- Final Crime tornado placement is removed and a valid crime card is promoted.

## Validation
- New/updated stabilization + lead integrity tests: 22 passed.
- Relevant canonical/county stabilization subset: 32 passed.
- Exact repository CI command: 962 passed, 45 warnings.
- `scripts/validate_package.py`: 38 modules imported, 119 public exports verified.
- `scripts/generate.py` compilation: PASS.
