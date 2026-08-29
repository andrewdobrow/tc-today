# TCT v1.13.6.8i — Above-the-fold membership plan cards

## Scope
Presentation-only refinement to `/subscribe.html`.

## Changes
- Replaces the broken right-side membership proof text in the subscription landing-page hero with two compact subscription cards.
- Monthly card: `$1` first month, then `$4.99/month`, direct `data-plan="monthly"` checkout button.
- Annual card: `$49/year`, direct `data-plan="annual"` checkout button.
- Both plan choices are now immediately available above the fold; the full detailed plan comparison remains farther down the page.
- Responsive behavior: cards sit stacked on desktop, side-by-side below the hero copy on tablet, and stack on small mobile screens.
- Bumps the subscribe-page membership stylesheet cache key to `1.13.6.8i`.
- Adds regression coverage requiring both checkout plan buttons to exist in the hero before the rest of the landing-page content.

## Validation
- Package validator: 38 modules / 122 public exports passed.
- Full production-equivalent test suite: 1,026 passed / 0 failed / 41 existing warnings.
