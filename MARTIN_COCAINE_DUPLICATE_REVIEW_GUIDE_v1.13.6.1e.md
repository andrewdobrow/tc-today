# v1.13.6.1e Production Review Guide

After applying the overlay, run **Update Treasure Coast Today**.

Verify:

1. The Aug. 14 article remains the substantive canonical page:
   `2026-08-14-17-arrested-in-indiantown-cocaine-trafficking-ring-three-remain-wanted-after-mon.html`
2. The Aug. 15 duplicate redirects to Aug. 14.
3. The Aug. 16 duplicate redirects to Aug. 14.
4. Neither later duplicate remains as an independent `archive.json` record or archive listing.
5. `_redirects` contains permanent redirect rules for both later URLs.
6. The generated redirect HTML is `noindex` and points to the Aug. 14 canonical.
7. `data/semantic-publication-gate.json` records either semantic duplicate handling or the deterministic verified-production fingerprint migration.
8. No unrelated Martin County drug story with a different arrest count is consolidated.

Expected diagnostic when fingerprint repair runs:
`Verified production duplicate repaired: Operation Beneath the Surface N later URL(s) -> Aug. 14 canonical`
