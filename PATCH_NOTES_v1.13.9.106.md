# TCT v1.13.9.106 — Section-owned county/category decks

## Problem
County/category tabs were reconstructed client-side from one globally deduplicated homepage card deck by checking multi-category membership tags. That meant:

- a card owned by `things_to_do` could appear high in Martin County merely because its metadata also contained `martin`;
- global canonical/permalink dedupe could retain the Business/Crime/etc. copy of a story and discard the Martin-owned placement;
- newer Martin stories that were not retained in the global deck could therefore be absent from the Martin tab entirely;
- sorting the surviving visible cards newest-first (v1.13.9.105) could not fix a candidate-set problem.

The Sept. 4 Dolly Parton/Jensen Beach story exposed this exact failure: it entered Martin through its Things To Do placement while much newer Martin reporting existed.

## Fix
- Keep Top News on the existing globally deduplicated Top Stories deck.
- Render a separate hidden card deck for every county/topic directly from that section's own server-built `hero + cards` state.
- Mark those cards with `data-section-owner`.
- County/category navigation now shows only cards whose `data-section-owner` exactly matches the active section.
- Multi-category `data-cats` metadata is retained for identity/projection, but it no longer controls interactive section visibility.
- Dedicated section cards are sorted by immutable publication chronology (`_section_publication_datetime`).
- Exclude the section hero from its card deck and dedupe cards by canonical permalink inside each section.
- Exclude dedicated section cards from the corresponding `More ... Stories` lists.
- Bump audience asset version to `1.13.9.106` so the new navigation behavior is not masked by cached `main.js`.

## Relationship to v1.13.9.105
This patch includes the v1.13.9.105 publication-chronology changes in the full current `generate.py`, `main.js`, and audience feature script. It supersedes v1.13.9.105 and may be applied over either v1.13.9.104 or v1.13.9.105.

## Validation
- `python -m py_compile scripts/generate.py` — passed
- `node --check main.js` — passed
- 14/14 direct section-deck + chronology + membership projection tests — passed
- 110/110 broader homepage/category/county/dedup/navigation/audience tests — passed
