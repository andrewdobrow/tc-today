# TCT v1.13.6.8k — Homepage Framing Provenance Integrity

## Scope
Narrow production fix for the three false homepage article-framing suppressions observed in the 2026-08-30 Generate News run.

## Root causes

### 1. Stale source-index provenance could outrank an exact source URL
`_cached_source_for_generated_item()` previously returned the current packet row at the cached numeric `source_index` before checking the cached article's exact source URL. Source packets are reordered between runs, so a valid cached WFLX hit-and-run article was rebound to a newer WPBF drone story's title/article text while retaining the WFLX URL. The final source-focus guard then compared mixed provenance and falsely reported `generated_copy_drifted_from_source_focus`.

The resolver now:
- treats an exact normalized source URL as authoritative;
- accepts the indexed row only when its URL matches the cached URL;
- otherwise searches the current packet for the exact URL;
- preserves the cached provenance if that historical source is no longer present;
- uses numeric `source_index` only when no stable URL exists.

### 2. Membership paywall markup made archive lead recovery blind
`_archive_article_body()` only understood legacy `<div class="article-body">...</div>` pages. Public protected pages now contain `<div class="article-body tct-member-preview">...</div>` and intentionally omit the protected remainder from the repository. During generation, this caused archive-backed homepage cards to fall back to the shorter `archive.json` teaser instead of the actual visible preview lead.

That produced two false `headline_jurisdiction_missing_from_lead` failures:
- Palm City boat-ramp story: archive teaser omitted `Palm City`, while the live preview starts `Some boaters in Palm City...`.
- Port St. Lucie ICE story: archive teaser starts with the person's name, while the live preview starts `Port St. Lucie High School senior...`.

The archive reader now recognizes the membership preview markup and returns the public preview text when the protected full body is not present. This does not expose or persist protected article content.

## What did not change
- No framing thresholds were weakened.
- No custom-article exemption changed.
- No semantic identity or publication gate changed.
- No paywall entitlement or protected-content storage changed.
- No Stripe/Supabase behavior changed.

## Regression coverage
- Exact source URL outranks a stale source index using the real WFLX/WPBF provenance shape from the incident.
- Membership preview lead is recovered from protected article markup and used by the final homepage framing guard.

## Validation
- Focused framing/cache suite: 23 passed.
- Full CI-equivalent suite: 1,033 passed, 0 failed, 41 existing datetime warnings.
- Package validation: 38 modules / 122 public exports passed.
