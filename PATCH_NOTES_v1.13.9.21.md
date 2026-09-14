# TCT v1.13.9.21 — iOS / Nextdoor in-app browser masthead bleed mitigation

- Adds an iOS-only, mobile-only solid paint shield above the sticky TCT masthead.
- This targets translucent WKWebView / iOS 26 browser chrome that can reveal scrolled article content above an otherwise opaque sticky header.
- The shield is absolutely positioned outside the masthead, does not affect layout, and accepts no pointer events.
- Bumps shared CSS/JS cache token from `1.13.7.5t` to `1.13.7.5u` so retained and newly generated pages receive the fix after the production normalization pass.
- Adds regression coverage that forbids transform, backdrop-filter, or layout-offset workarounds in this compatibility layer.
