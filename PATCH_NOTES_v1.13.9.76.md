# TCT v1.13.9.76 — Article list mobile gutter fix

Apply on top of v1.13.9.75.

## Problem
The site-wide CSS reset sets `padding: 0` on all elements. Normal article-body `ul`/`ol` elements did not have their list indentation restored, so outside bullet/number markers could sit in the narrow mobile gutter and appear partially clipped.

## Fix
- Adds explicit spacing only to `.article-body ul` and `.article-body ol`.
- Keeps `list-style-position: outside` for normal editorial typography while reserving sufficient internal gutter for the marker.
- Adds matching article-list typography for desktop and mobile.
- Handles nested lists without changing related-story, navigation, footer, Most Read, or other site lists.
- On screens <= 760px, uses a dedicated 1.55rem article-list gutter so markers remain inside the visible article area.

## Scope
Site-wide for article-body unordered and ordered lists. No article HTML, generator logic, newsletter modal, paywall, navigation, or other components are changed.
