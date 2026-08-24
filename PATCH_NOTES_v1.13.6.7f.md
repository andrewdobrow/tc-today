# v1.13.6.7f — Assignment Editor Topic Category-Fit Adjudication

## Scope
This increment changes only the Sonnet 5 assignment-editor shadow contract and its deterministic normalization/diagnostics. It does not alter live publication, county membership authority, story identity, paywall behavior, or final hero reconciliation.

## What changed
- Topic sections now require Sonnet 5 to independently judge whether every queued source genuinely belongs in the requested section before assigning hero/cards.
- Topic keys: `local_gov`, `crime`, `business`, `sports`, `things_to_do`, `florida`.
- The prompt deliberately does **not** encode a weather/crime exclusion list or other hand-maintained topic taxonomy. It asks for ordinary newsroom editorial judgment about the story's central subject and explicitly says upstream routing may be wrong.
- Sonnet returns one `category_fit` decision per source with `fits_category: true|false` and a brief reason.
- A topic source is assignable only if Sonnet explicitly marked it `fits_category:true`.
- Missing, malformed, duplicate, or self-contradictory fit adjudications fail closed in shadow mode.
- Category-fit diagnostics are persisted in `assignment-editor-shadow-report.json` through the existing assignment diagnostics object.

## County pages intentionally unchanged
Martin County, St. Lucie County, and Indian River County keep the existing geographic assignment contract and do not require the extra topic-fit adjudication step. A tornado in Port St. Lucie, for example, remains a valid St. Lucie County candidate.

## Regression coverage
- A source Sonnet rejects for topic fit cannot be committed as hero/card.
- Exact regression: a Port St. Lucie EF0 tornado can be rejected from Crime & Safety without a weather-specific exclusion rule.
- If Sonnet rejects a source and still attempts to assign it, the shadow fails closed.
- County pages remain on the simpler schema and can select a geographically valid tornado story.

## Validation
- 65 focused/broader regression tests passed across assignment editor, category eligibility, model usage, generation containment, final category identity, and model bakeoff suites.
- `python scripts/validate_package.py`: 38 modules imported / 119 public exports verified.
- `py_compile`: passed for modified Python files.
