# v1.11.9.1 — Persistent Incident Anchor Deduplication

Adds deterministic event anchors for two production incidents whose syndicated headline evolution fragmented the persistent story registry:

- Fort Pierce/St. Lucie County infant death, homicide finding and caregiver arrests.
- Martin County Fire Rescue property-tax reform fiscal impacts, including job cuts and station closures.

The anchors are resolved before URL and fuzzy-headline matching, so future variants bind to the existing persistent story and cannot mint a parallel permalink. Existing escaped URLs are permanently redirected to the oldest canonical article.
