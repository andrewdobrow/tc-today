# Treasure Coast Today v1.13.5.5 — Uniform Paywall Teaser

Incremental overlay for repositories already carrying v1.13.5.4d.

## Reader-facing fix
- Replaces paragraph-dependent previews with a character-bounded teaser across paragraph boundaries.
- Targets up to 340 public characters while keeping at least 90 characters protected.
- Uses a strong vertical text mask so the teaser progresses from fully readable to nearly invisible before the paywall.
- Keeps the protected article text out of public HTML.

## Existing paywalled article migration
- The production workflow first snapshots the current protected article store through the existing server-only content-sync secret.
- Already-paywalled pages are rehydrated in the runner, re-split using the new teaser contract, and then synced back to Supabase.
- New protected rows store the complete article body behind `<!--tct-full-article-v2-->`, making future teaser-format migrations independent of public HTML.
- Member unlock supports both v2 full-body rows and legacy protected-row formats.

## Deployment order
1. Upload this overlay at repository root.
2. Run `Deploy TCT Membership Backend` so the protected-store snapshot action exists server-side.
3. Run `Test Editorial Engine`.
4. If green, run `Update Treasure Coast Today`.

No database migration is required.
