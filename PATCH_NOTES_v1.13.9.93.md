# TCT v1.13.9.93 — News Tip header containment

Apply on top of v1.13.9.92.

## Problem
The News Tip page uses a semantic `<header class="news-tip-hero">` for the “TCT Newsroom / Send us a news tip” introduction. An old sitewide `header { position: sticky; z-index: 100; }` rule intended for the original masthead also applies to that content header, allowing the intro block to stick and paint over the real TCT masthead while scrolling.

## Fix
- Extends the existing event-detail semantic-header containment rule to `.news-tip-hero`.
- Forces the News Tip content header back into normal document flow with `position: static`, `top: auto`, and `z-index: auto`.
- Leaves `header.site-masthead` sticky and otherwise unchanged.
- Bumps the audience-surface asset token to `1.13.9.44` and updates the current `news-tip.html` so browsers fetch the corrected CSS immediately.
- Does not touch canonical redirects, editorial identity, paywall, membership, events data, or article generation.

## Files
- `style.css`
- `news-tip.html`
- `scripts/build_audience_features.py`
- `tests/test_news_tip_header_containment.py`

## Validation
- News Tip containment + audience-growth regression suite: 31/31 passed.
- Broader masthead/newsroom compatibility suite: 47/47 passed.
- `scripts/build_audience_features.py` Python compile check passed.
