# News Tip form removal + footer Quick Links columns — 2026-09-09

- Removed the News Tip web form and all Formspree/upload handling from the News Tip feature.
- News Tip now uses a direct mailto link to the existing `hello@treasurecoast.today` contact address.
- The existing Advertise Formspree endpoint is unchanged.
- Quick Links in the modern footer are rendered as two real child columns under a single Quick Links heading.
- Retained `footer-v2` pages with a flat Quick Links list are migrated idempotently during the audience-feature pass.
- Asset version bumped to 1.13.8.3 for CSS cache invalidation.
