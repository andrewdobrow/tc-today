# TCT v1.13.9.77 — Bunny article image mirror pilot

## Scope

Adds provider-neutral article-image provenance with Bunny Storage + Bunny CDN as the
first storage backend. This is for article publishing only; the Events pipeline is
unchanged.

## Safe rollout modes

- `external`: existing publisher-image behavior; no mirror network calls.
- `shadow`: download/upload/verify and persist the registry, but keep publisher URLs live.
- `mirror`: use the TCT-hosted URL only after upload verification and an atomic registry write.

Any mirror failure falls back to the publisher URL and is recorded for retry.

## Persistent files

- `data/article-image-registry.json` — canonical-slug provenance and global SHA-256 object dedupe.
- `data/article-image-mirror-report.json` — per-run observability (generated at runtime).

## GitHub Actions configuration

Secret:
- `BUNNY_STORAGE_ZONE_PASSWORD`

Variables:
- `BUNNY_STORAGE_ZONE_NAME`
- `BUNNY_STORAGE_REGION`
- `BUNNY_STORAGE_API_HOST` (optional if the region-derived host is correct)
- `BUNNY_CDN_BASE_URL`
- `TCT_ARTICLE_IMAGE_MODE`

The workflow defaults to `external`; mirroring cannot activate accidentally.

## Emergency restoration

`scripts/restore_external_article_images.py` restores recorded publisher URLs from the
version-controlled registry without contacting Bunny. It is dry-run by default; use
`--apply` to write changes.
