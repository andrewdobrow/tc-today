# Treasure Coast Today v1.13.5.4a — Paywall-aware provenance regression hotfix

This is a test-contract-only hotfix to apply on top of v1.13.5.4.

## Why the workflow failed

The shark-policy provenance regression assumed every committed article page must contain exactly one literal `<div class="article-body">` with all three public paragraphs. That assumption stopped being valid once the membership launch pipeline legitimately persists protected article pages as:

- `article-body tct-member-preview` for the public teaser, and
- an empty `article-body tct-protected-content ...` placeholder whose body is hydrated only after entitlement.

The provenance test was therefore failing on correct paywall output rather than on contaminated shark-policy content.

## Fix

The regression now preserves its actual editorial assertions (no unrelated shark-video source/content, correct WPTV attribution) while accepting both valid publication shapes:

1. full-public article body during dark/non-paywall state; or
2. member-preview + protected-content placeholder during paywall state.

No production generator, membership, Stripe, Supabase, freshness, duplicate, registry, or article content behavior is changed by this hotfix.

## Validation

The focused provenance suite passes in both states:

- full public article: 3 passed
- paywalled member-preview article: 3 passed
