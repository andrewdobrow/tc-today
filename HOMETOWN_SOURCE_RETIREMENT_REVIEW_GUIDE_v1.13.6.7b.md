# TCT v1.13.6.7b — Hometown News Emergency Source Retirement Review Guide

## Purpose

Immediately stop Hometown News Treasure Coast from entering new automated TCT production runs after repeated stale republications appeared as fresh stories.

## Required workflow

1. Apply the overlay ZIP at repository root **after v1.13.6.7a**.
2. Run **Test Editorial Engine**.
3. If green, run **Update Treasure Coast Today**.
4. Inspect the Generate News log for `Source policy excluded ... Hometown News item(s)` when Hometown entries are present in discovery feeds.
5. Confirm no newly generated article has `hometownnewstc.com` as its source URL.
6. Upload the fresh production repo ZIP and Generate News log for follow-up identity work.

## Production expectations

A new Hometown News item must be rejected whether it arrives as:

- a direct publisher URL;
- a Google News wrapper whose `source` metadata names Hometown News; or
- a Google News title carrying the Hometown publisher suffix.

The rejection must happen before title dedupe and before trusted-publisher recovery.

## Important scope boundary

This hotfix stops the immediate source-quality problem, but it does **not** close the broader duplicate-identity defects already exposed by:

- the Martin County $600K gold-bar scam, which had already fragmented across multiple persistent story IDs; and
- the Herman Nettles/Spanish Lakes burglary arrest, which generated a second canonical URL for the same underlying event.

Those remain the next deterministic identity correction once the emergency Hometown cutoff is live.

## Existing bad pages

This overlay does not retroactively remove pages that were already generated in a production run. Use the next fresh production repo as the authority for any duplicate-page purge/reconciliation so canonical and registry state can be corrected together.
