# TCT v1.13.9.75 — Time-Abbreviation Paragraph Integrity Fix

Apply on top of **v1.13.9.74**.

## Incident fixed
A generated St. Lucie County article rendered the continuing sentence:

`A welcome-home celebration for Enrique is planned for 7 p.m. Friday at the President Donald J. Trump International Airport.`

as two paragraphs, leaving `Friday at ...` as a sentence fragment.

## Changes
- `scripts/generate.py`
  - Generated articles now merge an accidental paragraph break after `a.m.` / `p.m.` when the following paragraph clearly continues with a weekday, date/month, or U.S. timezone.
  - The wall-of-text sentence regrouping path protects the same continuing time constructions, so it cannot reintroduce the split.
  - Custom/manual articles remain immutable: `preserve_all=True` keeps submitted paragraph boundaries unchanged.
- `tct_engine/article_prose_policy.py`
  - Adds a narrow rendered-HTML repair for already-published generated articles with the same broken time-continuation pattern.
  - The existing final sitewide prose-policy pass will repair affected retained article HTML on the next Update TCT run even if the story itself is not regenerated.
  - Genuine sentence endings such as `... 7 p.m.</p><p>Police ...` are not merged.
- `tests/test_time_abbreviation_paragraph_integrity.py`
  - Covers the exact `7 p.m. Friday ...` regression.
  - Covers long wall-of-text regrouping.
  - Covers already-published sitewide repair.
  - Verifies custom article paragraph immutability.
  - Verifies unrelated following sentences are not merged.

## Validation
- Python compile: PASSED for both changed production modules.
- Focused/relevant regression suite: **56 passed**.
- This overlay does not change article identity, deduplication, canonical URLs, images, social metadata, newsletter behavior, membership behavior, or model configuration.
