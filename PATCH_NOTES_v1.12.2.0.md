# TCT v1.12.2.0 — Semantic Final Publication Gate

## Summary

This release adds a bounded semantic backstop immediately before a generated story can receive a new public permalink.

Deterministic source, story, incident, custom-article, and exact-headline protections still run first. When none of those protections resolves the final article, the publisher now searches only recent canonical stories for high-similarity candidates and asks Claude to make two separate editorial judgments:

1. Does the incoming article describe the same real-world event as a recent canonical story?
2. If it does, is there a material new development that warrants updating the canonical article?

## Publication actions

- Same event with no material update: preserve the existing canonical page and suppress the duplicate permalink.
- Same event with a material update: route the completed copy into the existing canonical permalink.
- Different event: allow normal new-story publication.
- Ambiguous evidence, malformed output, timeout, or API failure: hold the new permalink and report the reason.

Claude returns a structured recommendation only. Deterministic publisher code validates the selected candidate, confidence, action, and target before any archive or page write occurs.

## Candidate retrieval

The gate examines the previous seven days by default and sends at most four candidates to Claude. Candidate nomination uses order-insensitive headline similarity plus available local-news anchors such as locality, event family, named people, precise locations, agencies, incident anchors, and known event keys.

Generic source labels such as weekly roundups are excluded from source-headline similarity so they cannot create broad false candidate pools.

## Existing duplicate repair

Before forward publication, the release also evaluates recent generated archive rows. A recent duplicate confirmed as the same event with no material update is removed from the active archive and retained as a redirect to the older canonical URL. Material updates and uncertain pairs are reported rather than destructively rewritten from rendered historical HTML.

Authoritative custom articles remain outside this repair path.

## Diagnostics and resilience

The release writes:

- `data/semantic-publication-gate.json`
- `data/semantic-publication-gate-cache.json`

The report records candidate scores, Claude decisions, holds, canonical selections, and retroactive redirects. Valid completed adjudications are cached by article content and candidate set. Transient failures and malformed responses are never cached, so the next production run can retry.

Environment controls:

- `TCT_SEMANTIC_GATE_RECENT_DAYS`
- `TCT_SEMANTIC_GATE_MAX_CANDIDATES`
- `TCT_SEMANTIC_GATE_TIMEOUT_SECONDS`
- `TCT_SEMANTIC_GATE_MIN_CONFIDENCE`
