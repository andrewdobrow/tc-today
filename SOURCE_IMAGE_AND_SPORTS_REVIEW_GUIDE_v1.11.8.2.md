# v1.11.8.2 Production Review Guide

## Expected image-quality indicators

Look for one or more lines like:

```text
Publisher-logo guard rejected hero source image (publisher_logo_or_placeholder_url)
Publisher-logo guard removed 1 cached image(s) before category reuse
Publisher-logo guard cleared 1 live image(s) before archive restoration
Publisher-logo archive migration: 1 archive image(s) replaced; 1 article page(s) updated
Source-image quality: 1 publisher logo/placeholder candidate(s) rejected
```

Review:

`data/source-image-quality-report.json`

For the Indiantown data-center article, confirm that the rejected image points to a TownNews/Hometown News branding or custom asset and that the live article now uses a TCT editorial fallback or a legitimate story photo.

The report should distinguish a rejected branding path such as:

```text
/content/tncms/custom/
```

from allowed editorial-photo paths such as:

```text
/content/tncms/assets/.../editorial/
```

## Expected Sports fast path

When the Sports source pool contains no real athletic lead, expect:

```text
Sports fast recovery: no deterministic hero candidate; skipping Claude and using verified archive recovery
```

In `data/category-generation-report.json`, Sports should show:

```json
{
  "status": "sports_zero_candidate_archive_recovery",
  "archive_recovery_requested": true,
  "attempt_count": 0,
  "model_elapsed_seconds": 0.0,
  "failure_code": "no_sports_hero_candidates"
}
```

When a legitimate St. Lucie Mets, high-school, or other qualifying sports story exists, this fast path should not fire.

## Required final checks

1. Open the Indiantown data-center article and verify the publisher logo is gone.
2. Check its Open Graph preview and article hero image.
3. Confirm the Martin County category hero uses the same valid image.
4. Confirm Sports contains only legitimate sports coverage or verified archive recovery.
5. Confirm all permalink, homepage uniqueness, category membership, RSS, nonstory, and presentation contracts pass.
6. Confirm the commit and Git push complete successfully.

## Files to send for review

- Full workflow log through `git push`
- `data/source-image-quality-report.json`
- `data/category-generation-report.json`
- `data/editorial_observability.json`
- Generated `index.html`
- The corrected Indiantown article HTML, when available
