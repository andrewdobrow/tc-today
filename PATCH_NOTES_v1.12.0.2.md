# Treasure Coast Today v1.12.0.2

## Chronological Latest News rail

The homepage **Latest News** rail previously reused the first five cards from the
importance-ranked Top Stories pool. That made the module display older high-priority
articles instead of the newest TCT publications.

This release separates the two editorial products:

- **Top Stories** remains ranked by impact, relevance and urgency.
- **Latest News** is selected independently from the canonical archive in strict
  reverse TCT publication order.
- The selector uses the full `first_published` receipt when available and falls back
  to the original article date for legacy records.
- `lastmod` is deliberately excluded from ordering so technical reconciliation and
  routine copy edits cannot make an old article appear newly published.
- Duplicate copies of the same canonical publication are collapsed.
- `data/latest-news-rail-contract.json` records the five selected articles and fails
  the build if the rendered order is not the five newest eligible publications.

No story-identity, canonical-ledger or update-context policy is weakened.
