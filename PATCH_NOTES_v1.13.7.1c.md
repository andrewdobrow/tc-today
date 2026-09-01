# TCT v1.13.7.1c — Post-read Story/Paywall Ordering Authority

## Production defect
v1.13.7.1b moved the entire `.tct-member-only` wrapper to the post-story newsletter/share boundary. In the normal generated shell that wrapper was already at that boundary, so the move could be a no-op. More importantly, legacy/unlocked payload shapes can leave `#tct-protected-content` inside that wrapper *after* the paywall section. Moving the wrapper therefore preserves the bad internal order: preview -> paywall -> unlocked continuation.

## Fix
The monthly-free unlock path now normalizes content and sales treatment separately:

1. If an unlocked `#tct-protected-content` continuation is still inside `.tct-member-only`, move the continuation back into the article flow before the wrapper.
2. Move the **paywall section itself** (`[data-tct-paywall]`) to the stable post-story boundary immediately before the article newsletter slot, or share block when no newsletter exists.
3. If neither boundary exists, place the paywall after the last unlocked `.article-body` block.
4. Remove the old `.tct-member-only` scaffolding only after the paywall has a proven destination.

Article #2+ is unchanged: the paywall remains at the teaser boundary because this normalization runs only after a successful `monthly_free` unlock.

## Cache
Membership asset version is `1.13.7.1c`.

## Validation
- Real headless Chromium DOM reproduction verified both current v2 full-body and legacy continuation shapes.
- Current/v2 order: full article body -> post-read membership card -> newsletter -> share.
- Legacy order: public lead -> unlocked protected continuation -> post-read membership card -> newsletter -> share.
- Focused membership/release tests: 42 passed / 0 failed.
- Full CI-equivalent `tests/` suite with standard standalone exclusions: 1060 passed / 0 failed / 44 existing warnings.
