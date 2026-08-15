# v1.13.6.1d production review guide

After applying this overlay and running **Update Treasure Coast Today**, verify the following.

## Exact production repair

The canonical article must remain:

`/articles/2026-08-14-17-arrested-in-indiantown-cocaine-trafficking-ring-three-remain-wanted-after-mon.html`

The newer duplicate must resolve to it:

`/articles/2026-08-15-17-arrested-in-martin-county-cocaine-trafficking-bust-4-kilos-seized-in-indianto.html`

Expected properties:

- the Aug. 14 row remains in `archive.json`;
- the Aug. 15 row is absent from canonical archive surfaces;
- `data/canonical-redirects.json` contains Aug. 15 -> Aug. 14;
- `_redirects` contains an HTTP 301 rule for Aug. 15 -> Aug. 14;
- the Aug. 15 HTML is a noindex redirect page;
- the Aug. 14 HTML remains the substantive article;
- homepage/category/RSS/sitemap surfaces do not expose both permalinks as separate stories.

## General prevention diagnostics

For future narcotics coverage, confirm:

- `firearm` or `firearms` never produce `fire reported` or a fire event type;
- a cocaine/drug seizure is not classified as `animal-case` merely because the source says `seized`;
- narcotics cases can carry `drug-case` event-family evidence;
- formally named law-enforcement operations can produce a stable anchor such as `law-enforcement-operation:beneath-the-surface`;
- near-threshold cross-publisher narcotics rewrites can reach semantic adjudication when same agency, locality, drug family, arrest concept and numeric evidence agree.

## Reports worth checking

- `data/semantic-publication-gate.json`
- `data/event-identity-authority.json`
- `data/forward-publication-identity.json`
- `data/canonical-redirects.json`
- `data/story-regression-report.json`

If the semantic gate resolves the pair before the migration fallback, that is preferred and the fallback should report `not_needed`. If the model is unavailable or the pair otherwise survives semantic repair, the verified migration fallback should still make the redirect deterministic.
