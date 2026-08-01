# Review Guide — v1.12.2.2 Semantic Candidate Recall Expansion

## Required production verification

After the next run, inspect `data/semantic-publication-gate.json` and verify that both known duplicate groups reach the model:

### Fatal Port St. Lucie intersection crash

- July 31 canonical article
- August 1 duplicate article
- Expected override tier: `strong_headline_similarity`

### Port St. Lucie officer resignation

- `2026-07-29-port-st-lucie-officer-resigned-after-leaving-scene-of-suspected-suicide-without`
- `2026-08-01-port-st-lucie-officer-resigns-after-allegations-he-left-scene-where-man-later-di`
- Expected override tier: `distinctive_token_overlap`
- Expected shared canonical token count: at least eight
- Expected publication gap: three days

For the officer pair, Claude should return `duplicate_use_existing_canonical` unless the August 1 story contains a consequential fact absent from the July 29 article. Different wording, a second outlet, more background, or a differently phrased allegation is not a material update.

## Expected public result

If Claude confirms duplicate/no material update:

- the July 29 officer article remains canonical
- the August 1 officer URL redirects to the July 29 URL
- only the canonical article remains in the homepage, St. Lucie County page, Crime & Safety page, archive, RSS, and sitemap

## Report fields to inspect

For each candidate pair, confirm:

- `structured_conflict_override: true`
- `structured_conflict_override_tier`
- `known_event_key_conflict` or `incident_anchor_conflict`
- `retrieval_score`
- `headline_similarity`
- `day_gap`
- `decision.action`
- `selected_candidate_slug`
- `confidence`
- `shared_anchors`
- `novel_facts`

## Failure behavior

A model timeout, malformed response, low-confidence same-event response, or invalid canonical selection must create a hold. It must not retain or mint a second active permalink as though the candidate gate had passed.

## Regression commands

```bash
python scripts/validate_package.py
python -m pytest tests -v \
  --ignore=tests/test_canonical_identity.py \
  --ignore=tests/test_matcher_contract.py
```
