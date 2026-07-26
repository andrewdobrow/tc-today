# TCT v1.11.4.6 — Branded OG Fallbacks

## Purpose

Retire the old AI-generated `/images/fallback/` photographs from automated publication and use TCT's existing branded category and county OG graphics whenever no real story image is available.

## Changes

- Replaces the rotating AI fallback map with:
  - `og-local_gov.png`
  - `og-crime.png`
  - `og-business.png`
  - `og-sports.png`
  - `og-things_to_do.png`
  - `og-florida.png`
  - `og-martin.png`
  - `og-st_lucie.png`
  - `og-indian_river.png`
  - `og-image.png` for generic or unknown categories
- Applies the branded fallback through existing homepage card, category hero, archive recovery, article page, and post-promotion paths.
- Removes every generator reference to `/images/fallback/` and the old numbered AI images.
- Returns no photo credit for branded graphics, preventing a misleading `Photo:` caption.
- Adds a code-ready real-photo library framework, storage structure, naming convention, shot list, and metadata manifest example.
- Does not modify `custom_articles.json` or delete the old files from the repository; they simply stop being selected.

## Engine label

`v1.11.4.6 branded-og-fallbacks`
