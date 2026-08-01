# Review Guide — v1.12.2.0 Semantic Final Publication Gate

## Production verification

After the first production run, inspect `data/semantic-publication-gate.json`.

Confirm that:

1. The Marie Martin Port St. Lucie crash pair appears as a bounded candidate comparison.
2. The decision is `duplicate_use_existing_canonical` unless the newer source contains a genuinely material development absent from the older article.
3. The older canonical permalink remains active.
4. The newer duplicate permalink redirects to the canonical page and is absent from the active archive, homepage, category pages, RSS, and sitemaps.
5. Unrelated stories with generic overlap are not submitted unless they cross the candidate threshold.
6. Any model timeout or malformed response creates a publication hold rather than a new URL.

## Material-update review

For decisions marked `update_existing_canonical`, confirm that `novel_facts` contains a consequential development such as an identification, arrest, charge, death following an injury report, official cause, court ruling, sentence, vote, or meaningful casualty revision.

A second source, reordered wording, another photograph, routine background, or additional scene detail is not sufficient.

## Operational review

Check the report summary for:

- candidate pairs
- model calls
- cache hits
- duplicates preserved
- canonical updates selected
- new stories allowed
- holds
- retroactive redirects

A model failure should not create a cache entry. Re-running after a transient failure should invoke Claude again.

## Regression command

```bash
python -m pytest tests -v \
  --ignore=tests/test_canonical_identity.py \
  --ignore=tests/test_matcher_contract.py
```

Then run:

```bash
python scripts/validate_package.py
```
