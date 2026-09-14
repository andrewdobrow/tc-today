# TCT v1.13.9.22 — Nextdoor-only iOS scrolling masthead workaround

- Removes the ineffective v1.13.9.21 offscreen paint shield.
- Detects the Nextdoor iOS in-app browser by its app-specific user-agent token.
- Only in that environment, changes the TCT masthead from sticky to normal document-flow positioning so it scrolls away with the article.
- Safari, Facebook, Chrome, Android, desktop, and other mobile/in-app browsers keep the normal sticky masthead.
- Includes iPadOS desktop-style user-agent handling via MacIntel + touch points, but still requires the Nextdoor token.
- Bumps shared CSS/JS cache token to `1.13.7.5v` so production-normalized pages receive the workaround promptly.
